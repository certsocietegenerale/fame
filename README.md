# What is FAME ?

FAME is a recursive acronym meaning “FAME Automates Malware Evaluation”.

It is meant to facilitate analysis of malicious files, leveraging as much knowledge as possible in order to speed up and automate end-to-end analysis.

Best case scenario: the analyst drops a sample, waits for a few minutes, and FAME is able to determine the malware family and extract its configuration and IOCs.

FAME should be seen as a framework that will empower your malware analysis development efforts.

You can get more information (and screenshots !) on the [website](https://certsocietegenerale.github.io/fame) and in the [documentation](https://fame.readthedocs.io/).

![screenshot](https://certsocietegenerale.github.io/fame/assets/images/screenshots/fame_detailed_results.png)

![screenshot](https://certsocietegenerale.github.io/fame/assets/images/screenshots/fame_observables.png)

# Installation

The detailed installation instructions can be found in the [documentation](https://fame.readthedocs.io/en/latest/installation.html).

# Community

Want to contribute as a developer or user ? See the [community page](https://certsocietegenerale.github.io/fame/community).

# Technical Specs

FAME is a Python application that relies on the following technologies:

* flask for the web framework
* celery for background tasks
* MongoDB (and pymongo) for the database

# Credits

Thanks to the guys over at [Creative Tim](http://www.creative-tim.com/) for their awesome Bootstrap theme. Download your version for free [here](http://demos.creative-tim.com/light-bootstrap-dashboard).

Robots lovingly delivered by [Robohash.org](https://robohash.org/).
