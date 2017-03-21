***************
Writing Modules
***************

FAME relies on modules to add functionality. Modules are actually Python classes that inherit from the ``fame.core.module.Module`` class.

Several kind of modules can be created:

* ``ProcessingModule``: this is where FAME's magic is. A ``ProcessingModule`` should define some automated analysis that can be performed on some types of files / analysis information.
* ``ReportingModule``: this kind of module enables reporting options, such as sending analysis results by email, or post a Slack notification when the analysis is finished.
* ``ThreatIntelligenceModule``: this kind of modules acts on IOCs. a ``ThreatIntelligenceModule`` has two roles:

  * Enrich the analysis, by adding Threat Intelligence information on IOCs when they are added to the analysis.
  * Enrich the Threat Intelligence Platform with IOCs extracted by FAME.

* ``AntivirusModule``: modules that act on files, and send them to antivirus vendors.

In order to create a module, create a Python file, and place it in the `fame/modules/processing`, `fame/modules/reporting` or `fame/modules/threat_intelligence` directory.

A valid module is simply a Python class in the `fame/modules` directory that inherits from the :class:`fame.core.module.Module` class.

The `fame/modules` directory contains a subdirectory for each module repository that has been added to your FAME instance. You should create your module inside one of these repositories, where you will be able to commit your changes (create an empty repository if needed).

The best practice is to do the following:

* Create a directory for your module inside one of the repositories.
* Make sure your directory is a valid Python package (do not use spaces, make sure every directory in the path as a ``__init__.py`` file).
* Create a python file inside your directory for your module.
* Inside your python file, create a class that inherits from :class:`fame.core.module.ProcessingModule`, :class:`fame.core.module.ReportingModule`, :class:`fame.core.module.ThreatIntelligenceModule` or :class:`fame.core.module.AntivirusModule`.

Writing a Processing module
===========================

Processing modules are where the malware analysis is made. They will be chained together in order to produce a complete analysis.

A processing module can use the following inputs:

* The main file to analyze
* Files produced by other modules
* The analysis itself, with all its elements

It can produce the following outputs:

* **Probable Name**: this is the malware family. A module should only set the probable name if it has a very high confidence in its diagnostic.
* **Extractions**: this is text information that should be the most useful for the analyst. A typical example would be malware's configuration.
* **Tags**: a tag is a computer-friendly piece of information that describes the analysis. Can be seen as a form of signature name.
* **Generated Files**: files that were produced by the analysis, such as memory dumps.
* **Support Files**: files that can be downloaded by the analyst, such as a sandbox analysis report.
* **Extracted Files**: files that deserve an analysis of their own.
* **IOCs**: indicators of compromise that could be used to detect this malware.
* **Detailed Results**: any kind of information that would be useful to the analyst.

Defining such a module is simple. Just create a Python class that inherits from :class:`fame.core.module.ProcessingModule`, and defines either :func:`fame.core.module.ProcessingModule.each` (recommended), :func:`fame.core.module.ProcessingModule.each_with_type` or :func:`fame.core.module.ProcessingModule.run`.

These methods should return a boolean indicating if the module successfully did its job. If the return value is ``True``, three things will happen:

* A tag with the module's name will automatically be added to the analysis.
* All tags produced by the module (stored in ``self.tags`` will be added to the analysis tags).
* The module detailed results (stored in ``self.results`` will also be added to the analysis).

For example, the module `office_macros` has one goal: extract VBA macros from office files. If it did not extract any macros, because the file did not contain any, the module should return ``False``.

Here is the minimal code required for a (not very useful) module::

    from fame.core.module import ProcessingModule


    class Dummy(ProcessingModule):
        # You have to give your module a name, and this name should be unique.
        name = "dummy"

        # (optional) Describe what your module will do. This will be displayed to users.
        description = "Does nothing."

        # This method will be called, with the object to analyze in target
        def each(self, target):
            return True

Scope
-----

In most cases, FAME will automatically decide when and where a processing module should be executed. These decisions are based on module attributes that you can define.

The most important attribute is :attr:`fame.core.module.ProcessingModule.acts_on` which defines the type of files this module can analyze. As an example, here is the definition of the `office_macros` module::

    class OfficeMacros(ProcessingModule):
        name = "office_macros"
        description = "Extract and analyze Office macros."
        acts_on = ["word", "html", "excel", "powerpoint"]

Not specifying this attribute means that the module can analyze any type of objects.

You can also define conditions that will trigger a module's execution with :attr:`fame.core.module.ProcessingModule.triggered_by`. Creating a module that would execute only on office documents that have macros could be done like this::

    class SomethingOnMacros(ProcessingModule):
        name = "something_on_macros"
        description = "Do something on Office documents with macros"
        acts_on = ["word", "html", "excel", "powerpoint"]
        triggered_by = "office_macros"

This module will only be executed on analyses where the ``office_macros`` tag was added. The default value of ``None`` means that the module is always executed.

Finally, you can define on which workers this module will be executed, if you have several, by defining :attr:`fame.core.module.ProcessingModule.queue`::

    class Dummy(ProcessingModule):
        name = "dummy"
        queue = "some_queue"

The default queue is named ``unix``.

Adding tags and results
-----------------------

Adding tags contributes to the chaining of modules performed by FAME. A tag will be automatically added for every executed module that returned ``True``, but modules also have the possibility to add their own tags with :func:`fame.core.module.ProcessingModule.add_tag`.

While tags are needed by FAME in order to determine which modules to execute, detailed results are useful for the analysts. In order to add results, just put a JSON-serializable object in ``self.results``.

As an example, we will imagine we were able to extract a list of signatures from a sandbox analysis::

    class SandboxSignatures(ProcessingModule):
        name = "sandbox_signatures"

        def each(self, target):
            # Do stuff with target, let's say we were able to get this set of signatures:
            signatures = {
                'http_requests': 'Sample connects to the Internet',
                'high_entropy': 'High entropy, might contain encrypted or compressed data'
            }

            # Add these to tags and detailed results
            self.results = {
                'signatures': []
            }
            for signature in signature:
                self.add_tag(signature)
                self.results['signatures'].append(signatures[signature])

            return True

Adding observables
------------------

It is important that all observables detected by your modules are declared so that they are listed on the analysis and checked against your Threat Intelligence modules.

You can declare an observable to the analysis with the :func:`fame.core.module.ProcessingModule.add_ioc` method. You can also add tags to each observable if you have more information about what this is::

    # Add an observable without tags
    self.add_ioc("http://example.com/url")

    # Add an observable with tags
    self.add_ioc("http://c2.example.com/gate.php", ['c2', 'pony'])

Generated files
---------------

In some cases, modules can generate files that might be useful to other modules. These files should be added to the analysis by calling :func:`fame.core.module.ProcessingModule.register_files`.

Here is an example of a module that is able to generate a memory dump::

    class MemDump(ProcessingModule):
        name = "memdump"

        acts_on = "executable"
        generates = "memory_dump"

        def each(self, target):
            # Do stuff to get a memory dump:
            filepath = get_memdump_somehow(target)

            self.register_files('memory_dump', filepath)

            return True

Note that when your module is able to generate files, you should define the :attr:`fame.core.module.ProcessingModule.generates` attribute in order to specify which type of files can be generated by this module.

Support Files
-------------

Support files are files that are added to an analysis so that they can be downloaded by the analyst. This could be a sandbox report, extracted source code, etc.

In order to add a support file, use the :func:`fame.core.module.ProcessingModule.add_support_file` method::

    self.add_support_file('NAME', filepath)

This will then display a link on the web interface that canbe used to download the file:

.. image:: /images/modules-support-file.png

Extracted Files
---------------

Extracted files are files that deserve their own analysis. A good example is the zip module. It will unzip a file and launch a new analysis on each extracted file.

A module can add an extracted file by calling the :func:`fame.core.module.ProcessingModule.add_extracted_file` method::

    self.add_extracted_file(filepath)

Links to the new analyses will be displayed like this:

.. image:: /images/modules-extracted-files.png

Making results look great again
-------------------------------

By default, FAME will try to render the detailed results of every processing module in a readable way.

However, there are lots of cases where this won't simply be enough. In these cases, you should create a specific template for your module by creating a file named `details.html` in your module's directory.

This file can contain any valid Jinja2 templating code, and can access the detailed results by using the ``results`` variable.

In order for your results to fit nicely in the analysis page, you should use the following template::

    <div class="col-md-12">
        <div class="card">
            <div class="header">
                <h4 class="title">{{name}}</h4>
                <p class="category">Detailed Results</p>
            </div>
            <div class="content">
                YOUR_SPECIFIC CODE HERE
            </div>
        </div>
    </div>

If you need to add links in the bottom of the panel, you can use the following template (to put at the end of the ``#content`` div)::

    <div class="footer">
        <hr>
        <div class="stats">
            <ul>
                <li><a href="#">FIRST_LINK</a></li>
                <li><a href="#">SECOND_LINK</a></li>
                <li><a href="#">...</a></li>
            </ul>
        </div>
    </div>

When your module might have support files, you can use the ``{{support_files(name)}}`` macro in order to display the download links::

    <div class="footer">
        <hr />
        <div class="stats">
            <ul>
                <li><a href="#">FIRST_LINK</a></li>
                <li><a href="#">SECOND_LINK</a></li>
                {{support_files(name)}}
            </ul>
        </div>
    </div>

As an example, here is the default template used::

    <div class="col-md-12">
        <div class="card">
            <div class="header">
                <h4 class="title">{{name}}</h4>
                <p class="category">Detailed Results</p>
            </div>
            <div class="content">
                {% if results is mapping %}
                    {% for key in results %}
                        <h5>{{key}}</h5>
                        {% if results[key] is string %}
                            <pre><code>{{results[key]}}</code></pre>
                        {% else %}
                            <pre><code>{{results[key]|to_json}}</code></pre>
                        {% endif %}
                    {% endfor %}
                {% elif results is string %}
                    <pre><code>{{ results }}</code></pre>
                {% else %}
                    <pre><code>{{ results|to_json }}</code></pre>
                {% endif %}

                {% if 'support_files' in analysis %}
                    {% if name in analysis.support_files %}
                        <div class="footer">
                            <hr />
                            <div class="stats">
                                <ul>
                                    {{support_files(name)}}
                                </ul>
                            </div>
                        </div>
                    {% endif %}
                {% endif %}
            </div>
        </div>
    </div>

Testing Processing Modules
--------------------------

When it comes to testing your processing modules during development, you have two options:

* Use a full FAME instance and test your module by launching new analyses using the web interface. You will need a running worker to execute your module. Note that the workers will not automatically reload modified code, so you should make sure to click on the `Reload` button on :ref:`admin-configuration`.
* The simpler option is to use the :ref:`single_module` utility. This way, you don't need a webserver, a worker or even a MongoDB instance.

Common module features
======================

The following paragraphs define functionalities that are available for all kinds of modules (not just Processing modules).

Configuration
-------------

Your modules will often need additional parameters in order to be able to execute properly. You can specify these configuration options by using the :attr:`fame.core.module.Module.config` attribute.

As an example, consider a module that will submit a file to a sandbox. It will need to know the URL where it can submit files::

    from fame.core.module import ProcessingModule


    class SandboxModule(ProcessingModule):
        name = "sandbox"

        config = [
            {
                'name': 'url',
                'type': 'str',
                'default': 'http://localhost:1234/submit',
                'description': 'URL of the sandbox submission endpoint.'
            },
        ]

``config`` is a list of dictionaries (one for each configuration option), with the following keys:

* ``name``: name of this setting. Will determine how to access this setting in the module.
* ``description``: a description of this setting, to help the user / administrator.
* ``type``: can be ``str``, ``integer``, ``bool`` or ``text``. The difference between ``text`` and ``str`` is only the representation of the setting in forms (input for ``str``, textarea for ``text``).
* ``default`` (optional): default value.
* ``option`` (optional): should this setting be available on a per-analysis basis ? Default value is ``False``.

The submission URL will always be the same, which explains why ``option`` remains ``False``. Adding an option to allow internet access on a per-analysis basis would look like this::

    config = [
        {
            'name': 'url',
            'type': 'str',
            'default': 'http://localhost:1234/submit',
            'description': 'URL of the sandbox submission endpoint.'
        },
        {
            'name': 'allow_internet_access',
            'type': 'bool',
            'default': True,
            'description': 'This allows full Internet access to the sandbox.',
            'option': True
        }
    ]

These two settings are then available in your code by their respective names::

    # Access configured submission URL
    self.url

    # See if internet access is allowed
    self.allow_internet_access

Handling dependencies
---------------------

When your module has some dependencies that are not already FAME dependencies, you should make sure that it is possible to import your module without the dependencies. Instead, check if the dependencies are available in the :func:`fame.core.module.Module.initialize` method::

    try:
        import ijson
        HAVE_IJSON = True
    except ImportError:
        HAVE_IJSON = False

    from fame.common.exceptions import ModuleInitializationError
    from fame.core.module import ProcessingModule

    class SomeModule(ProcessingModule):
        name = "some_module"

        def initialize(self):
            if not HAVE_IJSON:
                raise ModuleInitializationError(self, "Missing dependency: ijson")

You should also provide scripts that will ensure that your dependencies are available. You have the following options (not mutually exclusives):

* Add a ``requirements.txt`` to your module's directory when all is required is to install some python packages.
* Add a ``install.py`` file that will ensure dependencies are installed. If present, this file will be executed.
* Add a ``install.sh`` file that will ensure dependencies are installed. If present, this file will be executed on UNIX systems.
* Add a ``install.cmd`` file that will ensure dependencies are installed. If present, this file will be executed on Windows systems.

.. note::
    The ``install.py``, ``install.sh`` and ``install.cmd`` should exit with a non-zero return code if dependencies are not correctly installed.

    These scripts will be launched at each worker restart, so they should **ensure** dependencies are installed rather than always installing them.

When creating installation scripts, you can use ``from fame.common.constants import VENDOR_ROOT`` in order to put files inside the ``vendor`` subdirectory.

.. note::
    You can also provide additional information and installation information that will be displayed to the user by creating a ``README.md`` file.

Abstract Modules
----------------

Sometimes, it makes sense to create abstract modules in order to provide common functionalities to several modules.

In order to create an abstract module, just define a module without a :attr:`fame.core.module.Module.name`.

When you need configuration options in your abstract module, you should use :attr:`fame.core.module.Module.named_configs` rather than :attr:`fame.core.module.Module.config`. This way, the configuration will be shared between all modules instead of being duplicated::

    class MalwareConfig(ProcessingModule):
        named_configs = {
            'malware_config': {
                'description': 'Needed in order to be able to track malware targets',
                'config': [
                    {
                        'name': 'monitor',
                        'type': 'text',
                        'description': 'List of patterns (strings) to look for in malware configurations. There should be one pattern per line.'
                    }
                ]
            }
        }

``named_configs`` is a dict with the keys being the name of the configuration group.

This setting can then be accessed like this::

    # self.name_of_the_configuration_group.name_of_the_setting
    self.malware_config.monitor

API Reference
=============

This page documents how to create the different kinds of modules, by detailing their respective API, starting with the ``Module`` API, which is common to every kind of module.

Common module API
-----------------

.. autoclass:: fame.core.module.Module
    :members:

Processing Module
-----------------

.. autoclass:: fame.core.module.ProcessingModule
    :members:

Special Processing Modules
^^^^^^^^^^^^^^^^^^^^^^^^^^

Some processing modules define an interface of their own that make it easier to
develop certain kinds of modules:

* :class:`fame.modules.community.processing.vol.Volatility` to develop plugins that rely on the memory analysis framework Volatility.
* :class:`fame.modules.community.processing.malware_config.malware_config.MalwareConfig` to develop plugins that extract useful information from malware configurations.
* :class:`fame.modules.community.processing.apk.apk_plugins.APKPlugin` to develop static APK analysis plugins relying on Androguard. This kind of plugins are a little different, since they do not inherit from :class:`fame.core.module.ProcessingModule`.

.. autoclass:: fame.modules.community.processing.vol.Volatility
    :members:

.. autoclass:: fame.modules.community.processing.malware_config.malware_config.MalwareConfig
    :members:

.. autoclass:: fame.modules.community.processing.apk.apk_plugins.APKPlugin
    :members:

Reporting Modules
-----------------

Reporting Modules are meant to provide hooks in the analysis process for reporting needs. At this point, only one hook is available, when the analysis is finished.

.. autoclass:: fame.core.module.ReportingModule
    :members:

Threat Intelligence Modules
---------------------------

Threat Intelligence Modules have two roles:

* Enrich the analysis with Threat Intelligence data
* Enrich the Threat Intelligence Platform with IOCs extracted by FAME

.. autoclass:: fame.core.module.ThreatIntelligenceModule
    :members:

Antivirus Modules
-----------------

Antivirus Modules are used to submit analyzed files to antivirus vendors so that they can be included to their signatures.

.. autoclass:: fame.core.module.AntivirusModule
    :members:

.. autoclass:: fame.modules.community.antivirus.mail.mail_submission.MailSubmission
    :members:
