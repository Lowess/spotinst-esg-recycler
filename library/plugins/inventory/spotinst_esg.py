# Copyright (c) 2019, Florian Dambrine <android.florian@gmail.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type


DOCUMENTATION = '''
    name: spotinst_esg
    plugin_type: inventory
    requirements:
        - boto3
        - botocore
    short_description: Spotinst ESG inventory source
    extends_documentation_fragment:
        - inventory_cache
        - constructed
        - aws_credentials
    description:
        - Get inventory hosts from Spotinst ESGs.
        - Uses a YAML configuration file that ends with spotinst_esg.(yml|yaml).
    options:
        plugin:
            description: Token that ensures this is a source file for the 'spotinst_esg' plugin.
            required: True
            choices: ['spotinst_esg']

        spotinst_account_id:
            description: Account ID
            required: True
            env:
                - name: SPOTINST_ACCOUNT_ID

        spotinst_api_token:
            description: Spotinst API Token
            required: True
            env:
                - name: SPOTINST_API_TOKEN
'''

# Borrowed from aws_ec2.py
from ansible.errors import AnsibleError
from ansible.module_utils._text import to_native

from ansible.module_utils.basic import json
from ansible.module_utils.urls import open_url
from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable
from ansible.utils.display import Display

try:
    import boto3
    import botocore
except ImportError:
    raise AnsibleError('The spotinst_esg dynamic inventory plugin requires boto3 and botocore.')

display = Display()


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):

    NAME = 'spotinst_esg'  # used internally by Ansible, it should match the file name but not required

    def __init__(self):
        super(InventoryModule, self).__init__()

        self.hostvar_prefix = 'spotinst_'

        # credentials
        self.spotinst_api_token = None

        self.boto_profile = None
        self.aws_secret_access_key = None
        self.aws_access_key_id = None
        self.aws_security_token = None

    def verify_file(self, path):
        '''
            :param loader: an ansible.parsing.dataloader.DataLoader object
            :param path: the path to the inventory config file
            :return the contents of the config file
        '''
        if super(InventoryModule, self).verify_file(path):
            if path.endswith(('spotinst_esg.yml', 'spotinst_esg.yaml')):
                return True
        display.debug("spotinst_esg inventory filename must end with 'spotinst_esg.yml' or 'spotinst_esg.yaml'")
        return False

    def _get_credentials(self):
        '''
            Borrowed from aws_ec2 inventory.
            :return A dictionary of boto client credentials
        '''
        boto_params = {}
        for credential in (('aws_access_key_id', self.aws_access_key_id),
                           ('aws_secret_access_key', self.aws_secret_access_key),
                           ('aws_session_token', self.aws_security_token)):
            if credential[1]:
                boto_params[credential[0]] = credential[1]

        return boto_params

    def _set_credentials(self):
        '''
            Borrowed from aws_ec2 inventory and extended to spotinst.
            Set Spotinst and AWS credentials.
        '''
        self.spotinst_api_token = self.get_option('spotinst_api_token')

        self.boto_profile = self.get_option('aws_profile')
        self.aws_access_key_id = self.get_option('aws_access_key')
        self.aws_secret_access_key = self.get_option('aws_secret_key')
        self.aws_security_token = self.get_option('aws_security_token')

        if not self.boto_profile and not (self.aws_access_key_id and self.aws_secret_access_key):
            session = botocore.session.get_session()
            if session.get_credentials() is not None:
                self.aws_access_key_id = session.get_credentials().access_key
                self.aws_secret_access_key = session.get_credentials().secret_key
                self.aws_security_token = session.get_credentials().token

        if not self.boto_profile and not (self.aws_access_key_id and self.aws_secret_access_key):
            raise AnsibleError("Insufficient boto credentials found. Please provide them in your "
                               "inventory configuration file or set them as environment variables.")

    def _get_connection(self, credentials, region='us-east-1'):
        '''
            Borrowed from aws_ec2 inventory.
        '''
        try:
            connection = boto3.session.Session(profile_name=self.boto_profile).client('ec2', region, **credentials)
        except (botocore.exceptions.ProfileNotFound, botocore.exceptions.PartialCredentialsError) as e:
            if self.boto_profile:
                try:
                    connection = boto3.session.Session(profile_name=self.boto_profile).client('ec2', region)
                except (botocore.exceptions.ProfileNotFound, botocore.exceptions.PartialCredentialsError) as e:
                    raise AnsibleError("Insufficient credentials found: %s" % to_native(e))
            else:
                raise AnsibleError("Insufficient credentials found: %s" % to_native(e))
        return connection

    def _boto3_conn(self, regions):
        '''
            Borrowed from aws_ec2 inventory.
            :param regions: A list of regions to create a boto3 client
            Generator that yields a boto3 client and the region
        '''

        credentials = self._get_credentials()

        if not regions:
            try:
                # as per https://boto3.amazonaws.com/v1/documentation/api/latest/guide/ec2-example-regions-avail-zones.html
                client = self._get_connection(credentials)
                resp = client.describe_regions()
                regions = [x['RegionName'] for x in resp.get('Regions', [])]
            except botocore.exceptions.NoRegionError:
                # above seems to fail depending on boto3 version, ignore and lets try something else
                pass

        # fallback to local list hardcoded in boto3 if still no regions
        if not regions:
            session = boto3.Session()
            regions = session.get_available_regions('ec2')

        # I give up, now you MUST give me regions
        if not regions:
            raise AnsibleError('Unable to get regions list from available methods, you must specify the "regions" option to continue.')

        for region in regions:
            connection = self._get_connection(credentials, region)
            yield connection, region

    def _get_instances_by_region(self, regions, ids, strict_permissions=False):
        '''
            Borrowed from aws_ec2 inventory.
            :param regions: a list of regions in which to describe instances
            :param ids: a list of EC2 ids
            :param strict_permissions: a boolean determining whether to fail or ignore 403 error codes
            :return A list of instance dictionaries
        '''
        all_instances = []

        for connection, region in self._boto3_conn(regions):
            try:
                paginator = connection.get_paginator('describe_instances')
                reservations = paginator.paginate(InstanceIds=ids).build_full_result().get('Reservations')
                instances = []
                for r in reservations:
                    instances.extend(r['Instances'])
            except botocore.exceptions.ClientError as e:
                if e.response['ResponseMetadata']['HTTPStatusCode'] == 403 and not strict_permissions:
                    instances = []
                else:
                    raise AnsibleError("Failed to describe instances: %s" % to_native(e))
            except botocore.exceptions.BotoCoreError as e:
                raise AnsibleError("Failed to describe instances: %s" % to_native(e))

            all_instances.extend(instances)

        return sorted(all_instances, key=lambda x: x['InstanceId'])

    def _request_spotinst(self, endpoint, method='GET'):
        '''
            Interract with Spotinst API.
            :param endpoint: The spotinst API endpoint to query
        '''
        spotinst_api = "https://api.spotinst.io"

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(self.spotinst_api_token)
        }

        uri = "{}/{}".format(spotinst_api, endpoint)
        req = open_url(uri, method=method, headers=headers, validate_certs=True)
        res = json.loads(req.read())

        return res

    def _query(self, account_id):
        '''
            Generate a map of ESGs -> Instances. The Instance object comes from Spotinst API and is then
            enriched with AWS EC2 privateIp data.

            :param account_id: A spotinst account ID to retrieve ESGs from
        '''
        esg_instances = {}
        try:
            # https://api.spotinst.com/spotinst-api/elastigroup/amazon-web-services/list-all-groups/
            esgs = self._request_spotinst(endpoint="aws/ec2/group?accountId={}".format(account_id))

            for item in esgs['response']['items']:
                # https://api.spotinst.com/spotinst-api/elastigroup/amazon-web-services/stateful-api/list-stateful-instances
                esg_details = self._request_spotinst(endpoint="aws/ec2/group/{}/statefulInstance?accountId={}".format(item['id'], account_id))

                # Collect all instance IDs part of the ESG
                for instance in esg_details['response']['items']:
                    # Add attributes to instance object
                    instance['accountId'] = account_id
                    instance['esg_id'] = item['id']
                    instance['esg_name'] = item['name']
                    # Append instance to ESG group (id and name)
                    esg_instances.setdefault(item['id'], []).append(instance)
                    esg_instances.setdefault(item['name'], []).append(instance)

                # If stateful instances found, then gather ips
                if item['id'] in esg_instances:
                    # Get private ips of ESG instances
                    ec2s = self._get_instances_by_region([item['region']], [i['instanceId'] for i in esg_instances[item['id']]])

                    # For each instance update object to append privateIp from AWS
                    for instance in esg_instances[item['id']]:
                        instance.update(
                            {'privateIp': list(filter(lambda ec2: ec2['InstanceId'] == instance['instanceId'], ec2s))[0]['PrivateIpAddress']}
                        )
                else:
                    # TODO Deal with non stateful instances...
                    #   aws/ec2/group/{groupid} does not contain information about instanceId
                    #   if the group is not stateful. Might need to query AWS based on tags
                    pass

        except Exception as e:
            raise AnsibleError("An error occured while parsing Spotinst response: %s" % to_native(e))

        return esg_instances

    def _add_hosts(self, hosts, group):
        '''
            Borrowed from aws_ec2 inventory.
            :param hosts: a list of hosts to be added to a group
            :param group: the name of the group to which the hosts belong
            :param hostnames: a list of hostname destination variables in order of preference
        '''
        for host in hosts:
            self.inventory.add_host(host['privateIp'], group=group)
            for hostvar, hostval in host.items():
                self.inventory.set_variable(host['privateIp'],
                                            "{}{}".format(self.hostvar_prefix, hostvar),
                                            hostval)

    def _populate(self, groups):
        for group, hosts in groups.items():
            self.inventory.add_group(group)
            self._add_hosts(hosts=hosts, group=group)
            self.inventory.add_child('all', group)

    def parse(self, inventory, loader, path, cache=False):
        '''
            Populate the inventory from Spotinst API.
        '''
        super(InventoryModule, self).parse(inventory, loader, path)

        self._read_config_data(path)

        self._set_credentials()

        # get user specifications
        account_id = self.get_option('spotinst_account_id')
        cache_key = self.get_cache_key(path)

        # false when refresh_cache or --flush-cache is used
        if cache:
            # get the user-specified directive
            cache = self.get_option('cache')

        # Generate inventory
        cache_needs_update = False
        if cache:
            try:
                results = self.cache.get(cache_key)
            except KeyError:
                # if cache expires or cache file doesn't exist
                cache_needs_update = True

        if not cache or cache_needs_update:
            results = self._query(account_id)

        # print(results)
        self._populate(results)

        # If the cache has expired/doesn't exist or if refresh_inventory/flush cache is used
        # when the user is using caching, update the cached inventory
        if cache_needs_update or (not cache and self.get_option('cache')):
            self.cache.set(cache_key, results)
