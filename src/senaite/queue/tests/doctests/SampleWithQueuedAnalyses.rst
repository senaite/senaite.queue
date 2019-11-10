Sample with queued analyses
===========================

Samples that contain queued analyses cannot be transitioned until all analyses
it contains are successfully processed.

Running this test from buildout directory::

    bin/test test_textual_doctests -t SampleWithQueuedAnalyses


Test Setup
----------

Needed imports:

    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from plone.app.testing import TEST_USER_PASSWORD
    >>> from senaite.queue import api
    >>> from senaite.queue.interfaces import IQueued
    >>> from senaite.queue.tests import utils as test_utils
    >>> from bika.lims.workflow import getAllowedTransitions

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

    >>> def samples_transitions_allowed(analyses):
    ...     samples = map(lambda an: an.getRequest(), analyses)
    ...     transitions = map(lambda samp: getAllowedTransitions(samp), samples)
    ...     transitions = map(lambda trans: any(trans), transitions)
    ...     return all(transitions)

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

Enable rejection workflow, so at least the transition "reject" can be performed
against a Sample in "received" status.

    >>> rejection_reasons = [{"checkbox": "on", "textfield-1": "Invalid"}]
    >>> setup.setRejectionReasons(rejection_reasons)


Queued analyses
---------------

Set the number of analyses to be transitioned in a single queued task:

    >>> action = "submit"
    >>> api.set_chunk_size(action, 5)
    >>> api.get_chunk_size(action)
    5

Create a worksheet with some analyses, and set a result:

    >>> worksheet = new_worksheet(15)
    >>> analyses = worksheet.getAnalyses()
    >>> set_analyses_results(worksheet)

All Samples to which the analyses belong to can be transitioned (rejected):

    >>> samples_transitions_allowed(analyses)
    True

Submit the analyses:

    >>> test_utils.handle_action(worksheet, analyses, "submit")

Only the first chunk is transitioned and the samples they belong to can be
transitioned as well:

    >>> transitioned = test_utils.filter_by_state(analyses, "to_be_verified")
    >>> samples_transitions_allowed(transitioned)
    True

While the rest provide `IQueued` interface and the Samples they belong to cannot
be transitioned at all:

    >>> samples_transitions_allowed(analyses)
    False
    >>> non_transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> samples_transitions_allowed(non_transitioned)
    False

We manually trigger the queue dispatcher:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True

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

Unless we manually trigger the queue dispatcher again:

    >>> response = test_utils.dispatch()
    >>> "processed" in response
    True

All analyses have been processed at this point, so all samples can be
transitioned now:

    >>> samples_transitions_allowed(analyses)
    True
