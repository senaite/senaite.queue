Submit transition (analyses from worksheet)
-------------------------------------------

SENAITE Queue comes with an adapter for generic actions (e.g. submit, unassign).
Generic actions don't require additional logic other than transitioning and this
is handled by DC workflow. Thus, the adapter for generic actions provided by
`senaite.queue` only deal with the number of chunks to process per task, with
no additional logic. Most transitions from `senaite.core` match with these
requirements.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t WorksheetAnalysesSubmit


Test Setup
~~~~~~~~~~

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

    >>> def set_analyses_results(worksheet):
    ...     for analysis in worksheet.getAnalyses():
    ...         analysis.setResult(13)

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


Submit transition
~~~~~~~~~~~~~~~~~

Set the number of analyses to be transitioned in a single queued task:

    >>> action = "submit"
    >>> api.set_chunk_size(action, 5)
    >>> api.get_chunk_size(action)
    5

Create a worksheet with some analyses:

    >>> worksheet = new_worksheet(15)

Select all analyses, set a result:

    >>> analyses = worksheet.getAnalyses()
    >>> set_analyses_results(worksheet)

Submit the analyses

    >>> test_utils.handle_action(worksheet, analyses, action)

The worksheet is now queued:

    >>> api.is_queued(worksheet)
    True

No analyses have been transitioned yet:

    >>> transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> len(transitioned)
    0
    >>> _api.get_review_status(worksheet)
    'open'

And all them are queued:

    >>> all(map(api.is_queued, analyses))
    True

We manually trigger the queue dispatcher:

    >>> test_utils.dispatch()
    "Task 'task_action_submit' for ... processed"

Only the first chunk of analyses has been transitioned non-async:

    >>> transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> len(transitioned)
    5

And none of them provide are queued anymore:

    >>> any(map(api.is_queued, transitioned))
    False

While the rest of analyses, not yet transitioned, are still queued:

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(non_transitioned)
    10
    >>> all(map(api.is_queued, non_transitioned))
    True

As the queue confirms:

    >>> queue = test_utils.get_queue_tool()
    >>> queue.is_empty()
    False

We trigger the queue dispatcher again:

    >>> test_utils.dispatch()
    "Task 'task_action_submit' for ... processed"

The next chunk of analyses has been processed:

    >>> transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> len(transitioned)
    10
    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(non_transitioned)
    5
    >>> any(map(api.is_queued, transitioned))
    False
    >>> all(map(api.is_queued, non_transitioned))
    True

Since there are still 5 analyses remaining, the Worksheet is queued:

    >>> api.is_queued(worksheet)
    True
    >>> _api.get_review_status(worksheet)
    'open'

Change the number of items to process per task to 2:

    >>> api.set_chunk_size(action, 2)
    >>> api.get_chunk_size(action)
    2

And dispatch again:

    >>> test_utils.dispatch()
    "Task 'task_action_submit' for ... processed"

Now, only 2 analyses have been transitioned:

    >>> transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> len(transitioned)
    12
    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
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
    "Task 'task_action_submit' for ... processed"
    >>> queue.is_empty()
    True
    >>> transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> len(transitioned)
    15
    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(non_transitioned)
    0
    >>> any(map(api.is_queued, transitioned))
    False

Since all analyses have been processed, the worksheet is no longer queued:

    >>> api.is_queued(worksheet)
    False

The worksheet has been transitioned:

    >>> _api.get_review_status(worksheet)
    'to_be_verified'

And all samples as well:

    >>> samples = map(lambda an: an.getRequest(), analyses)
    >>> statuses = map(lambda samp: _api.get_review_status(samp) == "to_be_verified", samples)
    >>> all(statuses)
    True
