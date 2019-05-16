#!/usr/bin/python

"""Ansible spotinst_aws_stateful module."""

# (c) 2019, Florian Dambrine <android.florian@gmail.com>
#
# This module is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.


ANSIBLE_METADATA = {'metadata_version': '1.0',
                    'status': ['preview'],
                    'supported_by': 'community'}

DOCUMENTATION = '''
---
module: spotinst_aws_stateful
version_added: "2.7"
author: "Florian Dambrine (@Lowess)"
short_description: Manage Stateful Spotinst Elastigroups.
description:
    - A module to manage Stateful Spotinst Elastigroups using Spotinst API.
    - This module is able to recycle a stateful instance from an Elastigroup.
options:
    api_token:
        required: true
        description:
            - (String) Spotinst API token

    account_id:
        required: true
        description:
            - (String) Spotinst account id with format act-xxx. (Example act-12345)

    esg_id:
        required: true
        description:
            - (String) Id of the Elastigroup to operate on with format sig-xxx. (Example sig-227a0005)

    stateful_instance_id:
        required: true
        description:
            - (String) Stateful instance ID with format ssi-xxx. (Example ssi-227a0005)

    state:
        required: false
        choices: [ recyled ]
        description:
            - C(recyled) to recycle a stateful Elastigroup.

    wait_timeout:
        required: false
        default: 600
        description:
            - (Integer) Number of seconds to wait for the operation to complete, default is 10min
'''

EXAMPLES = '''
# Example for recycling a stateful ESG where `spotinst_esg.yml` dynamic inventory is used

- name: Recycle Stateful instance
  spotinst_aws_stateful:
    state: recycled
    esg: "{{ hostvars[inventory_hostname].spotinst_esg_id }}"
    account_id: "{{ hostvars[inventory_hostname].spotinst_accountId }}"
    api_token: "{{ lookup('env', 'SPOTINST_API_TOKEN' )}}"
    stateful_instance_id: "{{ hostvars[inventory_hostname].spotinst_id }}"
  delegate_to: localhost
  register: __testout
'''

RETURN = '''
stateful:
    description: New stateful status of the instance on which the operation was run on.
    returned: changed
    type: dict
    sample: {"createdAt": "2019-02-04T10:10:31.000Z", "devices": [{"deviceName": "/dev/xvdx", "volumeId": "vol-1234"}, ...], "id": "ssi-1234", "instanceId": "i-1234", "launchedAt": "2019-04-03T11:54:43.000Z", "privateIp": "10.201.x.y", "state": "<STATE>"}
'''

import time

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.basic import json
from ansible.module_utils.urls import open_url
from ansible.module_utils.ec2 import (boto3_conn, boto3_tag_list_to_ansible_dict, camel_dict_to_snake_dict,
                                      ec2_argument_spec, get_aws_connection_info)


try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


def _return_result(module, changed, failed, message):
    """todo."""
    result = {}
    if changed:
        pass

    result['stateful'] = message
    result['changed'] = changed
    result['failed'] = failed
    module.exit_json(**result)


def _call_spotinst_api(module, endpoint, method='GET'):
    """Interract with Spotinst API."""
    spotinst_api = "https://api.spotinst.io"

    api_token = module.params.get('api_token')

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {}".format(api_token)
    }

    uri = "{}/{}".format(spotinst_api, endpoint)
    r = None
    try:

        r = open_url(uri, method=method, headers=headers, validate_certs=True)
        result = json.loads(r.read())

        if 'response' in result:
            if result['response']['status']['code'] == 200:
                return result
        else:
            _return_result(module=module, changed=False, failed=True, message="Spotinst API raised an error: {}".format(result['response']))
    except ValueError as e:
        if r is not None:
            _return_result(module=module, changed=False, failed=True, message=r)
        else:
            _return_result(module=module, changed=False, failed=True, message='An unexpected exception occurred while calling Spotinst')
    except Exception as e:
        _return_result(module=module, changed=False, failed=True, message=str(e))


def _wait_for_stateful_instance(module, wait_timeout, pending_state, final_state='ACTIVE'):
    """TODO."""
    ssi = module.params.get('stateful_instance_id')
    endpoint = "aws/ec2/group/{}/statefulInstance?accountId={}".format(module.params.get('esg_id'),
                                                                       module.params.get('account_id'))

    # Build a list of states that the instance should be validated against
    states_path = [pending_state, final_state]
    timeout = time.time() + wait_timeout

    result = None
    while time.time() < timeout and len(states_path) > 0:
        result = _call_spotinst_api(module, endpoint, method='GET')

        instance_status = next((item for item in result['response']['items'] if item["id"] == ssi), None)
        if instance_status is not None:
            if instance_status['state'] == states_path[0]:
                states_path.pop(0)
            else:
                time.sleep(5)

    if len(states_path) > 0:
        _return_result(module=module, changed=False, failed=True,
                       message=("The instance ({}) could not transition from {} to {} "
                                "for [{}] operation before the timeout ({}s)".format(ssi,
                                                                                     pending_state,
                                                                                     final_state,
                                                                                     module.params.get('state'),
                                                                                     wait_timeout)))
    # Return True if no timeout
    else:
        return instance_status


def _get_instances_by_region(module, region, ids):
    """Get a list of EC2 instances matching the given list of IDs."""
    region, ec2_url, aws_connect_params = get_aws_connection_info(module, boto3=True)
    connection = boto3_conn(module, conn_type='client', resource='ec2', region=region, endpoint=ec2_url, **aws_connect_params)

    all_instances = []

    try:
        paginator = connection.get_paginator('describe_instances')
        reservations = paginator.paginate(InstanceIds=ids).build_full_result().get('Reservations')
        instances = []
        for r in reservations:
            instances.extend(r['Instances'])
    except ClientError as e:
        _return_result(module=module, changed=False, failed=True, message="Failed to describe instances: {}".format(e))

    all_instances.extend(instances)

    return sorted(all_instances, key=lambda x: x['InstanceId'])


def recycle_elastigroup(module):
    """Perform a recyling operation on a Stateful Spotinst instance."""
    ssi = module.params.get('stateful_instance_id')
    wait_timeout = int(module.params.get('wait_timeout'))
    endpoint = "aws/ec2/group/{}/statefulInstance/{}/recycle?accountId={}".format(module.params.get('esg_id'),
                                                                                  ssi,
                                                                                  module.params.get('account_id'))

    # Safety check as Stateful operations can only be performed when instance is in ACTIVE state
    _wait_for_stateful_instance(module, wait_timeout=wait_timeout, pending_state='ACTIVE')

    _call_spotinst_api(module, endpoint=endpoint, method='PUT')
    recycled_instance = _wait_for_stateful_instance(module, wait_timeout=wait_timeout, pending_state='RECYCLING')

    # If a Stateful instance does no have privateIp persistance gather new privateIp
    if 'privateIp' not in recycled_instance:
        endpoint = "aws/ec2/group/{}?accountId={}".format(module.params.get('esg_id'),
                                                          module.params.get('account_id'))
        # Gather information about the instance's ESG group to know in which region it is running
        esg_info = _call_spotinst_api(module, endpoint=endpoint)

        # Get the first instance found
        ec2 = _get_instances_by_region(module, region=[esg_info['response']['items'][0]['region']], ids=[recycled_instance['instanceId']])[0]

        # Append privateIp to the Spotinst instance object
        recycled_instance.update(
            {'privateIp': ec2['PrivateIpAddress']}
        )

    _return_result(module=module, changed=True, failed=False, message=recycled_instance)


def main():
    """Module entrypoint."""
    argument_spec = ec2_argument_spec()

    argument_spec.update(dict(
        api_token=dict(required=True, type='str'),
        account_id=dict(required=True, type='str'),
        esg_id=dict(required=True, type='str'),
        stateful_instance_id=dict(required=True, type='str'),
        state=dict(required=False, choices=['recycled'], default='recycled'),
        wait_timeout=dict(required=False, default=600)
    )),

    module = AnsibleModule(
        argument_spec=argument_spec,
    )

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    state = module.params.get('state')

    if state == 'recycled':
        recycle_elastigroup(module)

if __name__ == '__main__':
    main()
