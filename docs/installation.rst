************
Installation
************

.. note::
    This page documents how to install FAME on Ubuntu 20.04. FAME being written in Python, you can install it on the system of your choice.

The easy way
============

Probably the most easy way to run fame is::

    $ git clone https://github.com/certsocietegenerale/fame.git
    $ cd fame/docker
    $ cp fame.env.template fame.env
    $ echo "DEFAULT_EMAIL=admin@changeme.fame" >> fame.env
    $ echo "DEFAULT_PASSWORD=changeme" >> fame.env
    $ docker-compose up --build


Then browse http://localhost:4200/ using your web browser, and login using the `docker first run default credentials <https://github.com/certsocietegenerale/fame/blob/master/docker/fame.env.template>`_  (admin@changeme.fame / changeme)

These commands are very nice for having a first look to what fame is, but you may also want to install fame without docker. This is especially true given that FAME use docker internally for its activities, which leads to Docker-in-Docker situation.

Here is how to install fame without docker :

Dependencies
============

Install dependencies::

    $ sudo apt install git python3-pip python3-dev
    $ sudo pip3 install virtualenv

MongoDB
-------

FAME also relies on MongoDB as a database. You should not install MongoDB using `apt` because it is using an old version **that will not work**. Instead, follow installation guidelines available on MongoDB's website: https://docs.mongodb.org/manual/tutorial/install-mongodb-on-ubuntu/

.. note::
    MongoDB does not have to be on the same system as FAME's web server.

If needed, you should make sure to make MongoDB start when the system boots::

    $ sudo systemctl enable mongod

Make sure that MongoDB is started::

    $ sudo systemctl start mongod

By default, MongoDB only listens on localhost. If your MongoDB instance is on a different server than FAME, or if you plan to use remote workers, you should change this setting in the configuration file (`/etc/mongod.conf`) by commenting the `bindIp` directive::

    net:
      port: 27017
    #  bindIp: 127.0.0.1

It is also recommended to enable authentication on the MongoDB server. In order to do this, start by creating an admin user, as well as a user for FAME::

    $ mongo
    > use admin
    switched to db admin
    > db.createUser({ user: "admin", pwd: "SOME_STRONG_PASSWORD", roles: [ { role: "userAdminAnyDatabase", db: "admin" } ] })
    Successfully added user: {
       "user" : "admin",
       "roles" : [
           {
               "role" : "userAdminAnyDatabase",
               "db" : "admin"
           }
       ]
    }
    > use fame
    switched to db fame
    > db.createUser({ user: "fame", pwd: "SOME_OTHER_STRONG_PASSWORD", roles: [ { role: "dbOwner", db: "fame" } ] })
    Successfully added user: {
        "user" : "fame",
        "roles" : [
            {
                "role" : "dbOwner",
                "db" : "fame"
            }
        ]
    }

Then, you have to enable RBAC in the configuration file (`/etc/mongod.conf`)::

    security:
      authorization: enabled

All these modifications will only be effective once `mongod` is restarted::

    $ sudo systemctl restart mongod

Docker
------

Some modules rely on docker to properly execute. If you want to use these modules, follow these additional instructions.

Install docker::

    $ sudo apt install docker.io

Add the user to the docker group::

    $ sudo groupadd docker
    $ sudo usermod -aG docker $USER

Restart the system for changes to be effective::

    $ sudo reboot

Install FAME
============

Start by cloning the repository::

    $ git clone https://github.com/certsocietegenerale/fame
    $ cd fame

Run the install script, and answer the questions (choose '1' for installation type)::

    $ utils/run.sh utils/install.py

.. note::
    Every FAME command has to be run with `utils/run.sh`. This makes sure that everything takes place in FAME's virtualenv and will create it if it does not exists.

    On Windows, you have to use `utils/run.cmd`.

Running FAME
============

For FAME to work properly, you should have the web server running::

    $ utils/run.sh webserver.py

As well as a worker::

    $ utils/run.sh worker.py

Installation on a production environment
========================================

The commands shown above are good for development environments. In production, you will want to run the web server and the worker as daemons.

.. note::
    In this paragraph, we will describe how to set up FAME in production environments on Ubuntu 20.04, using nginx, uwsgi and systemd. If your setup differs, you will have to adapt these instructions.

Register the web server and the worker as services
--------------------------------------------------

Install uwsgi::

    $ sudo pip3 install uwsgi

Create a systemd configuration file for the web server, at `/etc/systemd/system/fame_web.service`::

    [Unit]
    Description=FAME web server

    [Service]
    Type=simple
    ExecStart=/bin/bash -c "cd /REPLACE/WITH/YOUR/PATH/fame && uwsgi -H /REPLACE/WITH/YOUR/PATH/fame/env --uid REPLACE_WITH_YOUR_USER --gid REPLACE_WITH_YOUR_USER --socket /tmp/fame.sock --chmod-socket=660 --chown-socket REPLACE_WITH_YOUR_USER:www-data -w webserver --callable app"

    [Install]
    WantedBy=multi-user.target

Create a second systemd configuration file for the worker, at `/etc/systemd/system/fame_worker.service`::

    [Unit]
    Description=FAME workers

    [Service]
    Type=simple
    User=REPLACE_WITH_YOUR_USER
    ExecStart=/bin/bash -c 'cd /REPLACE/WITH/YOUR/PATH/fame && utils/run.sh worker.py'

    [Install]
    WantedBy=multi-user.target

In both files, make sure to replace `REPLACE_WITH_YOUR_USER` with the user that should run FAME (usually the one used in order to clone the repository), and `/REPLACE/WITH/YOUR/PATH/fame` with the path to your FAME installation.

Then, enable the two services, so that they automatically start at boot time, and start them::

    $ sudo systemctl enable fame_web
    $ sudo systemctl enable fame_worker
    $ sudo systemctl start fame_web
    $ sudo systemctl start fame_worker


Serve the application with nginx
--------------------------------

Install nginx::

    $ sudo apt install nginx

Remove the default configuration file::

    $ sudo rm /etc/nginx/sites-enabled/default

Create the file `/etc/nginx/sites-available/fame` with the following contents::

    upstream fame {
        server unix:///tmp/fame.sock;
    }

    server {
        listen 80 default_server;

        # Allows big file upload
        client_max_body_size 0;

        location / {
          include uwsgi_params;
          uwsgi_pass fame;
        }

        location /static/ {
          alias /REPLACE/WITH/YOUR/PATH/fame/web/static/;
        }
    }

Once again, make sure to replace `/REPLACE/WITH/YOUR/PATH/fame` with the path to your FAME installation.

Enable your configuration file, and restart nginx::

    $ sudo ln -s /etc/nginx/sites-available/fame /etc/nginx/sites-enabled/fame
    $ sudo systemctl restart nginx

.. note::
    In most settings, we recommend updating this configuration to use HTTPS instead of HTTP, but this is not described here as each organization handles certificates differently.

Accessing FAME
==============

If you followed instruction in order to install FAME in production, you should now be able to access FAME at http://DOMAIN_OR_IP/.

Otherwise, the development version should be available at http://DOMAIN_OR_IP:4200/.

You can now follow the :ref:`admin`.

Installing a remote worker
==========================

FAME can have as many workers as you want. This can be useful in order to analyze more malware at the same time, or to have different capabilities (for example, a Windows worker could use different tools).

The installation process for a remote worker is the same, with less steps. You can only add a remote worker if you already have a working FAME installation.

Install dependencies::

    $ sudo apt-get install git python-pip
    $ sudo pip install virtualenv

Clone the repository::

    $ git clone https://github.com/certsocietegenerale/fame
    $ cd fame

Run the install script, and answer the questions (choose '2' for installation type)::

    $ utils/run.sh utils/install.py worker

You can now start your worker::

    $ utils/run.sh utils/worker.py

In production environments, you can use the same systemd configuration file detailed above.

You might want to have a look at the worker's documentation (FIX LINK) if you want to customize your setup (for example in order to use different queues).

Installing on Windows
=====================

When installing on Windows, install the following dependencies:

* Python 3 (https://www.python.org/)
* Git (https://git-scm.com/download/win)

You can then follow the same installation instructions::

    > pip install virtualenv
    > git clone https://github.com/certsocietegenerale/fame
    > cd fame
    > utils\run.cmd utils\install.py

Before starting FAME, make sure to follow the specific installation instructions for `python-magic` on Windows (https://github.com/ahupp/python-magic#dependencies). The three DLLs should be on your PATH (you can directly put them in the `fame` directory if you want).

Isolated Processing Modules
===========================

Some modules (that inherit from ``IsolatedProcessingModule``) require the use of Virtual Machines to work properly. You will recognize these modules by the fact that they are asking for virtualization information in their configuration.

Here is how you can create a Virtual Machine that will work with these modules:

* Use virtualization software that has a ``VirtualizationModule`` (FAME currently has support for Virtualbox and KVM).
* Install the operating system of your choice (verify the module's requirements in the module's README).
* Install Python 3.
* Install flask (``pip install flask``).
* Configure networking. You have two options:
    * Use NAT. If you do, you have to make sure to enable port forwarding so that port 4242 inside the guest is mapped to a port of your choice on the host. This port should then be specified in the module's configuration.
    * Use Host-Only. If you do, make sure to set a static IP address and specify this IP address in the module's configuration.
* Make sure to install module's dependencies (see module's README for instructions).
* Copy FAME's agent (in ``agent/agent.py``) on the system.
* Make sure the agent is running.
* Create a snapshot. You have to put the snapshot name in the module's configuration.

.. note::
    Depending on what you are trying to do, your Virtual Machine might need some hardening in order for malware to properly execute. These steps are not described here.


Updating FAME
=============

When you want to update your instance, you can use the following command::

    $ utils/run.sh utils/update.py

Then, do not forget to restart the webserver and worker for changes to be effective. On a production environment, this would be done with the following commands::

    $ sudo systemctl restart fame_web
    $ sudo systemctl restart fame_worker
