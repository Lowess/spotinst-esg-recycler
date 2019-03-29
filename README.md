# Spotinst-esg-recycler

Spotinst ESG Recycler helps you roll [Stateful Elastigroups](https://spotinst.com/blog/stateful-applications-spot-instances/) from [Spotinst](https://spotinst.com)

[GumGum](https://gumgum.com) leverages stateful elastigroups to run and deploy immutable AMI such as Zookeeper, Kafka, Elastisearch clusters.

In the even of changing the underlying AMI used by your stateful ESG, you will need to recycle each instance one by one in order to get the new AMI fully rolled out.

The solution proposed here leverages [Ansible](https://www.ansible.com/) in order to perform this recycling action.

## :package: What's in there ?

### :gear: `spotinst_esg` inventory plugin

* An [inventory plugin](https://docs.ansible.com/ansible/latest/user_guide/intro_dynamic_inventory.html)  named `spotinst_esg` that uses Spotinst API to build an inventory file made of Spotinst stateful instances (`library/inventory/spotinst_esg.py`)

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
