Unassign transition
-------------------

SENAITE Queue comes with an adapter for generic actions (e.g. submit, unassign).
Generic actions don't require additional logic other than transitioning and this
is handled by DC workflow. Thus, the adapter for generic actions provided by
`senaite.queue` only deal with the number of chunks to process per task, with
no additional logic. Most transitions from `senaite.core` match with these
requirements.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t WorksheetAnalysesUnassign


Test Setup
~~~~~~~~~~

Needed imports:

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
    ...     transaction.commit()
    ...     return worksheet

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
    >>> api.get_queue()
    <senaite.queue.server.utility.ServerQueueUtility object at...


Unassign transition
~~~~~~~~~~~~~~~~~~~

Disable the queue first, so `assign` transitions is performed non-async:

    >>> chunk_key = "senaite.queue.default"
    >>> plone_api.portal.set_registry_record(chunk_key, 0)
    >>> transaction.commit()

Create a worksheet with some analyses:

    >>> worksheet = new_worksheet(15)
    >>> analyses = worksheet.getAnalyses()

Enable the queue so we can trap the `unassign` transition:

    >>> plone_api.portal.set_registry_record(chunk_key, 5)
    >>> transaction.commit()

Unassign analyses:

    >>> test_utils.handle_action(worksheet, analyses, "unassign")

The worksheet is queued and the analyses as well:

    >>> api.is_queued(worksheet)
    True

    >>> len(test_utils.filter_by_state(analyses, "unassigned"))
    0

    >>> all(map(api.is_queued, analyses))
    True

And the queue contains one task:

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

    >>> transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(transitioned)
    5

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
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

    >>> transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(transitioned)
    10

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
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

    >>> transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(transitioned)
    15

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
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


Unassign transition (with ClientQueue)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Perform same test as before, but now using the `ClientQueueUtility`:

    >>> queue = test_utils.get_client_queue(browser, self.request)

Disable the queue first, so `submit` and `assign` transitions are performed
non-async:

    >>> chunk_key = "senaite.queue.default"
    >>> plone_api.portal.set_registry_record(chunk_key, 0)
    >>> transaction.commit()

Create a worksheet with some analyses:

    >>> worksheet = new_worksheet(15)
    >>> analyses = worksheet.getAnalyses()

Enable the queue so we can trap the `unassign` transition:

    >>> plone_api.portal.set_registry_record(chunk_key, 5)
    >>> transaction.commit()

Unassign the analyses:

    >>> test_utils.handle_action(worksheet, analyses, "unassign")

The queue contains one task:

    >>> queue.sync()
    >>> queue.is_empty()
    False

    >>> len(queue)
    1

    >>> len(queue.get_tasks_for(worksheet))
    1

    >>> all(filter(queue.get_tasks_for, analyses))
    True

Pop a task and process:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

The first chunk of analyses has been processed:

    >>> transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(transitioned)
    5

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(non_transitioned)
    10

    >>> queue.sync()
    >>> any(map(queue.has_tasks_for, transitioned))
    False

    >>> all(map(queue.has_tasks_for, non_transitioned))
    True

    >>> queue.has_tasks_for(worksheet)
    True

Pop and process again:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

Next chunk of analyses has been processed:

    >>> transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(transitioned)
    10

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(non_transitioned)
    5

    >>> queue.sync()
    >>> any(map(queue.has_tasks_for, transitioned))
    False

    >>> all(map(queue.has_tasks_for, non_transitioned))
    True

    >>> queue.has_tasks_for(worksheet)
    True

Pop and process again:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

Last chunk of analyses is processed:

    >>> transitioned = test_utils.filter_by_state(analyses, "unassigned")
    >>> len(transitioned)
    15

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(non_transitioned)
    0

    >>> queue.sync()
    >>> any(map(queue.has_tasks_for, transitioned))
    False

    >>> queue.is_empty()
    True

    >>> queue.has_tasks_for(worksheet)
    False
