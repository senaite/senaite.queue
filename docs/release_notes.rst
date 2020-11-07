Release notes
=============

Update from 1.0.1 to 1.0.2
--------------------------

With version 1.0.2, the legacy storage for queued tasks has changed and helper
storages (e.g. for Worksheets) are no longer required. ``IQueued`` marker
interface is no longer used neither. Most of the base code has been refactored
keeping in mind the following objectives:

* Less complexity: less code, better code
* Less chance of transaction commit conflicts
* Boost performance: better experience, with no delays

All these changes also makes the add-on easier to extend and maintain. The
downside is that old legacy storage is no longer used and therefore, tasks that
were queued before the upgrade will be discarded.

* Be sure there are no remaining tasks in the queue before the upgrade
* If you have your own add-on extending ``senaite.queue``, please review the changes
  and check if some parts of your add-on require modifications

A queue server has been introduced. Therefore, two zeo clients are recommended:
one that acts as the server and at least another one in charge of consuming
tasks. Also, this version now depends on three additional packages: ``requests``,
``senaite.jsonapi`` and ``cryptography``. Please read the installation
instructions and run buildout to download the dependencies.
