Client's Queue utility
----------------------

The ``IClientQueueUtility`` is an utility that acts as a singleton and is used
as an interface to interact with the Server's queue. It provides functions to
add tasks to the queue and retrieve them.

This utility is used by the instances that either act as queue clients or
consumers. The zeo instance that acts as the queue server uses
``IServerQueueUtility`` instead. ``IClientQueueUtility`` has a cache of tasks
that keeps up-to-date with those from server's queue through POST calls.

However, both utilities provide same interface, so developer does not need to
worry about which utility is actually using: except for some particular cases
involving `failed` and `ghost` tasks, their expected behaviour is exactly the
same.

Running this test from the buildout directory:

    bin/test test_textual_doctests -t ClientQueueUtility

Test Setup
~~~~~~~~~~

Needed imports:

    >>> import binascii
    >>> import os
    >>> import time
    >>> import transaction
    >>> from bika.lims import api as _api
    >>> from plone import api as plone_api
    >>> from plone.app.testing import setRoles
    >>> from plone.app.testing import TEST_USER_ID
    >>> from senaite.queue.interfaces import IQueueUtility
    >>> from senaite.queue.interfaces import IClientQueueUtility
    >>> from senaite.queue.interfaces import IServerQueueUtility
    >>> from senaite.queue.queue import new_task
    >>> from senaite.queue.tests import utils as test_utils
    >>> from senaite.queue.tests.utils import RequestTestHandler
    >>> from zope import globalrequest
    >>> from zope.component import getUtility

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
    >>> sample = new_sample()

Setup the current instance as the queue server too:

    >>> key = "senaite.queue.server"
    >>> host = u'http://nohost/plone'
    >>> plone_api.portal.set_registry_record(key, host)
    >>> transaction.commit()


Retrieve the client's queue utility
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The client queue utility provides all the functionalities required to manage the
the queue from the client side. This utility interacts internally with the queue
server via JSON API calls, but provides same interface. Therefore, the user
should expect the same behavior no matter if is using the client's queue or
the server's queue.

    >>> getUtility(IClientQueueUtility)
    <senaite.queue.client.utility.ClientQueueUtility object at...

Client utility implements ``IQueueUtility`` interface too:

    >>> utility = getUtility(IClientQueueUtility)
    >>> IQueueUtility.providedBy(utility)
    True

The utility makes use of ``requests`` module to ask the queue server. We
override the requests handler here for the doctests to mimic its behavior, but
using ``plone.testing.z2.Browser`` ( instead:

    >>> utility._req = RequestTestHandler(browser, self.request)

We we will also use the server's queue utility to validate integrity:

    >>> s_utility = getUtility(IServerQueueUtility)


Add a task
~~~~~~~~~~

The queue client does not have any task awaiting yet:

    >>> utility.is_empty()
    True

Add a task for a sample:

    >>> kwargs = {"action": "receive"}
    >>> task = new_task("task_action_receive", sample, **kwargs)

Add the new task:

    >>> utility.add(task) == task
    True

    >>> utility.is_empty()
    False

    >>> len(utility)
    1

The server queue contains the task as well:

    >>> len(s_utility)
    1

    >>> s_utility.has_task(task)
    True

Only tasks from ``QueueTask`` type are supported:

    >>> utility.add("dummy")
    Traceback (most recent call last):
    [...]
    ValueError: 'dummy' is not supported

Adding an existing task has no effect:

    >>> utility.add(task) is None
    True

    >>> len(utility)
    1

    >>> len(s_utility)
    1

However, we can add another task for same context and with same name:

    >>> kwargs = {"action": "receive", "test": "test"}
    >>> copy_task = new_task("task_action_receive", sample, **kwargs)
    >>> utility.add(copy_task) == copy_task
    True

    >>> len(utility)
    2

    >>> len(s_utility)
    2

But is not possible to add a new task for same context and task name when the
``unique`` wildcard is used:

    >>> kwargs = {"action": "receive", "unique": True}
    >>> unique_task = new_task("task_action_receive", sample, **kwargs)
    >>> utility.add(unique_task) is None
    True

    >>> len(utility)
    2

The server queue contains the two tasks as well:

    >>> len(s_utility)
    2

    >>> all(map(s_utility.has_task, utility.get_tasks()))
    True


Delete a task
~~~~~~~~~~~~~

We can delete a task directly:

    >>> utility.delete(copy_task)
    >>> len(utility)
    1

And the task gets removed from the server's queue as well:

    >>> len(s_utility)
    1

We can also delete a task by using the task uid:

    >>> added = utility.add(copy_task)
    >>> len(utility)
    2
    >>> len(s_utility)
    2

    >>> utility.delete(copy_task.task_uid)
    >>> len(utility)
    1
    >>> len(s_utility)
    1


Get a task
~~~~~~~~~~

We can retrieve the task we added before by it's uid:

    >>> retrieved_task = utility.get_task(task.task_uid)
    >>> retrieved_task == task
    True

If we ask for a task that does not exist, returns None:

    >>> dummy_uid = binascii.hexlify(os.urandom(16))
    >>> utility.get_task(dummy_uid) is None
    True

If we ask for something that is not a valid uid, we get an exception:

    >>> utility.get_task("dummy")
    Traceback (most recent call last):
    [...]
    ValueError: 'dummy' is not supported


Get tasks
~~~~~~~~~

Or we can get all the tasks the utility contains:

    >>> tasks = utility.get_tasks()
    >>> tasks
    [{...}]

    >>> task in tasks
    True

    >>> len(tasks)
    1


Get tasks by status
~~~~~~~~~~~~~~~~~~~

We can even get the tasks filtered by their status:

    >>> utility.get_tasks(status=["queued", "running"])
    [{...}]

    >>> utility.get_tasks(status="queued")
    [{...}]

    >>> utility.get_tasks(status="running")
    []


Get tasks by context
~~~~~~~~~~~~~~~~~~~~

Or we can get the task by context:

    >>> utility.get_tasks_for(sample)
    [{...}]

    >>> utility.get_tasks_for(_api.get_uid(sample))
    [{...}]

    >>> utility.get_tasks_for(task.task_uid)
    []

    >>> utility.get_tasks_for("dummy")
    Traceback (most recent call last):
    [...]
    ValueError: 'dummy' is not supported


Get tasks by context and task name
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    >>> utility.get_tasks_for(sample, name="task_action_receive")
    [{...}]

    >>> utility.get_tasks_for(sample, name="dummy")
    []


Get objects uids from tasks
~~~~~~~~~~~~~~~~~~~~~~~~~~~

We can also ask for all the uids from objects the utility contains:

    >>> uids = utility.get_uids()
    >>> len(uids)
    1

    >>> _api.get_uid(sample) in uids
    True

    >>> task.task_uid in uids
    False


Ask if a task exists
~~~~~~~~~~~~~~~~~~~~

    >>> utility.has_task(task)
    True

    >>> utility.has_task(task.task_uid)
    True

    >>> utility.has_task(_api.get_uid(sample))
    False

    >>> utility.has_task("dummy")
    Traceback (most recent call last):
    [...]
    ValueError: 'dummy' is not supported


Ask if a task for a context exists
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    >>> utility.has_tasks_for(sample)
    True

    >>> utility.has_tasks_for(_api.get_uid(sample))
    True

    >>> utility.has_tasks_for(task.task_uid)
    False

    >>> utility.has_tasks_for("dummy")
    Traceback (most recent call last):
    [...]
    ValueError: 'dummy' is not supported


Ask if a task for a context and name exists
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    >>> utility.has_tasks_for(sample, name="task_action_receive")
    True

    >>> utility.has_tasks_for(sample, name="dummy")
    False


Synchronize with queue server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If we add a task directly to the server's queue:

    >>> kwargs = {"action": "receive"}
    >>> server_task = new_task("task_action_receive", sample, **kwargs)
    >>> s_utility.add(server_task) == server_task
    True
    >>> s_utility.has_task(server_task)
    True
    >>> len(s_utility)
    2

The task is not in client's queue local pool:

    >>> server_task in utility.get_tasks()
    False

However, the client queue falls back to a search against server's queue when
asked for an specific task that does not exist in the local pool:

    >>> utility.has_task(server_task)
    True

    >>> utility.get_task(server_task.task_uid)
    {...}

Client queue's local pool of tasks can be easily synchronized with the tasks
from the server's queue:

    >>> len(utility)
    1

    >>> utility.sync()
    >>> len(utility)
    2

    >>> server_task in utility.get_tasks()
    True

    >>> all(map(s_utility.has_task, utility.get_tasks()))
    True

When the task status in the server is "running", the corresponding task of the
local pool is always updated on synchronization:

    >>> consumer_id = u'http://nohost'
    >>> running = s_utility.pop(consumer_id)
    >>> running.status
    'running'

    >>> local_task = utility.get_task(running.task_uid)
    >>> local_task.status
    'queued'

    >>> utility.sync()
    >>> local_task = utility.get_task(running.task_uid)
    >>> local_task.status
    'running'

Flush the queue:

    >>> deleted = map(utility.delete, utility.get_tasks())
    >>> len(utility)
    0
    >>> len(s_utility)
    0


Pop a task
~~~~~~~~~~

Add a new task to the queue:

    >>> kwargs = {"action": "receive"}
    >>> task = new_task("task_action_receive", sample, **kwargs)
    >>> utility.add(task) == task
    True

When a task is popped, the utility changes the status of the task to "running",
cause expects that the task has been popped for consumption:

    >>> consumer_id = u'http://nohost'
    >>> popped = utility.pop(consumer_id)
    >>> popped.status
    'running'

We can still add new tasks at the same time, even if they are for same context
and with same name:

    >>> kwargs = {"action": "receive"}
    >>> copy_task = new_task("task_action_receive", sample, **kwargs)
    >>> utility.add(copy_task) == copy_task
    True

However, is not allowed to consume more more tasks unless the queue server
receives an acknowledgment that the previously popped task is done:

    >>> utility.pop(consumer_id) is None
    True

Even if we ask again:

    >>> utility.pop(consumer_id) is None
    True

Unless we wait for 10 seconds, when the server assumes the consumer failed while
processing the task. Consumers always check that there is no thread running
from their side before doing a ``pop()``. Also, a consumer (that in fact, is a
zeo client) might be stopped at some point. Therefore, this timeout mechanism
is used as a safety fallback to prevent the queue to enter in a dead-lock:

    >>> time.sleep(11)
    >>> utility.pop(consumer_id) is None
    True

The previous task is now re-queued:

    >>> popped = utility.get_task(popped.task_uid)
    >>> popped.status
    'queued'

    >>> popped.get("error_message")
    'Purged on pop (http://nohost)'

And a ``pop`` returns now the next task:

    >>> next_task = utility.pop(consumer_id)
    >>> next_task.status
    'running'

    >>> next_task.task_uid != popped.task_uid
    True

Delete the newly added task, so we keep only one task in the queue for testing:

    >>> utility.delete(next_task)
    >>> len(utility)
    1

If we try now to ``pop`` again, the task the queue server considered as timeout
won't be popped because the server adds a delay of 5 seconds before the task
can be popped again. This mechanism prevents the queue to be jeopardized by
recurrent failing tasks and makes room for other tasks to be processed:

    >>> popped.get("delay")
    5

    >>> utility.pop(consumer_id) is None
    True

    >>> time.sleep(5)
    >>> delayed = utility.pop(consumer_id)
    >>> delayed.task_uid == popped.task_uid
    True

Flush the queue:

    >>> utility.delete(delayed)
    >>> len(utility)
    0


Task timeout
~~~~~~~~~~~~

Create a new task:

    >>> kwargs = {"action": "receive"}
    >>> task = new_task("task_action_receive", sample, **kwargs)
    >>> task = utility.add(task)

When a consumer thread in charge of processing a given task times out, it
notifies the queue accordingly so the task is re-queued:

    >>> running = utility.pop(consumer_id)
    >>> running.status
    'running'

    >>> utility.timeout(running)
    >>> queued = utility.get_task(running.task_uid)
    >>> queued.task_uid == running.task_uid
    True

    >>> queued.status
    'queued'

    >>> queued.get("error_message")
    'Timeout'

Each time a task is timed out, the number of seconds the system will wait for
the thread in charge of processing the task to complete increases. This
mechanism is used as a fall-back for when the processing of task takes longer
than initially expected:

    >>> queued.get("max_seconds") > running.get("max_seconds")
    True

Flush the queue:

    >>> utility.delete(queued)
    >>> len(utility)
    0


Task failure
~~~~~~~~~~~~

Create a new task:

    >>> kwargs = {"action": "receive"}
    >>> task = new_task("task_action_receive", sample, **kwargs)
    >>> task = utility.add(task)

If an error arises when processing a task, the client queue tells the server to
mark the task as failed. By default, the queue server re-queues the task up
to a pre-defined number of times before considering the task as failed. The
most common reason why a task fails is because of a transaction commit conflict
with a transaction taken place from userland. This mechanism is used as a
safeguard for when the workload is high and tasks keep failing because of this.

Pop a task first:

    >>> running = utility.pop(consumer_id)
    >>> task_uid = running.task_uid
    >>> running.status
    'running'

    >>> running.retries
    3

Flag as failed and the number of retries decreases in one unit:

    >>> utility.fail(running)
    >>> failed = utility.get_task(running.task_uid)
    >>> failed.task_uid == running.task_uid
    True

    >>> failed.retries
    2
    >>> failed.status
    'queued'

When the number of retries reach 0, the server eventually considers the task
as failed, its status becomes `failed` and cannot be popped anymore:

    >>> time.sleep(5)
    >>> failed = utility.pop(consumer_id)
    >>> utility.fail(failed)
    >>> failed = utility.get_task(failed.task_uid)
    >>> failed.status
    'queued'
    >>> failed.retries
    1

    >>> time.sleep(5)
    >>> failed = utility.pop(consumer_id)
    >>> utility.fail(failed)
    >>> failed = utility.get_task(failed.task_uid)
    >>> failed.status
    'queued'
    >>> failed.retries
    0

    >>> time.sleep(5)
    >>> failed = utility.pop(consumer_id)
    >>> utility.fail(failed)
    >>> failed = utility.get_task(failed.task_uid)
    >>> failed.status
    'failed'
    >>> failed.retries
    0

    >>> time.sleep(5)
    >>> utility.pop(consumer_id) is None
    True

Flush the queue:

    >>> utility.delete(failed)
    >>> len(utility)
    0


Task done
~~~~~~~~~

When the client notifies a task has been done to the server queue, the task is
removed from the queue:

    >>> kwargs = {"action": "receive"}
    >>> task = new_task("task_action_receive", sample, **kwargs)
    >>> task = utility.add(task)
    >>> utility.has_task(task)
    True

    >>> running = utility.pop(consumer_id)
    >>> utility.has_task(running)
    True

    >>> utility.done(running)
    >>> utility.has_task(running)
    False


Flush the queue
~~~~~~~~~~~~~~~

Flush the queue to make room for other tests:

    >>> test_utils.flush_queue(browser, self.request)
