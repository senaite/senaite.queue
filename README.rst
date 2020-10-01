Queue of asynchronous tasks for SENAITE LIMS
============================================

.. image:: https://img.shields.io/pypi/v/senaite.queue.svg?style=flat-square
    :target: https://pypi.python.org/pypi/senaite.queue

.. image:: https://img.shields.io/travis/senaite/senaite.queue/master.svg?style=flat-square
    :target: https://travis-ci.org/senaite/senaite.queue

.. image:: https://readthedocs.org/projects/pip/badge/
    :target: https://senaitequeue.readthedocs.org

.. image:: https://img.shields.io/github/issues-pr/senaite/senaite.queue.svg?style=flat-square
    :target: https://github.com/senaite/senaite.queue/pulls

.. image:: https://img.shields.io/github/issues/senaite/senaite.queue.svg?style=flat-square
    :target: https://github.com/senaite/senaite.queue/issues

.. image:: https://img.shields.io/badge/Made%20for%20SENAITE-%E2%AC%A1-lightgrey.svg
   :target: https://www.senaite.com


About
-----

This add-on enables asynchronous tasks for `SENAITE LIMS`_, that allows to
better handle concurrent actions and processes when the workload is high. Is
specially indicated for high-demand instances and for when there are custom
processes that take long to complete. Essentially, `senaite.queue` reduces the
chance of transaction commits by handling tasks asynchronously, in an
unattended and sequential manner.

Once installed, this add-on enables asynchronous processing of those tasks that
usually have a heavier footprint regarding performance, and with highest chance
of transaction conflicts:

* Assignment of analyses to worksheets
* Assignment of worksheet template to a worksheet
* Creation of a worksheet by using a worksheet template
* Workflow actions (submit, verify, etc.) for analyses assigned to worksheets
* Recursive permissions assignment on client contacts creation

This add-on neither provides support for workflow transitions/actions at Sample
level nor for Sample creation. However, this add-on can be extended easily to
match additional requirements.


Documentation
-------------

* https://senaitequeue.readthedocs.io


Contribute
----------

We want contributing to SENAITE.QUEUE to be fun, enjoyable, and educational
for anyone, and everyone. This project adheres to the `Contributor Covenant`_.

By participating, you are expected to uphold this code. Please report
unacceptable behavior.

Contributions go far beyond pull requests and commits. Although we love giving
you the opportunity to put your stamp on SENAITE.QUEUE, we also are thrilled
to receive a variety of other contributions.

Please, read `Contributing to senaite.queue document`_.

If you wish to contribute with translations, check the project site on `Transifex`_.


Feedback and support
--------------------

* `Community site`_
* `Gitter channel`_
* `Users list`_


License
-------

**SENAITE.QUEUE** Copyright (C) 2019-2020 RIDING BYTES & NARALABS

This program is free software; you can redistribute it and/or modify it under
the terms of the `GNU General Public License version 2`_ as published
by the Free Software Foundation.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

.. Links

.. _SENAITE LIMS: https://www.senaite.com
.. _Contributor Covenant: https://github.com/senaite/senaite.queue/blob/master/CODE_OF_CONDUCT.md
.. _Contributing to senaite.queue document: https://github.com/senaite/senaite.queue/blob/master/CONTRIBUTING.md
.. _Transifex: https://www.transifex.com/senaite/senaite-queue
.. _Community site: https://community.senaite.org/
.. _Gitter channel: https://gitter.im/senaite/Lobby
.. _Users list: https://sourceforge.net/projects/senaite/lists/senaite-users
.. _GNU General Public License version 2: https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
