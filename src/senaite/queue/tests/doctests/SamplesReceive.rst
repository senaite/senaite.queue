Receive Samples
---------------

SENAITE Queue supports the `receive` transition for samples selected from the
samples listing.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t SamplesReceive


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
    ...                                           sampletype, receive=False)
    ...         samples.append(sample)
    ...     transaction.commit()
    ...     return samples

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


Receive multiple samples at once
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create 15 Samples with 1 analysis each:

    >>> samples = new_samples(15)

The samples are in `sample_due` status:

    >>> len(test_utils.filter_by_state(samples, "sample_due"))
    15

Receive the samples (as if we selected them in Samples folder):

    >>> folder = _api.get_portal().analysisrequests
    >>> test_utils.handle_action(folder, samples, "receive")

None of the samples have been transitioned yet:

    >>> len(test_utils.filter_by_state(samples, "received"))
    0

The samples are now queued:

    >>> all(map(api.is_queued, samples))
    True

The queue contains one task:

    >>> queue = api.get_queue()
    >>> queue.is_empty()
    False

    >>> len(queue)
    1

    >>> len(queue.get_tasks_for(folder))
    1

Pop a task and process:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

The first chunk of samples has been processed:

    >>> len(test_utils.filter_by_state(samples, "sample_received"))
    10

    >>> len(test_utils.filter_by_state(samples, "sample_due"))
    5

Pop and process again:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

Remaining samples have been processed:

    >>> len(test_utils.filter_by_state(samples, "sample_received"))
    15

    >>> len(test_utils.filter_by_state(samples, "sample_due"))
    0

    >>> any(map(api.is_queued, samples))
    False

And the queue is now empty:

    >>> queue.is_empty()
    True


Receive multiple samples while adding more
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The "receive" action for Samples triggered from the samples listing is not
treated as "unique" by the queue, so even if the system contains samples in
the queue for reception already, the queue will keep accepting more tasks of
this type.

Create 5 Samples with 1 analysis each and receive them:

    >>> folder = _api.get_portal().analysisrequests
    >>> samples = new_samples(5)
    >>> test_utils.handle_action(folder, samples, "receive")

The queue contains one task for the samples folder context:

    >>> queue = api.get_queue()
    >>> len(queue.get_tasks_for(folder))
    1

Add 5 more Samples and receive them as well:

    >>> samples2 = new_samples(5)
    >>> test_utils.handle_action(folder, samples2, "receive")

The queue contains now two tasks for the samples folder context:

    >>> len(queue.get_tasks_for(folder))
    2

Pop a task and process:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

One set of samples has been processed:

    >>> all_samples = samples + samples2
    >>> len(test_utils.filter_by_state(all_samples, "sample_received"))
    5

    >>> len(queue.get_tasks_for(folder))
    1

Pop a task and process:

    >>> popped = queue.pop("http://nohost")
    >>> test_utils.process(browser, popped.task_uid)
    '{...Processed...}'

The rest of samples have been processed too:

    >>> len(test_utils.filter_by_state(all_samples, "sample_received"))
    10

And the queue is now empty:

    >>> queue = api.get_queue()
    >>> queue.is_empty()
    True
