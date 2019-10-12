Reject transition (analyses from worksheet)
===========================================

SENAITE Queue comes with an adapter for generic actions (e.g. submit, unassign).
Generic actions don't require additional logic other than transitioning and this
is handled by DC workflow. Thus, the adapter for generic actions provided by
`senaite.queue` only deal with the number of chunks to process per task, with
no additional logic. Most transitions from `senaite.core` match with these
requirements.

Running this test from the buildout directory::

    bin/test test_textual_doctests -t WorksheetAnalysesReject


Test Setup
----------

Needed imports:

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

    >>> def set_analyses_results(worksheet):
    ...     for analysis in worksheet.getAnalyses():
    ...         analysis.setResult(13)

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

    >>> api.disable_queue_for("task_assign_analyses")
    >>> api.is_queue_enabled("task_assign_analyses")
    False

And submit transition as well:

    >>> api.disable_queue_for("submit")
    >>> api.is_queue_enabled("submit")
    False


Retract transition
------------------

Set the number of analyses to be transitioned in a single queued task:

    >>> action = "reject"
    >>> api.set_chunk_size(action, 5)
    >>> api.get_chunk_size(action)
    5

Create a worksheet with some analyses, set a result and submit all them:

    >>> worksheet = new_worksheet(15)
    >>> analyses = worksheet.getAnalyses()
    >>> set_analyses_results(worksheet)
    >>> test_utils.handle_action(worksheet, analyses, "submit")

Retract the results:

    >>> test_utils.handle_action(worksheet, analyses, action)

The worksheet provides now the interface `IQueued`:

    >>> IQueued.providedBy(worksheet)
    True

Only the first chunk of analyses has been transitioned non-async:

    >>> transitioned = test_utils.filter_by_state(analyses, "rejected")
    >>> len(transitioned)
    5

And none of them provide the interface `IQueued`:

    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False

While the rest of analyses, not yet transitioned, do provide `IQueued`:

    >>> non_transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
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

    >>> transitioned = test_utils.filter_by_state(analyses, "rejected")
    >>> len(transitioned)
    10
    >>> non_transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
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

    >>> api.set_chunk_size(action, 2)
    >>> api.get_chunk_size(action)
    2

And dispatch again:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True

Now, only 2 analyses have been transitioned:

    >>> transitioned = test_utils.filter_by_state(analyses, "rejected")
    >>> len(transitioned)
    12
    >>> non_transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> len(non_transitioned)
    3
    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False
    >>> all(map(lambda an: IQueued.providedBy(an), non_transitioned))
    True
    >>> IQueued.providedBy(worksheet)
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

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True
    >>> queue.is_empty()
    True
    >>> transitioned = test_utils.filter_by_state(analyses, "rejected")
    >>> len(transitioned)
    15
    >>> non_transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> len(non_transitioned)
    0
    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False

Since all analyses have been processed, the worksheet no longer provides the
`IQueue` marker interface:

    >>> IQueued.providedBy(worksheet)
    False
