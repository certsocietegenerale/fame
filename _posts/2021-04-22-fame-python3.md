---
layout: post
cover: "assets/images/cover2.jpg"
title: Python 3 Update
date: 2021-04-22 08:00:00
tags: announcements
subclass: post
author: gael
---

We are glad to announce that FAME and the community FAME modules have finally been updated to (only) support Python 3.

FAME is still being used daily by several teams to analyze malware and these changes will allow us to keep maintaining and improving FAME in the future.

This update is still compatible with existing setups, which means you should be able to update and keep all your existing files, analyses and configurations.

<!--more-->

### New Features

During the four years since our initial blog post, some features were added, in the form of new module types:

- _IsolatedProcessingModule_ can be created to analyze malware samples inside virtual machines, without having to worry about orchestrating these virtual machines.
- _VirtualizationModule_ will take care of orchestrating these virtual machines for you. Two modules are currently available: _virtualbox_ and _kvm_.
- _FiletypeModule_ can be used when file type recognition is more difficult than looking at the extension or the MIME type of a file.
- _PreloadingModule_ are the new way used by FAME to analyze files when only a hash is submitted. This way, you can leverage several sources of hash to file conversion, including internal repositories that will not input your API quota of external services. You can also define priorities to determine which _PreloadingModule_ will be tried first. We would like to thank [Luca Ebach](https://twitter.com/lucebac) for this contribution.

### How to migrate ?

If you want to setup a new instance, you can follow the [installation documentation](https://fame.readthedocs.io/en/latest/installation.html).

If you already have a Python 2 instance and would like to migrate it to the Python 3 version, we recommend you follow the following steps.

- Stop running instances

```
$ sudo systemctl stop fame_web
$ sudo systemctl stop fame_worker
```

- Make sure Python 3 is installed (use at least Python 3.6)

```
$ sudo apt install git python3-pip python3-dev
$ sudo pip3 install virtualenv uwsgi
```

- Backup your existing installation

```
$ mv fame fame.py2_backup
```

- Clone the repository

```
$ git clone https://github.com/certsocietegenerale/fame
```

- Copy old files to the new directory

```
$ cp -r fame.py2_backup/conf fame.py2_backup/storage fame
```

- Run the installation script, and make sure you use the same MongoDB information (you can look at _fame/conf/fame.conf_ if needed)

```
$ cd fame
$ utils/run.sh utils/install.py
```

- Restart the services

```
$ sudo systemctl start fame_web
$ sudo systemctl start fame_worker
```

Note that you might also need to update remote workers or virtual machines used by _IsolatedProcessingModule_.

### What took us so long ?

It has now been a while since Python 2 is dead, so what took us so long ?

First of all, like most open-source projects, we have limited bandwidth to invest in structural changes like this.

The core of the FAME framework was not too difficult to migrate, but it took a lot longer to migrate our community FAME modules. Indeed, several Python libraries had to be upgraded or replaced, with some of them changing their APIs. Some examples:

- Androguard had some major changes which means we had to adapt all APK Plugins.
- Volatility3 is a complete rewrite of the memory analysis framework, which means we also had to completely rewrite Volatility based modules.
- The _cutthecrap_ module used the winappdbg library to debug Office applications. Since this library does not have a version compatible with Python 3, we had to do a complete rewrite of the module using [Frida](https://frida.re/)

We hope you will enjoy this update :)
