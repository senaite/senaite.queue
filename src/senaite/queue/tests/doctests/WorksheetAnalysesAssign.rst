Assignment of analyses
----------------------

SENAITE Queue supports the `assign` transition for analyses, either for when
the analyses are assigned manually (via `Add analyses` view from Worksheet) or
when using a Worksheet Template.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t WorksheetAnalysesAssign

Test Setup
~~~~~~~~~~

Needed imports:

    >>> from bika.lims import api as _api
    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from plone.app.testing import TEST_USER_PASSWORD
    >>> from senaite.queue import api
    >>> from senaite.queue.tests import utils as test_utils

Functional Helpers:

    >>> def new_samples(num_analyses):
    ...     samples = []
    ...     for num in range(num_analyses):
    ...         sample = test_utils.create_sample([Cu], client, contact,
    ...                                           sampletype, receive=True)
    ...         samples.append(sample)
    ...     return samples

    >>> def get_analyses_from(samples):
    ...     analyses = []
    ...     for sample in samples:
    ...         analyses.extend(sample.getAnalyses(full_objects=True))
    ...     return analyses

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

Make the test a bit faster by reducing the min_seconds:

    >>> test_utils.set_min_seconds(1)

Manual assignment of analyses to a Worksheet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set the number of analyses to be transitioned in a single queued task:

    >>> task_name = "task_assign_analyses"
    >>> api.set_chunk_size(task_name, 5)
    >>> api.get_chunk_size(task_name)
    5

Create 15 Samples with 1 analysis each:

    >>> samples = new_samples(15)
    >>> analyses = get_analyses_from(samples)

Create an empty worksheet and add all analyses:

    >>> worksheet = _api.create(portal.worksheets, "Worksheet")
    >>> worksheet.addAnalyses(analyses)

The worksheet is queued now:

    >>> api.is_queued(worksheet)
    True

And the analyses as well:

    >>> queued = map(api.is_queued, analyses)
    >>> all(queued)
    True

None of the analyses have been transitioned:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    0

The queue contains one task:

    >>> queue = test_utils.get_queue_tool()
    >>> queue.is_empty()
    False
    >>> len(queue)
    1
    >>> tasks = queue.get_tasks_for(worksheet)
    >>> len(list(tasks))
    1

We manually trigger the queue dispatcher:

    >>> test_utils.dispatch()
    "Task 'task_assign_analyses' for ... processed"

The first chunk of analyses has been processed:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    5
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    10
    >>> any(map(api.is_queued, transitioned))
    False
    >>> all(map(api.is_queued, non_transitioned))
    True

And the worksheet is still queued:

    >>> api.is_queued(worksheet)
    True

Change the number of items to process per task to 2:

    >>> api.set_chunk_size(task_name, 2)
    >>> api.get_chunk_size(task_name)
    2

And dispatch again:

    >>> test_utils.dispatch()
    "Task 'task_assign_analyses' for ... processed"

Only 2 analyses are transitioned now:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    7
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    8
    >>> any(map(api.is_queued, transitioned))
    False
    >>> all(map(api.is_queued, non_transitioned))
    True
    >>> api.is_queued(worksheet)
    True

As we've seen, the queue for this task is enabled:

    >>> api.is_queue_active(task_name)
    True

But we can disable the queue for this task if we set the number of items to
process per task to 0:

    >>> api.disable_queue(task_name)
    >>> api.is_queue_active(task_name)
    False
    >>> api.get_chunk_size(task_name)
    0

But still, if we manually trigger the dispatch with the queue being disabled,
the action will take place. Thus, disabling the queue only prevents the system
to add new tasks to the queue, but won't have any effect to those that remain in
the queue. Rather, it will transition all remaining analyses at once:

    >>> test_utils.dispatch()
    "Task 'task_assign_analyses' for ... processed"
    >>> queue.is_empty()
    True
    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    15
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    0
    >>> any(map(api.is_queued, transitioned))
    False
    >>> api.is_queued(worksheet)
    False

Since all analyses have been processed, the worksheet is no longer queued:

    >>> api.is_queued(worksheet)
    False

Assignment of analyses through Worksheet Template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Analyses can be assigned to a worksheet by making use of a Worksheet Template.
In such case, the system must behave exactly the same way as before.

Set the number of analyses to be transitioned in a single queued task:

    >>> task_name = "task_assign_analyses"
    >>> api.set_chunk_size(task_name, 5)
    >>> api.get_chunk_size(task_name)
    5

Create 20 Samples with 1 analysis each:

    >>> samples = new_samples(20)
    >>> analyses = get_analyses_from(samples)

Create a Worksheet Template with 20 slots reserved for `Cu` analysis:

    >>> template = _api.create(setup.bika_worksheettemplates, "WorksheetTemplate")
    >>> template.setService([Cu])
    >>> layout = map(lambda idx: {"pos": idx + 1, "type": "a"}, range(20))
    >>> template.setLayout(layout)

Use the template for Worksheet creation:

    >>> worksheet = _api.create(portal.worksheets, "Worksheet")
    >>> worksheet.applyWorksheetTemplate(template)

Five analyses (chunk size) have been assigned:

    >>> assigned = worksheet.getAnalyses()
    >>> len(assigned)
    5

    >>> list(set(map(_api.get_review_status, assigned)))
    ['assigned']

And none of these assigned analyses are queued:

    >>> any(map(api.is_queued, assigned))
    False

Remove these assigned analyses from the list:

    >>> analyses = filter(lambda a: a not in assigned, analyses)

The worksheet is now queued, as well as the not-yet assigned analyses:

    >>> api.is_queued(worksheet)
    True
    >>> all(map(api.is_queued, analyses))
    True

None of the analyses has been transitioned:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    0

And the queue is not empty:

    >>> queue = test_utils.get_queue_tool()
    >>> queue.is_empty()
    False

And contains a task:

    >>> len(queue)
    1
    >>> tasks = queue.get_tasks_for(worksheet)
    >>> len(list(tasks))
    1

We manually trigger the queue dispatcher:

    >>> test_utils.dispatch()
    "Task 'task_assign_analyses' for ... processed"

Only the first chunk of analyses has been transitioned non-async:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    5

And they are no longer queued:

    >>> any(map(api.is_queued, transitioned))
    False

While the rest of analyses remain queued:

    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    10
    >>> all(map(api.is_queued, non_transitioned))
    True

As the queue confirms:

    >>> queue.is_empty()
    False
    >>> len(queue)
    1
    >>> queue.has_tasks_for(worksheet)
    True

We manually trigger the queue dispatcher:

    >>> test_utils.dispatch()
    "Task 'task_assign_analyses' for ... processed"

Next chunk of analyses is processed:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    10
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    5
    >>> any(map(api.is_queued, transitioned))
    False
    >>> all(map(api.is_queued, non_transitioned))
    True

Since there are still 5 analyses remaining, the Worksheet is still queued:

    >>> api.is_queued(worksheet)
    True

We manually trigger the queue dispatcher:

    >>> test_utils.dispatch()
    "Task 'task_assign_analyses' for ... processed"

Last chunk of analyses is processed:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    15
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    0
    >>> any(map(api.is_queued, transitioned))
    False

The queue is now empty:

    >>> queue.is_empty()
    True

And the worksheet is no longer queued:

    >>> api.is_queued(worksheet)
    False
