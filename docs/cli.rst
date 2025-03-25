******************
Command line tools
******************

FAME comes with several command line tools to help you with different tasks. They should all be run with :ref:`run`.

.. _run:

run.sh / run.cmd
----------------

FAME is managing its own virtualenv in order to function properly. In order to make sure that all command line tools are using this virtualenv, they should be launched with ``run.sh`` (on UNIX systems), or ``run.cmd`` (on Windows systems).

webserver.py
------------

The web server does not have any option::

    $ utils/run.sh webserver.py

worker.py
---------

You can launch a worker by simply launching the script without arguments::

    $ utils/run.sh worker.py

This script accepts some arguments::

    $ utils/run.sh worker.py -h
    [+] Using existing virtualenv.

    usage: worker.py [-h] [-c CELERY_ARGS] [-r REFRESH_INTERVAL]
                     [queue [queue ...]]

    Launches a FAME worker.

    positional arguments:
      queue                 The task queues that this worker will handle.

    optional arguments:
      -h, --help            show this help message and exit
      -c CELERY_ARGS, --celery_args CELERY_ARGS
                            Additional arguments for the celery worker.
      -r REFRESH_INTERVAL, --refresh_interval REFRESH_INTERVAL
                            Frequency at which the worker will check for updates.

* queue: the name of a queue that this worker should handle. By default, the value is ``unix`` on UNIX systems and ``windows`` on Windows systems.
* CELERY_ARGS: additional arguments to pass to celery. For example, you might want to run more modules concurrently::

    $ utils/run.sh worker.py -c '--concurrency 10'

* REFRESH_INTERVAL: the time (in seconds) between two verification for updates. When an update of modules is detected, the worker will automatically restart. The default value is ``30``.

.. _single_module:

single_module.py
----------------

In order to assist in processing modules' development, FAME provides a little
utility that enables anyone to test a processing module without having a full
FAME instance running (no need for MongoDB, the webserver or a worker).

To use it, run the following command::

    $ utils/run.sh utils/single_module.py <MODULE_NAME> <TARGET_FILE>

This tool will detail all module's output in the console.

By default, this tool will try to find ``MODULE_NAME`` using FAME's standard process, by connecting to the MongoDB instance and fetching the module as well as its current configuration. If it cannot connect to MongoDB or if the requested module is not enabled, the tool will enable "test mode". This mode is directly locating the module using the files on disk, and loading its configuration using default values or asking the user.

Here is the full usage of this tool::

    $ utils/run.sh utils/single_module.py -h
    [+] Using existing virtualenv.

    usage: single_module.py [-h] [-i] [-t] [-l] module file [type]

    Launches a single FAME module.

    positional arguments:
      module             The name of the module to run.
      file               The file to analyze.
      type               The FAME type to use for this file.

    optional arguments:
      -h, --help         show this help message and exit
      -i, --interactive  Ask the user for every configuration option. Without this
                         option, it will use default values when provided. Only
                         used in test mode.
      -t, --test         Enable test mode. This mode does not require connection
                         to the database. It is automatically enabled when a
                         connection is not available or the module is disabled.
      -l, --local        IsolatedProcessingModule will be directly executed on the
                         local system, bypassing the use of virtualization. THIS
                         MIGHT BE DANGEROUS AND INFECT YOUR SYSTEM, ONLY USE IF
                         YOU KNOW WHAT YOU ARE DOING!

Example of using this script to test the `apk` module::

    $ utils/run.sh utils/single_module.py apk /tmp/androrat.apk
    [+] Using existing virtualenv.


    Result: True

    Probable Names: AndroRAT


    ## Extracted Files


    ## IOCs

    boss-dz.zapto.org:1111 (c2, androdat)

    ## Extractions

    -- AndroRAT Configuration --

    {
      "c2": "boss-dz.zapto.org:1111"
    }

    ## Generated Files


    ## Support Files


    ## Logs

    2017-03-07 23:58: warning: apk: z3core: missing dependency: elftools
    ## Detailed results

    {'main_activity': u'my.app.client.LauncherActivity', 'name': u'Ashox', 'main_activity_content': 'package my.app.client;\npublic class LauncherActivity extends android.app.Activity {\n    android.content.Intent Client;\n    android.content.Intent ClientAlt;\n    android.widget.Button btnStart;\n    android.widget.Button btnStop;\n    android.widget.EditText ipfield;\n    String myIp;\n    int myPort;\n    android.widget.EditText portfield;\n\n    public LauncherActivity()\n    {\n        this.myIp = "boss-dz.zapto.org";\n        this.myPort = 1111;\n        return;\n    }\n\n    public void onCreate(android.os.Bundle p4)\n    {\n        super.onCreate(p4);\n        this.setContentView(2130903040);\n        this.Client = new android.content.Intent(this, my.app.client.Client);\n        this.Client.setAction(my.app.client.LauncherActivity.getName());\n        this.btnStart = ((android.widget.Button) this.findViewById(2131099650));\n        this.btnStop = ((android.widget.Button) this.findViewById(2131099651));\n        this.ipfield = ((android.widget.EditText) this.findViewById(2131099648));\n        this.portfield = ((android.widget.EditText) this.findViewById(2131099649));\n        if (this.myIp != "") {\n            this.ipfield.setText(this.myIp);\n            this.portfield.setText(String.valueOf(this.myPort));\n            this.Client.putExtra("IP", this.myIp);\n            this.Client.putExtra("PORT", this.myPort);\n        } else {\n            this.ipfield.setText("boss-dz.zapto.org");\n            this.portfield.setText("1111");\n            this.Client.putExtra("IP", this.ipfield.getText().toString());\n            this.Client.putExtra("PORT", Integer.parseInt(this.portfield.getText().toString()));\n        }\n        this.startService(this.Client);\n        this.btnStart.setEnabled(0);\n        this.btnStop.setEnabled(1);\n        return;\n    }\n\n    public void onResume()\n    {\n        super.onResume();\n        this.setContentView(2130903040);\n        this.Client = new android.content.Intent(this, my.app.client.Client);\n        this.Client.setAction(my.app.client.LauncherActivity.getName());\n        this.btnStart = ((android.widget.Button) this.findViewById(2131099650));\n        this.btnStop = ((android.widget.Button) this.findViewById(2131099651));\n        this.ipfield = ((android.widget.EditText) this.findViewById(2131099648));\n        this.portfield = ((android.widget.EditText) this.findViewById(2131099649));\n        if (this.myIp != "") {\n            this.ipfield.setText(this.myIp);\n            this.portfield.setText(String.valueOf(this.myPort));\n            this.Client.putExtra("IP", this.myIp);\n            this.Client.putExtra("PORT", this.myPort);\n        } else {\n            this.ipfield.setText("boss-dz.zapto.org");\n            this.portfield.setText("1111");\n            this.Client.putExtra("IP", this.ipfield.getText().toString());\n            this.Client.putExtra("PORT", Integer.parseInt(this.portfield.getText().toString()));\n        }\n        this.startService(this.Client);\n        this.btnStart.setEnabled(0);\n        this.btnStop.setEnabled(1);\n        return;\n    }\n\n    public void onStart()\n    {\n        super.onStart();\n        this.onResume();\n        return;\n    }\n}\n', 'receivers': ['my.app.client.BootReceiver', 'my.app.client.AlarmListener'], 'package': u'my.app.client', 'services': ['my.app.client.Client'], 'permissions': ['android.permission.RECEIVE_SMS', 'android.permission.READ_SMS', 'android.permission.SEND_SMS', 'android.permission.READ_PHONE_STATE', 'android.permission.PROCESS_OUTGOING_CALLS', 'android.permission.ACCESS_NETWORK_STATE', 'android.permission.ACCESS_FINE_LOCATION', 'android.permission.INTERNET', 'android.permission.RECORD_AUDIO', 'android.permission.WRITE_EXTERNAL_STORAGE', 'android.permission.CAMERA', 'android.permission.RECEIVE_BOOT_COMPLETED', 'android.permission.CALL_PHONE', 'android.permission.READ_CONTACTS', 'android.permission.VIBRATE']}

.. _create_user:

create_user.py
--------------

.. warning::
    The recommended way of creating users is to use the web interface.

This utility can be used to create a user account when using the `user_password`
authentication module (the one used by default).

Simply execute it and answer the questions::

    $ utils/run.sh utils/create_user.py
    Full Name: John Doe
    Email Address: john.doe@email.com
    Groups (comma-separated): cert
    Default Sharing Groups (comma-separated): cert
    Permissions (comma-separated): submit_iocs,access_joe
    Password:
    Confirm:
    User created.
    Downloaded avatar.

Some fields require more explanation:

* `Groups`: comma-separated list of groups the user belongs to. There is no need for the groups to be created first.
* `Default Sharing Groups`: comma-separated list of groups with which this user's submission will be shared by default. The user will have the possibility of changing this setting globally and on a per-analysis basis.
* `Permissions`: comma-separated list of permissions the user has.

.. _update:

update.py
--------------

If you bring some customization to the core of Fame, you should update it through this utility. Go to fame folder and :

    $ utils/run.sh utils/update.py

and then restart the corresponding service via systemctl. 