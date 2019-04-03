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

> :point_up: Please note that `hostvars` are not populated yet... Feel free to open a PR and contribute.

### :books: An example of inventory `demo.spotinst_esg.yml` using the `spotinst_esg` plugin

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

### :gear: Ansible role and playbook to perform a rolling recycle on a Spotinst ESG

TODO
