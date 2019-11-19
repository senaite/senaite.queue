Assignment of analyses to a Worksheet
=====================================

SENAITE Queue supports the `assign` transition for analyses, either for when
the analyses are assigned manually (via `Add analyses` view from Worksheet) or
when using a Worksheet Template.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t WorksheetAnalysesAssign

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

Manual assignment of analyses to a Worksheet
--------------------------------------------

Set the number of analyses to be transitioned in a single queued task:

    >>> task_name = "task_assign_analyses"
    >>> api.set_chunk_size(task_name, 5)
    >>> api.get_chunk_size(task_name)
    5

Create 15 Samples with 1 analysis each:

    >>> samples = new_samples(15)
    >>> analyses = get_analyses_from(samples)

Create an empty worksheet and add all analyses:

    >>> worksheet = api.create(portal.worksheets, "Worksheet")
    >>> worksheet.addAnalyses(analyses)

The worksheet provides now the interface `IQueued`:

    >>> IQueued.providedBy(worksheet)
    True

Only the first chunk of analyses has been transitioned non-async:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    5

And none of them provide the interface `IQueued`:

    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False

While the rest of analyses, not yet transitioned, do provide `IQueued`:

    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
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

The next chunk of analyses has been processed and only those that have been
transitioned provide the interface `IQueued`:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    10
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
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

    >>> api.set_chunk_size(task_name, 2)
    >>> api.get_chunk_size(task_name)
    2

And dispatch again:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True

Now, only 2 analyses have been transitioned:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    12
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
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

    >>> api.disable_queue_for(task_name)
    >>> api.is_queue_enabled(task_name)
    False
    >>> api.get_chunk_size(task_name)
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
    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    15
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    0
    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False

Since all analyses have been processed, the worksheet no longer provides the
`IQueue` marker interface:

    >>> IQueued.providedBy(worksheet)
    False


Assignment of analyses through Worksheet Template
-------------------------------------------------

Analyses can be assigned to a worksheet by making use of a Worksheet Template.
In such case, the system must behave exactly the same way as before.

Set the number of analyses to be transitioned in a single queued task:

    >>> task_name = "task_assign_analyses"
    >>> api.set_chunk_size(task_name, 5)
    >>> api.get_chunk_size(task_name)
    5

Create 15 Samples with 1 analysis each:

    >>> samples = new_samples(15)
    >>> analyses = get_analyses_from(samples)

Create a Worksheet Template with 15 slots reserved for `Cu` analysis:

    >>> template = api.create(setup.bika_worksheettemplates, "WorksheetTemplate")
    >>> template.setService([Cu])
    >>> layout = map(lambda idx: {"pos": idx + 1, "type": "a"}, range(15))
    >>> template.setLayout(layout)

Use the template for Worksheet creation:

    >>> worksheet = api.create(portal.worksheets, "Worksheet")
    >>> worksheet.applyWorksheetTemplate(template)

The worksheet provides now the interface `IQueued`:

    >>> IQueued.providedBy(worksheet)
    True

Only the first chunk of analyses has been transitioned non-async:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    5

And none of them provide the interface `IQueued`:

    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False

While the rest of analyses, not yet transitioned, do provide `IQueued`:

    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    10
    >>> all(map(lambda an: IQueued.providedBy(an), non_transitioned))
    True

As the queue confirms:

    >>> queue = test_utils.get_queue_tool()
    >>> len(queue.tasks)
    1
    >>> queue.contains_tasks_for(worksheet)
    True

We manually trigger the queue dispatcher:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True

And now, the queue has processed a new task but is not yet empty:

    >>> queue.is_empty()
    False
    >>> queue.contains_tasks_for(worksheet)
    True

The next chunk of analyses has been processed and only those that have been
transitioned provide the interface `IQueued`:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    10
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
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

    >>> api.set_chunk_size(task_name, 2)
    >>> api.get_chunk_size(task_name)
    2

And dispatch again:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True

Now, only 2 analyses have been transitioned:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    12
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
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

    >>> api.disable_queue_for(task_name)
    >>> api.is_queue_enabled(task_name)
    False
    >>> api.get_chunk_size(task_name)
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
    >>> queue.contains_tasks_for(worksheet)
    False
    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    15
    >>> non_transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(non_transitioned)
    0
    >>> any(map(lambda an: IQueued.providedBy(an), transitioned))
    False

Since all analyses have been processed, the worksheet no longer provides the
`IQueue` marker interface:

    >>> IQueued.providedBy(worksheet)
    False
