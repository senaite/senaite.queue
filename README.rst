*Queue of asynchronous tasks for SENAITE LIMS*
==============================================

.. image:: https://img.shields.io/pypi/v/senaite.queue.svg?style=flat-square
    :target: https://pypi.python.org/pypi/senaite.queue

.. image:: https://img.shields.io/travis/senaite/senaite.queue/master.svg?style=flat-square
    :target: https://travis-ci.org/senaite/senaite.queue

.. image:: https://img.shields.io/github/issues-pr/senaite/senaite.queue.svg?style=flat-square
    :target: https://github.com/senaite/senaite.queue/pulls

.. image:: https://img.shields.io/github/issues/senaite/senaite.queue.svg?style=flat-square
    :target: https://github.com/senaite/senaite.queue/issues

.. image:: https://img.shields.io/badge/Made%20for%20SENAITE-%E2%AC%A1-lightgrey.svg
   :target: https://www.senaite.com


About
=====

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


Configuration
=============

Some parameters of `senaite.queue` can be configured from SENAITE UI directly.
Login as admin user and visit "Site Setup". A link "Queue Settings" can be found
under "Add-on configuration". From this view you can either disable queue for
specific actions and configure the number of items to be processed by a single
queued task for a given action.


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

Queue settings
--------------

.. image:: https://raw.githubusercontent.com/senaite/senaite.queue/master/static/queue_settings.png
   :alt: Queue configuration view
   :width: 760px
   :align: center


How to see the queued tasks
===========================

Login with `admin` user and visit the following address: http://<your_senaite_site>/queue_gc

To beautify the JSON results, you might install JSON Lite for Firefox:
https://addons.mozilla.org/en-US/firefox/addon/json-lite/?src=recommended


Empty queue
-----------

.. code-block:: json

    {
      "tasks": [],
      "locked": null,
      "current": null,
      "processed": {},
      "container": "/senaite/bika_setup",
      "speed": -1,
      "id": "senaite.queue.main.storage"
    }


Empty queue, but with a task processed recently
-----------------------------------------------

Queue can be empty (empty list in `tasks` attribute), but with a task recently
processed. Note that the last task processed, with additional info, is displayed
under `processed` key:


.. code-block:: json

    {
    "tasks": [],
    "locked": null,
    "current": null,
    "processed": {
      "context_uid": "9188a07b15be428d83c7a9f615dc8e28",
      "request": {
        "HTTP_USER_AGENT": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36",
        "X_REAL_IP": "",
        "_orig_env": {
          "SERVER_SOFTWARE": "Zope/(2.13.28, python 2.7.12, linux2) ZServer/1.1",
          "SCRIPT_NAME": "",
          "REQUEST_METHOD": "POST",
          "PATH_INFO": "/VirtualHostBase/https/192.168.0.32/senaite/VirtualHostRoot//worksheets/WS19-1850/workflow_action",
          "HTTP_ORIGIN": "https://192.168.0.32",
          "SERVER_PROTOCOL": "HTTP/1.0",
          "channel.creation_time": 1573034435,
          "HTTP_X_REAL_IP": "192.168.0.126",
          "CONNECTION_TYPE": "close",
          "HTTP_USER_AGENT": "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36",
          "HTTP_REFERER": "https://192.168.0.32/worksheets/WS19-1850",
          "SERVER_NAME": "localhost",
          "REMOTE_ADDR": "127.0.0.1",
          "PATH_TRANSLATED": "/VirtualHostBase/https/192.168.0.32/senaite/VirtualHostRoot/worksheets/WS19-1850/workflow_action",
          "SERVER_PORT": "8085",
          "CONTENT_LENGTH": "415",
          "HTTP_SEC_FETCH_MODE": "navigate",
          "HTTP_HOST": "192.168.0.32",
          "HTTP_SEC_FETCH_SITE": "same-origin",
          "HTTP_UPGRADE_INSECURE_REQUESTS": "1",
          "HTTP_CACHE_CONTROL": "max-age=0",
          "HTTP_ACCEPT": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3",
          "GATEWAY_INTERFACE": "CGI/1.1",
          "HTTP_X_FORWARDED_FOR": "192.168.0.126",
          "HTTP_ACCEPT_LANGUAGE": "en-US,en;q=0.9",
          "HTTP_SEC_FETCH_USER": "?1",
          "CONTENT_TYPE": "application/x-www-form-urlencoded",
          "HTTP_ACCEPT_ENCODING": "gzip, deflate, br"
         },
        "HTTP_REFERER": "https://192.168.0.32/worksheets/WS19-1850",
        "REMOTE_ADDR": "127.0.0.1",
        "AUTHENTICATED_USER": "sisyal",
        "X_FORWARDED_FOR": ""
      },
      "name": "task_action_submit"
    },
    "container": "/senaite/bika_setup",
    "speed": 2,
    "id": "senaite.queue.main.storage"
    }


Empty queue, but with a task undergoing
---------------------------------------

If queue is empty, but with a task undergoing, the task is stored in `current`,
but an empty list is displayed in `tasks`:

.. code-block:: json

    {
    "tasks": [],
    "locked": 1573034850.609937,
    "current": {
      "context_uid": "9188a07b15be428d83c7a9f615dc8e28",
      "request": {
        "HTTP_USER_AGENT": "python-requests/2.18.4",
        "X_REAL_IP": "",
        "_orig_env": {
          "CONNECTION_TYPE": "keep-alive",
          "HTTP_ACCEPT": "*/*",
          "HTTP_USER_AGENT": "python-requests/2.18.4",
          "SERVER_NAME": "localhost",
          "GATEWAY_INTERFACE": "CGI/1.1",
          "REMOTE_ADDR": "127.0.0.1",
          "SERVER_SOFTWARE": "Zope/(2.13.28, python 2.7.12, linux2) ZServer/1.1",
          "SCRIPT_NAME": "",
          "REQUEST_METHOD": "GET",
          "HTTP_HOST": "localhost:8086",
          "PATH_INFO": "/senaite/queue_consumer",
          "SERVER_PORT": "8086",
          "SERVER_PROTOCOL": "HTTP/1.1",
          "channel.creation_time": 1573034830,
          "HTTP_ACCEPT_ENCODING": "gzip, deflate",
          "PATH_TRANSLATED": "/senaite/queue_consumer"
        },
        "HTTP_REFERER": "",
        "REMOTE_ADDR": "127.0.0.1",
        "AUTHENTICATED_USER": "patsikaz",
        "X_FORWARDED_FOR": ""
      },
      "name": "task_action_verify"
    },
    "processed": null,
    "container": "/senaite/bika_setup",
    "speed": 2,
    "id": "senaite.queue.main.storage"
    }


Non-empty queue
---------------

When the queue is not empty, you will see the list of tasks to be processed
inside `tasks` attribute:


.. code-block:: json

    {
    "tasks": [{
      "context_uid": "9188a07b15be428d83c7a9f615dc8e28",
      "request": {
        "HTTP_USER_AGENT": "python-requests/2.18.4",
        "X_REAL_IP": "",
        "_orig_env": {
          "CONNECTION_TYPE": "keep-alive",
          "HTTP_ACCEPT": "*/*",
          "HTTP_USER_AGENT": "python-requests/2.18.4",
          "SERVER_NAME": "localhost",
          "GATEWAY_INTERFACE": "CGI/1.1",
          "REMOTE_ADDR": "127.0.0.1",
          "SERVER_SOFTWARE": "Zope/(2.13.28, python 2.7.12, linux2) ZServer/1.1",
          "SCRIPT_NAME": "",
          "REQUEST_METHOD": "GET",
          "HTTP_HOST": "localhost:8086",
          "PATH_INFO": "/senaite/queue_consumer",
          "SERVER_PORT": "8086",
          "SERVER_PROTOCOL": "HTTP/1.1",
          "channel.creation_time": 1573034910,
          "HTTP_ACCEPT_ENCODING": "gzip, deflate",
          "PATH_TRANSLATED": "/senaite/queue_consumer"
        },
        "HTTP_REFERER": "",
        "REMOTE_ADDR": "127.0.0.1",
        "AUTHENTICATED_USER": "patsikaz",
        "X_FORWARDED_FOR": ""
      },
      "name": "task_action_verify"
    }],
    "locked": null,
    "current": null,
    "processed": {},
    "container": "/senaite/bika_setup",
    "speed": -1,
    "id": "senaite.queue.main.storage"
    }


Contribute
==========

We want contributing to SENAITE.STORAGE to be fun, enjoyable, and educational
for anyone, and everyone. This project adheres to the `Contributor Covenant
<https://github.com/senaite/senaite.queue/blob/master/CODE_OF_CONDUCT.md>`_.

By participating, you are expected to uphold this code. Please report
unacceptable behavior.

Contributions go far beyond pull requests and commits. Although we love giving
you the opportunity to put your stamp on SENAITE.STORAGE, we also are thrilled
to receive a variety of other contributions.

Please, read `Contributing to senaite.queue document
<https://github.com/senaite/senaite.queue/blob/master/CONTRIBUTING.md>`_.

If you wish to contribute with translations, check the project site on
`Transifex <https://www.transifex.com/senaite/senaite-queue/>`_.


Feedback and support
====================

* `Community site <https://community.senaite.org/>`_
* `Gitter channel <https://gitter.im/senaite/Lobby>`_
* `Users list <https://sourceforge.net/projects/senaite/lists/senaite-users>`_


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
