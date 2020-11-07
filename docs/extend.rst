Extend and Customize
====================

This package is built to be extended. You can use the `Zope Component
Architecture` to provide specific Adapters to both control how a task is
processed and to indicate which processes/logic needs to be executed
asynchronously by `senaite.queue`_. The process or logic to be handled by
`senaite.queue` can be from either `SENAITE LIMS`_ or from any other
`SENAITE`-specific add-on.


Queued task for a workflow action
---------------------------------

Let's imagine you have your own add-on with a custom transition/action (e.g.
*dispatch*) in sample's workflow, that transitions the sample to a *dispatched*
status. The user can choose multiple samples at once from the listing and
transition all them at once. This functionality might entail an undesired impact
on performance, specially if hundreds of samples are selected at once.

To address this functionality, we can extend `senaite.queue` in our own add-on.
We are not interested in replacing the logic behind such transition, but feed
the queue for this action. Therefore, we can make use of the generic adapter
`WorkflowGenericQueueAdapter` that comes by default with `senaite.queue` and
only do the registration in `configure.zcml`:

.. code-block:: xml

    <adapter
      name="workflow_action_dispatch"
      for="*
           zope.publisher.interfaces.browser.IBrowserRequest"
      factory="senaite.queue.actions.WorkflowActionGenericQueueAdapter"
      provides="bika.lims.interfaces.IWorkflowActionAdapter"
      permission="zope.Public" />


This is a named adapter, and the name must be the action id with
`workflow_action` prepended. When the workflow action `dispatch` is triggered,
the system looks for registered adapters and if a match is found, the adapter
is called. Note that `for` field is neither context-specific nor layer specific,
so this adapter will always be called when the action `dispatch` is triggered,
regardless of context and layer.

Alternatively, you can directly feed the queue programmatically:

.. code-block:: python

    from senaite.queue import api
    api.add_action_task(objects, action)


Parameter objects can be either a brain, an object, a uid or a list/tuple of any
of them.


Queued task for custom logic
----------------------------

Imagine that instead of having a workflow action "dispatch" in place, you rather
have a simple view from which the user can choose samples and generate a
dispatch pdf from all them at once. Basically you want to feed the queue
directly by your own:

.. code-block:: python

    class DispatchSamplesView(BrowserView):

        def __call__(self):
            ...

            # Get the selected samples from the form
            uids = self.request.form.get("selected_uids", [])

            # Queue the task
            params = {"uids": uids}
            api.add_task("my.addon.task_dispatch", self.context, **params)


Note the following:

* We use a "uids" field to store the list of objects to be processed
* We've set a custom task id `my.addon.task_dispatch`. This task id will be used
  by `senaite.queue` to look for a suitable adapter able to handle tasks with
  this id.

Create an adapter in charge of handling the task:

.. code-block:: python

    from bika.lims import api as _api
    from Products.Archetypes.interfaces.base import IBaseObject
    from senaite.queue import api
    from senaite.queue.queue import get_chunks_for
    from senaite.queue.interfaces import IQueuedTaskAdapter

    DISPATCH_TASK_ID = "my.addon.task_dispatch"

    class DispatchQueuedTaskAdapter(object):
        """Adapter for dispatch transition
        """
        implements(IQueuedTaskAdapter)
        adapts(IBaseObject)

        def __init__(self, context):
            self.context = context

        def process(self, task):
            """Process the objects from the task
            """
            # If there are too many objects to process, split them in chunks to
            # prevent the task to take too much time to complete
            chunks = get_chunks_for(task)

            # Process the first chunk
            objects = map(_api.get_object_by_uid, chunks[0])
            map(dispatch_sample, objects)

            # Add remaining objects to the queue
            params = {"uids": chunks[1]}
            api.add_task(DISPATCH_TASK_ID, self.context, **params)

        def dispatch_sample(self, sample):
            """Generates a dispatch report for this sample
            """
            # Generate the pdf here
            pdf = generate_dispatch_pdf(sample)

            # Store the pdf as an attachment to the sample
            att = _api.create(sample.aq_parent, "Attachment")
            att.setAttachmentFile(open(pdf))
            sample.setAttachment(att)

Register this adapter in `configure.zcml`:

.. code-block:: xml

    <adapter
      name="my.addon.task_dispatch"
      factory="my.addon.adapters.DispatchQueuedTaskAdapter"
      provides="senaite.queue.interfaces.IQueuedTaskAdapter"
      for="*" />

Note that this adapter is not only in charge of generating the dispatch pdfs,
but also splits the tasks into separate chunks preventing overload.

.. Links

.. _senaite.queue: https://pypi.python.org/pypi/senaite.queue
.. _SENAITE LIMS: https://www.senaite.com