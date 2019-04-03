# Spotinst-esg-recycler

Spotinst ESG Recycler helps you roll [Stateful Elastigroups](https://spotinst.com/blog/stateful-applications-spot-instances/) from [Spotinst](https://spotinst.com)

[GumGum](https://gumgum.com) leverages stateful elastigroups to run and deploy immutable AMI such as Zookeeper, Kafka, Elastisearch clusters.

In the even of changing the underlying AMI used by your stateful ESG, you will need to recycle each instance one by one in order to get the new AMI fully rolled out.

The solution proposed here leverages [Ansible](https://www.ansible.com/) in order to perform this recycling action.

## :package: What's in there ?

### :gear: `spotinst_esg` inventory plugin

* An [inventory plugin](https://docs.ansible.com/ansible/latest/user_guide/intro_dynamic_inventory.html)  named `spotinst_esg` that uses Spotinst API to build an inventory file made of Spotinst stateful instances (`library/inventory/spotinst_esg.py`)

* Inventory output example:

```bash
# Define mandatory plugin variables through env vars
$ export AWS_PROFILE=some_profile
$ export SPOTINST_ACCOUNT_ID=act-123
$ export SPOTINST_API_TOKEN=xxxxxx

# Invoke plugin
$ ansible-inventory  -i inventories/demo.spotinst_esg.yml --list
```

```json
{
    "_meta": {
        "hostvars": {
            "x.y.z.100": {
                "spotinst_accountId": "act-1234",
                "spotinst_createdAt": "2019-02-04T10:10:31.000Z",
                "spotinst_devices": [
                    {
                        "deviceName": "/dev/xvdx",
                        "volumeId": "vol-1234"
                    },
                    {
                        "deviceName": "/dev/xvdz",
                        "volumeId": "vol-2345"
                    },
                    {
                        "deviceName": "/dev/xvdy",
                        "volumeId": "vol-3456"
                    },
                    {
                        "deviceName": "/dev/xvdw",
                        "volumeId": "vol-4567"
                    }
                ],
                "spotinst_esg_id": "sig-1234",
                "spotinst_esg_name": "spotinst-elastigroup-demo",
                "spotinst_id": "ssi-1234",
                "spotinst_instanceId": "i-1234",
                "spotinst_launchedAt": "2019-04-03T08:36:44.000Z",
                "spotinst_privateIp": "10.201.0.107",
                "spotinst_state": "ACTIVE"
            },
            },
            "x.y.z.120": {
                ...
            },
            "x.y.z.50": {
                ...
            },
            ...
        }
    },
    "all": {
        "children": [
            "sig-1234",
            "ungrouped",
            "spotinst-elastigroup-demo",
            ...
        ]
    },
    "sig-1234": {
        "hosts": [
            "x.y.z.100",
            "x.y.z.100",
            "x.y.z.100"
        ]
    },
    "ungrouped": {},
    "spotinst-elastigroup-demo": {
        "hosts": [
            "x.y.z.100",
            "x.y.z.100",
            "x.y.z.100"
        ]
    },
    ...
}
```

> :point_up: Please note that `hostvars` are prefixed with `spotinst_`.

#### :books: An example of inventory `demo.spotinst_esg.yml` using the `spotinst_esg` plugin

In order to make use of the inventory you need to make sure the following required variables are set properly

```yaml
plugin: spotinst_esg

aws_profile: some_profile         # Can also be set with AWS_PROFILE / AWS_DEFAULT_PROFILE

### Spotinst settings
spotinst_account_id: act-123      # Can also be set with SPOTINST_ACCOUNT_ID
spotinst_api_token: xxxxxx        # Can also be set with SPOTINST_API_TOKEN

### Inventory cachehing
cache: True
cache_plugin: jsonfile
cache_connection: ~/.ansible
```

> :point_up: Inventory caching is also supported please see [enabling fact cache plugins](https://docs.ansible.com/ansible/latest/plugins/cache.html#enabling-fact-cache-plugins)

### :gear: `spotinst_aws_stateful` custom module

> :point_up: Please not that right now the module only supports `recycling` stateful elastigroups but the gap to implement other stateful operations such as `deallocate`, `pause` and `resume` should be fairly straight forward. PR welcome :blush:

---

#### spotinst_aws_stateful

Manage Stateful Spotinst Elastigroups.

  * Synopsis
  * Options
  * Examples

##### Synopsis
 A module to manage Stateful Spotinst Elastigroups using Spotinst API.
 This module is able to recycle a stateful instance from an Elastigroup.

##### Options

| Parameter            | Required | Default | Choices                     | Comments                                                                                 |
|:---------------------|:--------:|:--------|:----------------------------|:-----------------------------------------------------------------------------------------|
| account_id           |   yes    |         |                             | (String) Spotinst account id with format act-xxx. (Example act-12345)                    |
| stateful_instance_id |   yes    |         |                             | (String) Stateful instance ID with format ssi-xxx. (Example ssi-227a0005)                |
| state                |    no    |         | <ul> <li>recyled</li> </ul> | C(recyled) to recycle a stateful Elastigroup.                                            |
| esg_id               |   yes    |         |                             | (String) Id of the Elastigroup to operate on with format sig-xxx. (Example sig-227a0005) |
| api_token            |   yes    |         |                             | (String) Spotinst API token                                                              |
| wait_timeout         |    no    | 500     |                             | (Integer) Number of seconds to wait for the operation to complete                        |


##### Examples

```
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

```

---

### :gear: `recycle-esg.yml` playbook to perform a rolling recycle on a Spotinst ESG

#### :books: Playbook example:

```yaml
- name: Recycle Kafka ESG
  hosts: <esg-name>
  gather_facts: false
  serial: 1

  vars:
    recycle_check_port: 9092

  tasks:
    - name: Recycle stateful instance and wait for it
      block:

        - name: Recycle stateful instance
          spotinst_aws_stateful:
            state: recycled
            esg_id: "{{ hostvars[inventory_hostname].spotinst_esg_id }}"
            account_id: "{{ hostvars[inventory_hostname].spotinst_accountId }}"
            api_token: "{{ lookup('env', 'SPOTINST_API_TOKEN' )}}"
            stateful_instance_id: "{{ hostvars[inventory_hostname].spotinst_id }}"
          register: __spotinst_recycled_instance

        - name: Dump recycled output
          debug:
            msg: "{{ __spotinst_recycled_instance }}"
            verbosity: 2

        - name: Wait for port to be up
          wait_for:
            state: present
            host: "{{ __spotinst_recycled_instance.stateful.privateIp }}"
            port: "{{ recycle_check_port }}"

      delegate_to: localhost

```

#### :metal: Playbook execution and output:

```sh
# Required exports
$ export AWS_PROFILE=some_profile
$ export SPOTINST_API_TOKEN=xxxxxx

# Make use of the custom inventory spotinst_esg.yml
$ ansible-playbook -i inventories/demo.spotinst_esg.yml recycle-esg.yml

PLAY [Recycle Kafka ESG] *************************************************************************************************************

TASK [Recycle stateful instance] *****************************************************************************************************
changed: [10.201.0.x -> localhost]

TASK [Dump recycled output] **********************************************************************************************************
skipping: [10.201.0.x]

TASK [Wait for port to be up] ********************************************************************************************************
ok: [10.201.0.x -> localhost]

PLAY [Recycle Kafka ESG] *************************************************************************************************************

TASK [Recycle stateful instance] *****************************************************************************************************
changed: [10.201.0.y -> localhost]

TASK [Dump recycled output] **********************************************************************************************************
skipping: [10.201.0.y]

TASK [Wait for port to be up] ********************************************************************************************************
ok: [10.201.0.y -> localhost]

PLAY [Recycle Kafka ESG] *************************************************************************************************************

TASK [Recycle stateful instance] *****************************************************************************************************
changed: [10.201.0.z -> localhost]

TASK [Dump recycled output] **********************************************************************************************************
skipping: [10.201.0.z]

TASK [Wait for port to be up] ********************************************************************************************************
ok: [10.201.0.z -> localhost]

PLAY RECAP ************************************************************************************************************************************************************
10.201.0.x               : ok=3    changed=1    unreachable=0    failed=0
10.201.0.y               : ok=3    changed=1    unreachable=0    failed=0
10.201.0.z               : ok=3    changed=1    unreachable=0    failed=0

Playbook run took 0 days, 0 hours, 17 minutes, 34 seconds
```

---

Made with :heart: by Florian Dambrine @GumGum
