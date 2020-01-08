Queued task failure
===================

When a queued task fails, the system re-queues the task as many times as set
in the `max_retries` setting from the registry before considering the task
as failed.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t TaskFailure

Test Setup
----------

Needed imports:

    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from plone.app.testing import TEST_USER_PASSWORD
    >>> from senaite.queue import api
    >>> from senaite.queue.interfaces import IQueued
    >>> from senaite.queue.tests import utils as test_utils
    >>> from bika.lims.workflow import doActionFor
    >>> from zope.interface import alsoProvides
    >>> from zope.interface import noLongerProvides

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

Failure while assigning analyses to a Worksheet
-----------------------------------------------

Set the number of max retries on failure:

    >>> api.set_max_retries(3)

Set the number of analyses to be transitioned in a single queued task:

    >>> task_name = "task_assign_analyses"
    >>> api.set_chunk_size(task_name, 5)
    >>> api.get_chunk_size(task_name)
    5

Create 10 Samples with 1 analysis each and add the analyses to a worksheet:

    >>> samples = new_samples(10)
    >>> analyses = get_analyses_from(samples)
    >>> worksheet = api.create(portal.worksheets, "Worksheet")
    >>> worksheet.addAnalyses(analyses)

Only the first chunk of analyses has been transitioned non-async:

    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned)
    5

Remove one of the remaining analyses to be assigned:

    >>> non_transitioned = filter(lambda an: IQueued.providedBy(an), analyses)
    >>> black_sheep = non_transitioned[0]
    >>> black_sheep.aq_parent.manage_delObjects([black_sheep.getId()])

The system won't be able to process the task successfully:

    >>> "No object found for UID" in test_utils.dispatch()
    True
    >>> transitioned = test_utils.filter_by_state(analyses, "assigned")
    >>> len(transitioned) < 10
    True

And the task is re-queued automatically:

    >>> queue = test_utils.get_queue_tool()
    >>> task = queue.tasks[0]
    >>> task.retries
    1

If we retry, the number of retries increases:

    >>> "No object found for UID" in test_utils.dispatch()
    True
    >>> queue.tasks[0].retries
    2

Until we reach the maximum of retries:

    >>> "No object found for UID" in test_utils.dispatch()
    True
    >>> len(queue.tasks)
    1
    >>> queue.tasks[0].retries
    3
    >>> "No object found for UID" in test_utils.dispatch()
    True
    >>> len(queue.tasks)
    0

At this point, `IQueued` marker interface is no longer provided by Worksheet:

     >>> IQueued.providedBy(worksheet)
     False
