Unassign transition (analyses from worksheet)
=============================================

SENAITE Queue comes with an adapter for generic actions (e.g. submit, unassign).
Generic actions don't require additional logic other than transitioning and this
is handled by DC workflow. Thus, the adapter for generic actions provided by
`senaite.queue` only deal with the number of chunks to process per task, with
no additional logic. Most transitions from `senaite.core` match with these
requirements.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t WorksheetAnalysesUnassign


Test Setup
----------

Needed imports:

    >>> from bika.lims import api as _api
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
    ...     worksheet = _api.create(portal.worksheets, "Worksheet")
    ...     worksheet.addAnalyses(analyses)
    ...     return worksheet

Variables:

    >>> portal = self.portal
    >>> request = self.request
    >>> setup = _api.get_setup()

Create some basic objects for the test:

    >>> setRoles(portal, TEST_USER_ID, ['Manager',])
    >>> client = _api.create(portal.clients, "Client", Name="Happy Hills", ClientID="HH", MemberDiscountApplies=True)
    >>> contact = _api.create(client, "Contact", Firstname="Rita", Lastname="Mohale")
    >>> sampletype = _api.create(setup.bika_sampletypes, "SampleType", title="Water", Prefix="W")
    >>> labcontact = _api.create(setup.bika_labcontacts, "LabContact", Firstname="Lab", Lastname="Manager")
    >>> department = _api.create(setup.bika_departments, "Department", title="Chemistry", Manager=labcontact)
    >>> category = _api.create(setup.bika_analysiscategories, "AnalysisCategory", title="Metals", Department=department)
    >>> Cu = _api.create(setup.bika_analysisservices, "AnalysisService", title="Copper", Keyword="Cu", Price="15", Category=category.UID(), Accredited=True)

Disable the queue for `task_assign_analyses` so we can create Worksheets to test
generic actions (`assign` action is not a generic one because involves handling
a worksheet, slot positions, etc.).

    >>> api.disable_queue_for("task_assign_analyses")
    >>> api.is_queue_enabled("task_assign_analyses")
    False


Unassign transition
-------------------

Set the number of analyses to be transitioned in a single queued task:

    >>> action = "unassign"
    >>> api.set_chunk_size(action, 5)
    >>> api.get_chunk_size(action)
    5

Create a worksheet with some analyses:

    >>> worksheet = new_worksheet(15)
    >>> analyses = worksheet.getAnalyses()

Unassign analyses:

    >>> test_utils.handle_action(worksheet, analyses, action)

The worksheet is now queued:

    >>> api.is_queued(worksheet)
    True

None of the analyses have been transitioned yet:

    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    0

And all them are queued:

    >>> all(map(api.is_queued, analyses))
    True

We manually trigger the queue dispatcher:

    >>> test_utils.dispatch()
    "Task 'task_action_unassign' for ... processed"

Only the first chunk of analyses has been transitioned non-async:

    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    5

And none of them are queued anymore:

    >>> any(map(api.is_queued, transitioned))
    False

While the rest of analyses, not yet transitioned, are still queued:

    >>> non_transitioned = filter(lambda an: an.getWorksheet(), analyses)
    >>> len(non_transitioned)
    10
    >>> all(map(api.is_queued, non_transitioned))
    True

As the queue confirms:

    >>> queue = test_utils.get_queue_tool()
    >>> len(queue)
    1

We manually trigger the queue dispatcher:

    >>> test_utils.dispatch()
    "Task 'task_action_unassign' for ... processed"

The next chunk of analyses has been processed and only those that have
transitioned are still queued:

    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    10
    >>> non_transitioned = filter(lambda an: an.getWorksheet(), analyses)
    >>> len(non_transitioned)
    5
    >>> any(map(api.is_queued, transitioned))
    False
    >>> all(map(api.is_queued, non_transitioned))
    True

Since there are still 5 analyses remaining, the Worksheet is still queued too:

    >>> api.is_queued(worksheet)
    True

Change the number of items to process per task to 2:

    >>> api.set_chunk_size(action, 2)
    >>> api.get_chunk_size(action)
    2

And dispatch again:

    >>> test_utils.dispatch()
    "Task 'task_action_unassign' for ... processed"

Now, only 2 analyses have been transitioned:

    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    12
    >>> non_transitioned = filter(lambda an: an.getWorksheet(), analyses)
    >>> len(non_transitioned)
    3
    >>> any(map(api.is_queued, transitioned))
    False
    >>> all(map(api.is_queued, non_transitioned))
    True
    >>> api.is_queued(worksheet)
    True

As we've seen, the queue for this task is enabled:

    >>> api.is_queue_enabled(action)
    True

But we can disable the queue for this task if we set the number of items to
process per task to 0:

    >>> api.disable_queue_for(action)
    >>> api.is_queue_enabled(action)
    False
    >>> api.get_chunk_size(action)
    0

But still, if we manually trigger the dispatch with the queue being disabled,
the action will take place. Thus, disabling the queue only prevents the system
to add new tasks to the queue, but won't have effect to those that remain in
the queue. Rather all remaining tasks will be processed in just one shot:

    >>> test_utils.dispatch()
    "Task 'task_action_unassign' for ... processed"
    >>> queue.is_empty()
    True
    >>> transitioned = filter(lambda an: not an.getWorksheet(), analyses)
    >>> len(transitioned)
    15
    >>> non_transitioned = filter(lambda an: an.getWorksheet(), analyses)
    >>> len(non_transitioned)
    0
    >>> any(map(api.is_queued, transitioned))
    False

Since all analyses have been processed, the worksheet is no longer queued:

    >>> api.is_queued(worksheet)
    False
