************
Installation
************

.. note::
    FAME provides Dockerfiles and a preconfigured ``docker-compose.yml`` for deploying FAME via Docker.

.. _docker:

======
Docker
======

This part of the page presents information on how to run FAME via Docker.

Preliminaries
=============

First, you need to have a running docker environment on your machine (preferably including ``docker-compose``). The Docker community provides information on how to install Docker for different operating systems: https://docs.docker.com/install/

.. note::
    The docker installation method was only tested on Ubuntu 18.04 LTS. By the nature of Docker it should work on all supported platforms but **any other platform than Ubuntu 18.04 LTS is untested**.

Once you have Docker running, spinning up a working FAME environment is as simple as ``docker-compose up -d``. FAME will listen internally on ``http://fame-web:8080`` so you a required to have a properly configured web server accessible within the FAME stack to be able to access FAME from within your local network.

Configuration
=============

The Docker container can be configured by environment variables only. All available environment variables are described below.

:FAME_INSTALL_COMMUNITY_REPO: (web only) Defines whether or not to install the community module repository when spawning a fresh instance.
:FAME_URL: (worker/web) On the *worker*, this defines the (internal) base URL of the fame-web container (e.g. ``http://fame-web:8080/``). For the *web* container, this defines at which URL the web interface will be available to the users (e.g. ``http://fame.example.com/``)
:FAME_ADMIN_FULLNAME: (web only) The full name of the admin user (e.g. ``FAME Admin``).
:FAME_ADMIN_EMAIL: (web only) The email address of the admin user (e.g. ``admin@fame.example.com``). **Note**: this must be a valid email address. Otherwise logging in through the web interface will not be possible.
:FAME_ADMIN_GROUPS: (web only) The default list of groups for the admin user (e.g. ``cert``).
:FAME_ADMIN_DEFAULT_SHARING: (web only)
:FAME_ADMIN_PERMISSIONS: (web only)
:FAME_ADMIN_PASSWORD: (web only) The password of the admin user account.
:FAME_PUBLIC_KEY: (web only) The SSH *public* which is shown to the admins when a private repository is to be cloned (e.g. ``ssh-rsa [..] FAME deploy key``).
:FAME_SECRET_KEY: (web only) The Flask secret to use for session encryption. Should be generated randomly (e.g. via ``cat /dev/urandom | head -c 32 | xxd -p | tr -d '\n'``).
:DOCKER_HOST: (worker only) The address of the docker daemon (e.g. ``unix:///var/run/docker.sock``). Please refer to the official Docker documentation of this variable for all allowed values.
:MONGO_HOST: (worker/web) The (internal) hostname of the MongoDB instance that powers FAME.
:MONGO_PORT: (worker/web) The port of the MongoDB instance that powers FAME.
:MONGO_DB: (worker/web) The database name which FAME should use.
:MONGO_USERNAME: The username of the FAME MongoDB user (**note**: this value must match the user defined in ``docker/mongo/adduser.js``).
:MONGO_PASSWORD: The password of the FAME MongoDB user (**note**: this value must match the password defined in ``docker/mongo/adduser.js``).

Serving FAME in Docker
======================

We recommend using Traefik (https://traefik.io) for serving the FAME web interface. The provided ``docker-compose.yml`` file includes all necessary information for Traefik to serve FAME properly (depending on your configuration of Traefik this also includes serving FAME via TLS).

Docker networking
=================

The default configuration creates an internal network for all FAME containers. If you use your own Docker network stack, it is strongly recommended to put all FAME containers into the same dedicated Docker network to achieve container isolation.

.. note::
    The worker containers need to have a working internet connection to be able to install module requirements. The web interface is not required to have a working internet connection in general. Only if you like fancy profile avatars or want to use antivirus modules a working internet connection is required. Threat intel modules only need to be able to connect to their target instance and thus an internet/network connection is only required if the target instance is not available within the FAME network.


=======================
Bare-Metal Installation
=======================

.. note::
    This part of the page documents how to install FAME on Ubuntu 16.04. FAME being written in Python, you can install it on the system of your choice.

Dependencies
============

Install dependencies::

    $ sudo apt-get install git python-pip python-dev
    $ sudo pip install virtualenv

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
    In this paragraph, we will describe how to set up FAME in production environments on Ubuntu 16.04, using nginx, uwsgi and systemd. If you setup differs, you will have to adapt these instructions.

Register the web server and the worker as services
--------------------------------------------------

Install uwsgi::

    $ sudo pip install uwsgi

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

    $ sudo apt-get install nginx

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

    $ utils/run.sh utils/install.py

You can now start your worker::

    $ utils/run.sh utils/worker.py

In production environments, you can use the same systemd configuration file detailed above.

You might want to have a look at the worker's documentation (FIX LINK) if you want to customize your setup (for example in order to use different queues).

Installing on Windows
=====================

When installing on Windows, install the following dependencies:

* Python 2.7 (https://www.python.org/)
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
* Install Python 2.7.
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
