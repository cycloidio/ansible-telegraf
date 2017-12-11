# Cycloid telegraf

This role just use https://github.com/dj-wasabi/ansible-telegraf and add some features.

  * `telegraf_aws_checks: true` : Install Cycloid aws check for telegraf based on https://github.com/sensu-plugins/sensu-plugins-aws/tree/master/bin

Requirements.yml

```
- src: git@github.com:cycloidio/ansible-telegraf.git
  version: master
  name: cycloid.telegraf
  scm: git

- src: https://github.com/dj-wasabi/ansible-telegraf
  version: master
  name: dj-wasabi.telegraf
  scm: git
```

Call :

```                                                                                                                                                                                                                                                                                                                                                                     
     - {role: cycloid.telegraf, tags: telegraf}
```

