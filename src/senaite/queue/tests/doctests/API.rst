Queue API
---------

`senaite.queue` comes with an api to facilitate the interaction with the queue
of tasks.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t API

Test Setup
~~~~~~~~~~

Needed imports:

    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from senaite.queue import api
    >>> from senaite.queue.tests import utils as test_utils
    >>> from bika.lims import api as _api
    >>> from plone import api as plone_api

Functional Helpers:

    >>> def new_sample():
    ...     return test_utils.create_sample([Cu], client, contact,
    ...                                     sampletype, receive=False)

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

Queue a workflow action
~~~~~~~~~~~~~~~~~~~~~~~

We can queue workflow actions easily:

    >>> sample = new_sample()
    >>> task = api.queue_action(sample, "receive")
    >>> task
    {...}

    >>> task.get("action")
    'receive'

The task has been added to the queue:

    >>> api.is_queued(sample)
    True

    >>> api.get_queue().is_empty()
    False

    >>> queued_task = api.get_queue().get_task(task.task_uid)
    >>> queued_task == task
    True

And the sample won't be transitioned unless queue dispatcher is triggered:

    >>> _api.get_review_status(sample)
    'sample_due'

    >>> test_utils.dispatch()
    "Task 'task_generic_action' for ... processed"

    >>> _api.get_review_status(sample)
    'sample_received'

At this point, the sample is no longer queued:

    >>> api.is_queued(sample)
    False

And the queue is empty:

    >>> api.get_queue().is_empty()
    True


Queue a task
~~~~~~~~~~~~

We can queue a task directly, whether a workflow action or anything else:

    >>> sample = new_sample()
    >>> request = _api.get_request()
    >>> task_name = api.get_action_task_name("receive")
    >>> task = api.queue_task(task_name, request, sample)
    >>> task
    {...}

    >>> task.get("action")
    'receive'

The task has been added to the queue:

    >>> api.is_queued(sample)
    True

    >>> queued_task = api.get_queue().get_task(task.task_uid)
    >>> queued_task == task
    True

Queue a task without adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If we try to queue a task for which there is no adapter capable of handling
that specific process, an Exception is rised:

    >>> sample = new_sample()
    >>> request = _api.get_request()
    >>> api.queue_task("something", request, sample)
    Traceback (most recent call last):
    [...]
    ValueError: No IQueuedTaskAdapter found for task 'something' and context...


Enable/Disable queue
~~~~~~~~~~~~~~~~~~~~

By default, the queue is enabled:

    >>> api.is_queue_enabled()
    True

And for default supported actions as well:

    >>> actions = ["submit", "unassign", "reject", "retract", "verify", "task_assign_analyses"]
    >>> all(map(api.is_queue_enabled, actions))
    True

We can disable a queue for an specific action:

    >>> api.disable_queue("verify")
    >>> api.is_queue_enabled("verify")
    False

While keeping the queue for the rest of tasks enabled:

    >>> enabled_actions = filter(lambda a: a != "verify", actions)
    >>> all(map(api.is_queue_enabled, enabled_actions))
    True

And the whole queue as well:

    >>> api.is_queue_enabled()
    True

Disabling a queue for a given action, resets its chunk size to 0:

    >>> api.get_chunk_size("verify")
    0

We can re-enable the queue for that specific task:

    >>> api.enable_queue("verify")
    >>> api.is_queue_enabled("verify")
    True

And the chunk size for that specific task is now default's:

    >>> api.get_chunk_size("verify")
    10

If we change the default chunk size, the specific task will keep its own:

    >>> api.set_default_chunk_size(50)
    >>> api.get_chunk_size()
    50

    >>> api.get_chunk_size("verify")
    10

If we disable and re-enable the task for this task, the chunksize becomes
default though:

    >>> api.disable_queue("verify")
    >>> api.is_queue_enabled("verify")
    False

    >>> api.get_chunk_size("verify")
    0

    >>> api.enable_queue("verify")
    >>> api.is_queue_enabled("verify")
    True

    >>> api.get_chunk_size("verify")
    50

We can disable the whole queue too:

    >>> api.disable_queue()
    >>> api.is_queue_enabled()
    False

And the queue for all tasks becomes disabled too:

    >>> any(map(api.is_queue_enabled, actions))
    False

The default chunk size becomes 0, as well as task-specific chunk sizes:

    >>> api.get_chunk_size()
    0
    >>> list(set(map(api.get_chunk_size, actions)))
    [0]

If we re-enable the whole queue, the task-specific queue are also enabled:

    >>> api.enable_queue()
    >>> api.is_queue_enabled()
    True

    >>> all(map(api.is_queue_enabled, actions))
    True

And their chunk sizes are preserved:

    >>> api.get_chunk_size("verify")
    50


Minimum seconds per task
~~~~~~~~~~~~~~~~~~~~~~~~

If a given task is performed very rapidly, it will have priority over an eventual
transaction done from userland. In case of conflict, the transaction from userland
will fail because took more time to complete. The "Minimum seconds per task"
setting makes the thread that handles the task to take some time to complete,
thus preventing threads from userland to be delayed or fail:

    >>> api.get_min_seconds_task()
    3

We can change this value from control panel:

    >>> registry_id = api.resolve_queue_registry_record("min_seconds_task")
    >>> plone_api.portal.set_registry_record(registry_id, 10)
    >>> api.get_min_seconds_task()
    10

But values below 1 are not allowed:

    >>> plone_api.portal.set_registry_record(registry_id, 0)
    >>> api.get_min_seconds_task()
    1

    >>> plone_api.portal.set_registry_record(registry_id, -1)
    >>> api.get_min_seconds_task()
    1


Maximum seconds per task
~~~~~~~~~~~~~~~~~~~~~~~~

Maximum seconds per task defines the number of seconds the system will wait for
a running task to finish. If the number of seconds spend on the task is above
this setting, the system will transition the task to a failed status and the
queue won't be stuck anymore.

Queue has a setting by default:

    >>> api.get_max_seconds_task()
    120

But we can modify this setting through control panel:

    >>> registry_id = api.resolve_queue_registry_record("max_seconds_unlock")
    >>> plone_api.portal.set_registry_record(registry_id, 300)
    >>> api.get_max_seconds_task()
    300

But values below 30 are not allowed:

    >>> plone_api.portal.set_registry_record(registry_id, 29)
    >>> api.get_max_seconds_task()
    30

    >>> plone_api.portal.set_registry_record(registry_id, 1)
    >>> api.get_max_seconds_task()
    30

Number of retries
~~~~~~~~~~~~~~~~~

The number of retries establishes how many times a task must be automatically
retried on failure. If the number of retries is reached, the system transitions
the task to a failed status to give room for other tasks.


Queue has a setting by default:

    >>> api.get_max_retries()
    3

But we can modify this setting through control panel:

    >>> registry_id = api.resolve_queue_registry_record("max_retries")
    >>> plone_api.portal.set_registry_record(registry_id, 5)
    >>> api.get_max_retries()
    5

But values below 0 are not allowed:

    >>> plone_api.portal.set_registry_record(registry_id, -1)
    >>> api.get_max_retries()
    0
