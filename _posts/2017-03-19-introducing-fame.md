---
layout: post
cover: 'assets/images/cover2.jpg'
title: Introducing FAME
date: 2017-03-19 16:00:00
tags: announcements
subclass: post
author: cert
---

At CERT Société Générale, we have our fair share of malware to analyze: banking malware, targeting the bank's customers, and all kinds of malware targeting our users.

The process of malware analysis in our team had two main issues:

* It takes too much time to complete an analysis. Let's take the example of a banking trojan. Even if the analyst already recognized the malware family from the spam run, he still has to submit the sample to a sandbox, wait for the analysis to be over, download a memory dump, extract the configuration from memory and compare the configuration with our perimeter in order to determine if we are targeted. It the malware family is unknown, it is even more complicated.
* Every analyst does not necessarily have the same knowledge regarding malware analysis.

Our answer to these problems is FAME, our malware analysis platform.

<!--more-->

FAME is a malware analysis pipeline, that will chain the execution of modules in order to perform end-to-end analysis. In the best case scenario, an analyst will submit a sample, wait for a few minutes, and FAME will be able to recognize the malware family, extract its configuration and identify how the malware is targeting your organization.

### Not a sandbox

FAME is not a malware analysis sandbox and it will not be very useful if not combined with a sandbox. It already has support for Cuckoo Sandbox (the cuckoo-modified version) and Joe Sandbox.

### A framework

FAME should be seen as a framework. Instead of developing various malware analysis scripts, create FAME modules that will be able to interact with each others.

Creating a FAME module is as simple as creating a Python class:

```python
from fame.core.module import ProcessingModule


class DummyModule(ProcessingModule):
    name = "dummy"
    description = "Does nothing. Give me something useful to do !"

    def each(self, target):
        # Do something useful !

        return True
```

Still, FAME comes with some useful modules out of the box, see the [fame_modules repository](https://github.com/certsocietegenerale/fame_modules) for the list of currently available modules.

An example of available module is office_macros, which leverages [oletools](https://github.com/decalage2/oletools) to analyze Office macros.

![alt text](/assets/images/screenshots/fame_detailed_results.png "Office Macros")

### Leverage your Threat Intelligence

Threat Intelligence modules are automatically used by FAME to enrich your analysis with tags and indicators from your Threat Intelligence platforms.

![alt text](/assets/images/screenshots/fame_ti.png "TI is awesome")

You can also add observables to your Threat Intelligence Platform directly from FAME. At this point, FAME comes with support for [Yeti](https://yeti-platform.github.io/).

### Open-Source

We were really pleased with our experience open-sourcing [FIR](https://github.com/certsocietegenerale/FIR), our incident management platform.

That is why we are now releasing FAME, hoping it will help incident response teams with their malware analysis needs. We cannot wait to hear about your ideas and use the awesome modules that will be created by the community. See the [Community](FIXME) page for more details.

### Get yours today

Sounds interesting ? Get started now by getting the code from [GitHub](https://github.com/certsocietegenerale/fame). Do not forget to [read the docs](FIXME).
