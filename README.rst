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

Create a new user in senaite (under *senaite/acl_users*) with username
*queue_daemon* and password *queue_daemon*. It won't work when using acl
users registered in Zope's root (e.g. *admin*).

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
      period 5
      user ${buildout:queue-user-name}
      password ${buildout:queue-user-password}
      host localhost:8088
  </clock-server>


Configuration
=============

Some parameters of *senaite.queue* can be configured from SENAITE UI directly.
Login as admin user and visit "Site Setup". A link "Queue Settings" can be found
under "Add-on configuration". From this view you can either disable queue for
specific actions and configure the number of items to be processed by a single
queued task for a given action.

Queue is not able to process tasks fired by users from Zope's root (e.g. default 
*admin* user). *senaite.queue* will try to process them, but these tasks will be
discarded after some attempts (see "Maximum retries" configuration option from
Queue Control Panel). As a rule of thumb, always login with users registered in 
Senaite portal. Zope's root users must be used for maintenance tasks only.

Extend
======

To make a process to be run async by *senaite.queue*, add an adapter for that
specific process. Let's imagine you have a custom transition (e.g. *dispatch*)
in sample's workflow, that besides transitioning the sample, it also generates a
dispatch report. We want this transition to be handled asynchronously by
*senaite.queue*.

We need first to intercept the action *dispatch* and feed the queue by adding a
specific-adapter:

.. code-block:: xml

  <adapter
    name="workflow_action_dispatch"
    for="*
         zope.publisher.interfaces.browser.IBrowserRequest"
    factory=".analysisrequests.WorkflowActionDispatchAdapter"
    provides="bika.lims.interfaces.IWorkflowActionAdapter"
    permission="zope.Public" />

.. code-block:: python

  from bika.lims.browser.workflow import WorkflowActionGenericAdapter
  from senaite.queue.queue import queue_task

  DISPATCH_TASK_ID = "my.addon.task_dispatch"

  class WorkflowActionDispatchAdapter(WorkflowActionGenericAdapter):
      """Adapter that intercepts the action dispatch from samples listing and
      add the process into the queue
      """

      def do_action(self, action, objects):
          # Queue one task per object
          for obj in objects:
              queue_task(DISPATCH_TASK_ID, self.request, obj)
          return objects

Now, we only need to tell *senaite.queue* how to handle this task by adding
another adapter:

.. code-block:: xml

  <!-- My own adapter for dispatch action to be handled by senaite.queue -->
  <adapter
    name="my.addon.task_dispatch"
    factory=".QueuedDispatchTaskAdapter"
    provides="senaite.queue.interfaces.IQueuedTaskAdapter"
    for="bika.lims.interfaces.IAnalysisRequest" />

.. code-block:: python

  from senaite.core.interfaces import IAnalysisRequest
  from senaite.queue.adapters import QueuedTaskAdapter

  class QueuedDispatchTaskAdapter(QueuedTaskAdapter):
       """Adapter in charge dispatching a Sample
       """
       adapts(IAnalysisRequest)

       def process(self, task, request):
           sample = task.context

           # Your logic here for processing the sample
           # e.g transition the sample, generate the report, send email, etc.

           # Return whether the process finished successfully or not
           return succeed

This procedure can be used not only for transitions, but for any process you
might think of.

Since transitions are good candidates for queued tasks, *senaite.queue* provides
an easier mechanism to queue and process workflow actions. Instead of all the
above, you can easily bind a workflow action by reusing the adapters
*senaite.queue* already provides such scenarios. For instance, if you want the
action "dispatch" to be automatically handled by *senaite.queue* when user
clicks the button "Dispatch" from the bottom of generic Samples listing, you
only need to declare two adapters, as follows:

.. code-block:: xml

  <!-- Adapter that intercepts the action "dispatch" from listings and adds
  tasks for this action and selected objects to the queue -->
  <adapter
    name="workflow_action_dispatch"
    for="bika.lims.interfaces.IAnalysisRequests
         senaite.queue.interfaces.ISenaiteQueueLayer"
    factory="senaite.queue.adapters.WorkflowActionGenericQueueAdapter"
    provides="bika.lims.interfaces.IWorkflowActionAdapter"
    permission="zope.Public" />

  <!-- Adapter that processes the "dispatch" action for a queued task -->
  <adapter
    name="task_action_dispatch"
    factory="senaite.queue.adapters.QueuedActionTaskAdapter"
    provides="senaite.queue.interfaces.IQueuedTaskAdapter"
    for="bika.lims.interfaces.IAnalysisRequests" />


Screenshots
===========

Queued tasks
------------

.. image:: https://raw.githubusercontent.com/senaite/senaite.queue/master/static/queued_tasks.png
   :alt: Queued tasks
   :width: 760px
   :align: center

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

Contribute
==========

We want contributing to SENAITE.QUEUE to be fun, enjoyable, and educational
for anyone, and everyone. This project adheres to the `Contributor Covenant
<https://github.com/senaite/senaite.queue/blob/master/CODE_OF_CONDUCT.md>`_.

By participating, you are expected to uphold this code. Please report
unacceptable behavior.

Contributions go far beyond pull requests and commits. Although we love giving
you the opportunity to put your stamp on SENAITE.QUEUE, we also are thrilled
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

**SENAITE.QUEUE** Copyright (C) 2019-2020 RIDING BYTES & NARALABS

This program is free software; you can redistribute it and/or modify it under
the terms of the `GNU General Public License version 2
<https://github.com/senaite/senaite.queue/blob/master/LICENSE>`_ as published
by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
