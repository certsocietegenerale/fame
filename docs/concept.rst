*******
Concept
*******

FAME was built to facilitate malware analysis by automating as many tasks as possible.

The real work of malware analysis is done by processing modules.

FAME will do its best to determine what processing modules should be run during each analysis, and will chain modules' execution in order to achieve end-to-end analysis.

Each processing module can produce the following analysis elements:

* **Probable Name**: this is the malware family. A module should only set the probable name if it has a very high confidence in its diagnostic.
* **Extractions**: this is text information that should be the most useful for the analyst. A typical example would be malware's configuration.
* **Tags**: a tag is a computer-friendly piece of information that describes the analysis. Can be seen as a form of signature name.
* **Generated Files**: files that were produced by the analysis, such as memory dumps.
* **Support Files**: files that can be downloaded by the analyst, such as a sandbox analysis report.
* **Extracted Files**: files that deserve an analysis of their own.
* **IOCs**: indicators of compromise that could be used to detect this malware.
* **Detailed Results**: any kind of information that would be useful to the analyst.

When analyzing a file, the first step is to determine the file type. FAME will try to determine the file type based on the file extension and `python-magic`. A FAME-specific file type will then be associated to the file using different indicators (examples: "executable", "word", "pdf", etc.).

Then, the analyst has to choose between two types of analysis: :ref:`concept-magic` (recommended) or :ref:`concept-targeted`.

.. _concept-magic:

Just Do Your Magic
==================

In this mode of operation, FAME will start by executing every `generic` processing module that knows how to handle the file type previously determined. `Generic` modules are modules that are always interesting to execute on a given file type. For example, putting the file in a sandbox.

Execution of these modules will then potentially trigger execution of other modules. There is several reasons this could happen:

* The processing module generated new files (for example, a memory dump). In this case, all `generic` processing modules that can apply on memory dumps will be executed.
* The processing module generated some tags. Tags can be seen as a form of signatures. They control modules' execution chaining. For example, the tag `cuckoo[dridex]` might be generated if cuckoo thinks the sample is a Dridex sample. The specific module `dridex` would then be executed since it is triggered by any tag containing the word `dridex`.


Analysis is finished when there is no more processing modules to execute.

.. _concept-targeted:

Targeted analysis
=================

When using targeted analysis, the analyst asks for a specific processing module to run on the file.

In this case, we have to differentiate between two scenarios:

* If the target module is directly applicable to the file type previously determined, it is executed.
* If not, FAME will try to find a suitable execution path to fulfill the analyst's demand. For example, if the analyst asked for the `dridex` module, that acts on `memory dumps`, but the analyzed file is an `executable`, FAME will first execute the `cuckoo` module, which takes an `executable`, and produces a `memory dump`.

The rules of processing modules' execution chaining described in the previous paragraph still apply.

Different kinds of modules
==========================

FAME relies on modules to add functionality. Modules are actually Python classes that inherit from the ``fame.core.module.Module`` class.

Several kind of modules can be created:

* ``PreloadingModule``: these modules can be used to preload a given hash provided to FAME for analysis so that the sample file is available to FAME without the need of manually downloading it.
* ``ProcessingModule``: this is where FAME's magic is. A ``ProcessingModule`` should define some automated analysis that can be performed on some types of files / analysis information.
* ``ReportingModule``: this kind of module enables reporting options, such as send analysis results by email, or post a Slack notification when the analysis is finished.
* ``ThreatIntelligenceModule``: this kind of modules acts on IOCs. a ``ThreatIntelligenceModule`` has two roles:

  * Enrich the analysis, by adding Threat Intelligence information on IOCs when they are added to the analysis.
  * Enrich the Threat Intelligence Platform with IOCs extracted by FAME.

* ``AntivirusModule``: modules that act on files, and send them to antivirus vendors.

Architecture
============

FAME relies on three components:

* A MongoDB database, storing everything and serving as a link between other components.
* A web server, that is serving the web application, and exposing internal services.
* Any number of workers (at least 1), which are performing the actual analysis tasks.

.. image:: /images/concept-architecture.png

Components can all be on the same server, or split across multiple servers.

The web server is where antivirus modules and threat intelligence modules are executed.

Everything else (preloading modules, processing modules, reporting modules and intelligence modules lookups) is executed on workers.
