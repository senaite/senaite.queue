
*Open Source LIMS Core based on the CMS Plone*
==============================================

.. image:: https://img.shields.io/pypi/v/senaite.queue.svg?style=flat-square
    :target: https://pypi.python.org/pypi/senaite.queue

.. image:: https://img.shields.io/travis/senaite/senaite.queue/master.svg?style=flat-square
    :target: https://travis-ci.org/senaite/senaite.core

.. image:: https://img.shields.io/github/issues-pr/senaite/senaite.queue.svg?style=flat-square
    :target: https://github.com/senaite/senaite.queue/pulls

.. image:: https://img.shields.io/github/issues/senaite/senaite.queue.svg?style=flat-square
    :target: https://github.com/senaite/senaite.queue/issues

.. image:: https://img.shields.io/badge/Made%20for%20SENAITE-%E2%AC%A1-lightgrey.svg
   :target: https://www.senaite.com



About
=====

This is an **EXPERIMENTAL PACKAGE, use at your own risk**

This package enables asynchronous tasks in Senaite to better handle concurrent
actions and processes when senaite's workload is high, especially for instances
with high-demand on writing to disk. 

At present time, this add-on provides support for workflow transitions for
analyses and worksheets mostly (e.g., verifications, submissions, assignment of
analyses to worksheets, creation of worksheets by using workseet templates, etc.).

Transitions for sample levels could be easily supported in a near future.

The asynchronous creation of Sample is not supported yet.

Usage
=====

Create a new user in senaite (under `senaite/acl_users`) with username
`queue_daemon` and password `queue_daemon`. It will not work when using acl
users registered in Plone's root (e.g. `admin`).

Add a new client in your buildout:

.. code-block::

  # Reserved user queued tasks
  queue-user-name=queue_daemon
  queue-user-password=queue_daemon
  parts =
      ....
      client_queue


and configure the client properly:

.. code-block::

  [client_queue]
  # Client reserved as a worker for async tasks
  <= client_base
  recipe = plone.recipe.zope2instance
  http-address = 127.0.0.1:8088
  zope-conf-additional =
  # Queue tasks dispatcher
  <clock-server>
      method /senaite/queue_dispatcher
      period 10
      user ${buildout:queue-user-name}
      password ${buildout:queue-user-password}
      host localhost:8088
  </clock-server>


Screenshots
===========

Queued analyses
---------------

.. image:: https://raw.githubusercontent.com/senaite/senaite.queue/master/static/queued_analyses.png
   :alt: Queued analyses
   :width: 760px
   :align: center

Queued worksheet
----------------

.. image:: https://raw.githubusercontent.com/senaite/senaite.queue/master/static/queued_worksheet.png
   :alt: Queued worksheet
   :width: 760px
   :align: center


License
=======

**SENAITE.QUEUE** Copyright (C) 2019 Senaite Foundation

This program is free software; you can redistribute it and/or modify it under
the terms of the `GNU General Public License version 2
<https://github.com/senaite/senaite.storage/blob/master/LICENSE>`_ as published
by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
