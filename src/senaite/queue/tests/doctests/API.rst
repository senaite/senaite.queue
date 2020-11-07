Queue API
---------

`senaite.queue` comes with an api to facilitate the interaction with queue.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t API

Test Setup
~~~~~~~~~~

Needed imports:

    >>> import transaction
    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from senaite.queue import api
    >>> from senaite.queue.queue import QueueTask
    >>> from senaite.queue.tests import utils as test_utils
    >>> from bika.lims import api as _api
    >>> from plone import api as plone_api
    >>> from zope import globalrequest

Functional Helpers:

    >>> def new_sample():
    ...     return test_utils.create_sample([Cu], client, contact,
    ...                                     sampletype, receive=False)

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


Retrieve the Queue Utility
~~~~~~~~~~~~~~~~~~~~~~~~~~

The queue utility is the engine from `senaite.queue` that is responsible of
providing access to the queue storage. Unless the current zeo client is
configured to act as the queue's server, ``api.get_queue()`` always returns the
client queue utility:

    >>> api.get_queue()
    <senaite.queue.client.utility.ClientQueueUtility object at...

If we configure the current zeo client as the server, we get the server queue
utility instead:

    >>> api.is_queue_server()
    False

    >>> api.get_server_url()
    'http://localhost:8080/senaite'

    >>> key = "senaite.queue.server"
    >>> plone_api.portal.set_registry_record(key, u'http://nohost/plone')
    >>> transaction.commit()
    >>> api.get_queue()
    <senaite.queue.server.utility.ServerQueueUtility object at...

    >>> api.is_queue_server()
    True

    >>> api.get_server_url()
    'http://nohost/plone'

Both utility queues provide same interface and same behavior is expected,
regardless of the type of ``QueueUtility``. See ``ClientQueueUtility.rst`` and
``ServerQueueUtility.rst`` doctests for additional information.


Queue status
~~~~~~~~~~~~

We can check the queue status:

    >>> api.get_queue_status()
    'ready'

We can even use the helper ``is_queue_ready``:

    >>> api.is_queue_ready()
    True

Queue might be enabled, but not ready:

    >>> api.is_queue_enabled()
    True


Enable/Disable queue
~~~~~~~~~~~~~~~~~~~~

The queue can be disabled and enabled from Site Setup > Queue Settings:

    >>> key = "senaite.queue.default"
    >>> plone_api.portal.set_registry_record(key, 0)
    >>> api.is_queue_enabled()
    False

    >>> api.is_queue_ready()
    False

    >>> api.get_queue_status()
    'disabled'

We can re-enable the queue by defining the default's chunk size:

    >>> plone_api.portal.set_registry_record(key, 10)
    >>> api.is_queue_enabled()
    True

    >>> api.is_queue_ready()
    True

    >>> api.get_queue_status()
    'ready'


Add a task
~~~~~~~~~~

We can add a task without the need of retrieving the queue utility or without
the need of creating a ``QueueTask`` object:

    >>> sample = new_sample()
    >>> kwargs = {"action": "receive"}
    >>> task = api.add_task("task_action_receive", sample)
    >>> isinstance(task, QueueTask)
    True

    >>> api.get_queue().get_tasks()
    [{...}]

    >>> len(api.get_queue())
    1


Add an action task
~~~~~~~~~~~~~~~~~~

Tasks for workflow actions are quite common. Therefore, a specific function for
actions is also available:

    >>> task = api.add_action_task(sample, "submit")
    >>> isinstance(task, QueueTask)
    True

    >>> len(api.get_queue())
    2


Add assign action task
~~~~~~~~~~~~~~~~~~~~~~

The action "assign" (for analyses) requires not only the worksheet, but also the
list of analyses to be assigned and the slot positions as well. Therefore, a
helper function to make it easier is also available:

    >>> worksheet = _api.create(portal.worksheets, "Worksheet")
    >>> analyses = sample.getAnalyses(full_objects=True)
    >>> task = api.add_assign_task(worksheet, analyses)
    >>> isinstance(task, QueueTask)
    True

    >>> len(api.get_queue())
    3


Check if an object is queued
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    >>> new_sample = new_sample()
    >>> api.is_queued(new_sample)
    False

    >>> api.is_queued(sample)
    True

    >>> api.is_queued(worksheet)
    True


Flush the queue
~~~~~~~~~~~~~~~

Flush the queue to make room for other tests:

    >>> test_utils.flush_queue(browser, self.request)
