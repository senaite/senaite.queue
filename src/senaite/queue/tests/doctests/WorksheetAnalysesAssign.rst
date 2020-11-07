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

    >>> import time
    >>> import transaction
    >>> from bika.lims import api as _api
    >>> from plone import api as plone_api
    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from plone.app.testing import TEST_USER_PASSWORD
    >>> from senaite.queue import api
    >>> from senaite.queue.tests import utils as test_utils
    >>> from zope import globalrequest

Functional Helpers:

    >>> def new_samples(num_analyses):
    ...     samples = []
    ...     for num in range(num_analyses):
    ...         sample = test_utils.create_sample([Cu], client, contact,
    ...                                           sampletype, receive=True)
    ...         samples.append(sample)
    ...     transaction.commit()
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
    >>> browser = self.getBrowser()
    >>> globalrequest.setRequest(request)
    >>> setRoles(portal, TEST_USER_ID, ["LabManager", "Manager"])
    >>> transaction.commit()

Create some basic objects for the test:

    >>> setRoles(portal, TEST_USER_ID, ['Manager',])
    >>> client = _api.create(portal.clients, "Client", Name="Happy Hills", ClientID="HH", MemberDiscountApplies=True)
    >>> contact = _api.create(client, "Contact", Firstname="Rita", Lastname="Mohale")
    >>> sampletype = _api.create(setup.bika_sampletypes, "SampleType", title="Water", Prefix="W")
    >>> labcontact = _api.create(setup.bika_labcontacts, "LabContact", Firstname="Lab", Lastname="Manager")
    >>> department = _api.create(setup.bika_departments, "Department", title="Chemistry", Manager=labcontact)
    >>> category = _api.create(setup.bika_analysiscategories, "AnalysisCategory", title="Metals", Department=department)
    >>> Cu = _api.create(setup.bika_analysisservices, "AnalysisService", title="Copper", Keyword="Cu", Price="15", Category=category.UID(), Accredited=True)

Setup the current instance as the queue server too:

    >>> key = "senaite.queue.server"
    >>> host = u'http://nohost/plone'
    >>> plone_api.portal.set_registry_record(key, host)
    >>> transaction.commit()


Manual assignment of analyses to a Worksheet
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set the default number of objects to process per task to 5:

    >>> chunk_key = "senaite.queue.default"
    >>> plone_api.portal.set_registry_record(chunk_key, 5)
    >>> transaction.commit()

Create 15 Samples with 1 analysis each:

    >>> samples = new_samples(15)
    >>> analyses = get_analyses_from(samples)

Create an empty worksheet and add all analyses:

    >>> worksheet = _api.create(portal.worksheets, "Worksheet")
    >>> worksheet.addAnalyses(analyses)
    >>> transaction.commit()

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

    >>> queue = api.get_queue()
    >>> queue.is_empty()
    False

    >>> len(queue)
    1

    >>> len(queue.get_tasks_for(worksheet))
    1

Pop a task and process:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

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

    >>> plone_api.portal.set_registry_record(chunk_key, 2)
    >>> transaction.commit()

Pop a task and process again:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

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

We can disable the queue. Set the number of items to process per task to 0:

    >>> plone_api.portal.set_registry_record(chunk_key, 0)
    >>> transaction.commit()

Because the queue contains tasks not yet processed, the queue remains enabled,
although is not ready:

    >>> api.is_queue_enabled()
    True

    >>> api.is_queue_ready()
    False

    >>> api.get_queue_status()
    'resuming'

Queue does not allow the addition of new tasks, but remaining tasks are
processed as usual but will transition all remaining analyses at once:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

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

Since all analyses have been processed, the worksheet is no longer queued and
the queue is now disabled:

    >>> api.is_queued(worksheet)
    False

    >>> api.is_queue_enabled()
    False

    >>> api.is_queue_ready()
    False

    >>> api.get_queue_status()
    'disabled'


Assignment of analyses through Worksheet Template
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Analyses can be assigned to a worksheet by making use of a Worksheet Template.
In such case, the system must behave exactly the same way as before.

Set the number of analyses to be transitioned in a single process:

    >>> chunk_key = "senaite.queue.default"
    >>> plone_api.portal.set_registry_record(chunk_key, 5)
    >>> transaction.commit()

Create 15 Samples with 1 analysis each:

    >>> samples = new_samples(15)
    >>> analyses = get_analyses_from(samples)

Create a Worksheet Template with 15 slots reserved for `Cu` analysis:

    >>> template = _api.create(setup.bika_worksheettemplates, "WorksheetTemplate")
    >>> template.setService([Cu])
    >>> layout = map(lambda idx: {"pos": idx + 1, "type": "a"}, range(15))
    >>> template.setLayout(layout)
    >>> transaction.commit()

Use the template for Worksheet creation:

    >>> worksheet = _api.create(portal.worksheets, "Worksheet")
    >>> worksheet.applyWorksheetTemplate(template)
    >>> transaction.commit()

The worksheet is now queued:

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

And the queue contains one task:

    >>> queue = api.get_queue()
    >>> queue.is_empty()
    False

    >>> len(queue)
    1

    >>> len(queue.get_tasks_for(worksheet))
    1

Wait for the task delay. This is a mechanism to prevent consumers to start
processing while the life-cycle of current request has not been finished yet:

    >>> task = queue.get_tasks_for(worksheet)[0]
    >>> time.sleep(task.get("delay", 0))

Pop a task and process:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

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

As the queue confirms:

    >>> queue.is_empty()
    False

    >>> len(queue)
    1

    >>> queue.has_tasks_for(worksheet)
    True

Pop and process again:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

Next chunk of analyses has been processed:

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

Pop and process again:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

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
