Unassign transition (analyses from worksheet)
=============================================

SENAITE Queue comes with an adapter for generic actions (e.g. submit, unassign).
Generic actions don't require additional logic other than transitioning and this
is handled by DC workflow. Thus, the adapter for generic actions provided by
`senaite.queue` only deal with the number of chunks to process per task, with
no additional logic. Most transitions from `senaite.core` match with these
requirements.

Running this test from the buildout directory::

    bin/test test_textual_doctests -t WorksheetAnalysesUnassign


Test Setup
----------

Needed imports:

    >>> from bika.lims.workflow import doActionFor as do_action_for
    >>> from plone import api as ploneapi
    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from plone.app.testing import TEST_USER_PASSWORD
    >>> from senaite.queue import api
    >>> from senaite.queue.interfaces import IQueued
    >>> from senaite.queue.tests import utils as test_utils

Functional Helpers:

    >>> def new_sample(services):
    ...     return test_utils.create_sample(services, client, contact,
    ...                                     sampletype, receive=True)

    >>> def new_worksheet(num_analyses):
    ...     analyses = []
    ...     for num in range(num_analyses):
    ...         sample = new_sample([Cu])
    ...         analyses.extend(sample.getAnalyses(full_objects=True))
    ...     worksheet = api.create(portal.worksheets, "Worksheet")
    ...     worksheet.addAnalyses(analyses)
    ...     return worksheet

Variables:

    >>> portal = self.portal
    >>> request = self.request
    >>> setup = api.get_setup()

Create some basic objects for the test:

    >>> setRoles(portal, TEST_USER_ID, ['Manager',])
    >>> client = api.create(portal.clients, "Client", Name="Happy Hills", ClientID="HH", MemberDiscountApplies=True)
    >>> contact = api.create(client, "Contact", Firstname="Rita", Lastname="Mohale")
    >>> sampletype = api.create(setup.bika_sampletypes, "SampleType", title="Water", Prefix="W")
    >>> labcontact = api.create(setup.bika_labcontacts, "LabContact", Firstname="Lab", Lastname="Manager")
    >>> department = api.create(setup.bika_departments, "Department", title="Chemistry", Manager=labcontact)
    >>> category = api.create(setup.bika_analysiscategories, "AnalysisCategory", title="Metals", Department=department)
    >>> Cu = api.create(setup.bika_analysisservices, "AnalysisService", title="Copper", Keyword="Cu", Price="15", Category=category.UID(), Accredited=True)

Disable the queue for `task_assign_analyses` so we can create Worksheets to test
generic actions (`assign` action is not a generic one because involves handling
a worksheet, slot positions, etc.).

    >>> test_utils.set_registry_record("senaite.queue.task_assign_analyses", 0)
    >>> api.get_chunk_size("task_assign_analyses") == 0
    True


Unassign transition
-------------------

Set the variables:

    >>> action = "unassign"
    >>> task_name = api.get_action_task_name(action)
    >>> task_registry = "senaite.queue.{}".format(task_name)

Set the number of analyses to be transitioned in a single queued task:

    >>> test_utils.set_registry_record(task_registry, 5)
    >>> api.get_chunk_size(action) == 5
    True

Create a worksheet with some analyses:

    >>> worksheet = new_worksheet(15)

Select all analyses and transition them:

    >>> analyses = worksheet.getAnalyses()
    >>> test_utils.handle_action(worksheet, analyses, action)

The worksheet provides now the interface `IQueued`:

    >>> IQueued.providedBy(worksheet)
    True

Only the first chunk of analyses has been transitioned non-async:

    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    5

And none of them provide the interface `IQueued`:

    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False

While the rest of analyses, not yet transitioned, do provide `IQueued`:

    >>> non_transitioned = filter(lambda an: an.getWorksheet(), analyses)
    >>> len(non_transitioned)
    10
    >>> all(map(lambda an: IQueued.providedBy(an), non_transitioned))
    True

As the queue confirms:

    >>> queue = test_utils.get_queue_tool()
    >>> len(queue.tasks)
    1
    >>> queue.processed is None
    True

We manually trigger the queue dispatcher:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True

And now, the queue has processed a new task:

    >>> queue.processed is None
    False

But is not yet empty:

    >>> queue.is_empty()
    False

The next chunk of analyses has been processed and only those that have
transitioned provide the interface `IQueued`:

    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    10
    >>> non_transitioned = filter(lambda an: an.getWorksheet(), analyses)
    >>> len(non_transitioned)
    5
    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False
    >>> all(map(lambda an: IQueued.providedBy(an), non_transitioned))
    True

Since there are still 5 analyses remaining, the Worksheet provides `IQueued`:

    >>> IQueued.providedBy(worksheet)
    True

Change the number of items to process per task to 2:

    >>> test_utils.set_registry_record(task_registry, 2)
    >>> api.get_chunk_size(action) == 2
    True

And dispatch again:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True

Now, only 2 analyses have been transitioned:

    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    12
    >>> non_transitioned = filter(lambda an: an.getWorksheet(), analyses)
    >>> len(non_transitioned)
    3
    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False
    >>> all(map(lambda an: IQueued.providedBy(an), non_transitioned))
    True
    >>> IQueued.providedBy(worksheet)
    True

As we've seen, the queue for this task is enabled:

    >>> api.is_queue_enabled(task_name)
    True

But we can disable the queue for this task if we set the number of items to
process per task to 0:

    >>> test_utils.set_registry_record(task_registry, 0)
    >>> api.get_chunk_size(action) == 0
    True
    >>> api.is_queue_enabled(task_name)
    False

But still, if we manually trigger the dispatch with the queue being disabled,
the action will take place. Thus, disabling the queue only prevents the system
to add new tasks to the queue, but won't have effect to those that remain in
the queue. Rather all remaining tasks will be processed in just one shot:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True
    >>> queue.is_empty()
    True
    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    15
    >>> non_transitioned = filter(lambda an: an.getWorksheet(), analyses)
    >>> len(non_transitioned)
    0
    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False

Since all analyses have been processed, the worksheet no longer provides the
`IQueue` marker interface:

    >>> IQueued.providedBy(worksheet)
    False
