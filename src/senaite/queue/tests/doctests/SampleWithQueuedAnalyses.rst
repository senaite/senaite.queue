Sample with queued analyses
---------------------------

Samples that contain queued analyses cannot be transitioned until all analyses
it contains are successfully processed.

Running this test from buildout directory:

    bin/test test_textual_doctests -t SampleWithQueuedAnalyses


Test Setup
~~~~~~~~~~

Needed imports:

    >>> import transaction
    >>> from bika.lims import api as _api
    >>> from bika.lims.workflow import getAllowedTransitions
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

    >>> def set_analyses_results(worksheet):
    ...     for analysis in worksheet.getAnalyses():
    ...         analysis.setResult(13)
    ...     transaction.commit()

    >>> def samples_transitions_allowed(analyses):
    ...     samples = map(lambda an: an.getRequest(), analyses)
    ...     transitions = map(lambda samp: getAllowedTransitions(samp), samples)
    ...     transitions = map(lambda trans: any(trans), transitions)
    ...     return all(transitions)

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


Queued analyses
~~~~~~~~~~~~~~~


Disable the queue first, so `assign` transition is performed non-async:

    >>> chunk_key = "senaite.queue.default"
    >>> plone_api.portal.set_registry_record(chunk_key, 0)
    >>> transaction.commit()

Create a worksheet with some analyses and set results:

    >>> worksheet = new_worksheet(15)
    >>> analyses = worksheet.getAnalyses()
    >>> set_analyses_results(worksheet)

Enable the queue so we can trap the `submit` transition:

    >>> plone_api.portal.set_registry_record(chunk_key, 5)
    >>> transaction.commit()

Submit the analyses

    >>> test_utils.handle_action(worksheet, analyses, "submit")

No analyses have been transitioned. All them have been queued:

    >>> test_utils.filter_by_state(analyses, "to_be_verified")
    []

Pop a task and process:

    >>> queue = api.get_queue()
    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

Only the first chunk is transitioned and the samples they belong to can be
transitioned as well:

    >>> transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> samples_transitions_allowed(transitioned)
    True

While the rest cannot be transitioned, these analyses are still queued:

    >>> samples_transitions_allowed(analyses)
    False

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> samples_transitions_allowed(non_transitioned)
    False

Pop a task and process again:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

The next chunk of analyses has been processed and again, only the Samples for
those that have been transitioned can be transitioned too:

    >>> transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> samples_transitions_allowed(transitioned)
    True

While the rest of Samples (5) cannot be transitioned yet:

    >>> samples_transitions_allowed(analyses)
    False

    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> samples_transitions_allowed(non_transitioned)
    False

Pop a task and process:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

All analyses have been processed at this point, so all samples can be
transitioned now:

    >>> samples_transitions_allowed(analyses)
    True
