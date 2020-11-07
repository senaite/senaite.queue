Tasks handling
==============

SENAITE QUEUE keeps a prioritized queue that contains the tasks to be processed.
Each time the clock wakes-up (*clock-server* directive in *buildout*
configuration, see :doc:`installation`), the system checks if the queue is
currently locked by the tasks consumer. If locked, the system does nothing and
returns to a neutral state, awaiting for the undergoing task to finish. If the
queue is not locked, the consumer pops the next task from the queue. The
consumer then starts a new thread for processing the task.

As soon as the processing of the task finishes, the consumer notifies the Queue
so it can return to a neutral state and dispatch next task. This task is removed
from the queue.

If an error arises while processing the task, the consumer notifies the Queue
about the incident as well. This time, the queue resumes to neutral state, but
labels the task as "failed" and is not removed.

Prioritization
--------------

Two factors are taken into account for tasks prioritization: creation date time
and task custom priority value.

By default, system applies a priority value of 10 for all type of tasks. This
value can be changed for specific tasks though. The lesser the priority value,
the higher will be the priority of that task over others.

However, the creation date time is also used for tasks prioritization. So, even
if a task has a higher priority based on the priority value explained before,
tasks that were created long before this task will be prioritized. For this to
happen, the system calculates the task priority with this formula:

.. math::

    P = t + 300 * p

where:

* *P*: Priority of the task
* *t*: Number of seconds passed since epoch when the task was queued
* *p*: Priority value

For instance, given two tasks added to the queue with a difference of 5 minutes
(300 seconds), the first one with a *p* of 100 and the second with a *p* of 10:

.. math::

    P_0 = 1600003935 + 300 \times 100 = 1600033935

    P_1 = (1600003935 + 300) + 300 \times 10 = 1600037235

    P_0 < P_1

In this example, the task that was added first will be processed first, although
its priority value was greater than second's (remember the lesser the priority
value, the more priority).

This mechanism prevents the Queue to be jeopardized by high-priority tasks when
there is a lot of overload. Also, each time a new attempt for a failed task
takes place, the *created* value is updated accordingly. Thus, the mechanism
also acts as a safeguard for when a task takes long to complete and requires
several attempts to finish: it makes room for other tasks to be processed
instead of retrying the same task time again and again.


Failed tasks
------------

The Queue discards a task as "failed" because of any of the following reasons:

* The process did not complete because of transaction commit conflicts

* The process did not complete because of other errors

* The process reached the timeout defined in settings

By default, the Queue will try to re-process the failed tasks up to 3 times.
This value can be changed in :ref:`QueueControlPanel`. view: *Maximum retries*.
When a task is considered as failed, the Queue transitions from status "locked"
to "unlocked" and therefore, next task becomes available for consumption. If the
process does not succeed after maximum retries is reached, the task is discarded
as failed again, but no further retries will take place.

On each re-attempt, the queue sets a delay of 5 seconds, giving some time before
the task is re-processed. This mechanism reduces the chance of failures and also
makes room for other tasks to be processed before retries.

Also, the number of items to process for that precise task is reduced in a half.
This reduces the chance of both conflicts and timeouts.

When a process does not complete successfully, the thread in charge of handling
the task ends gracefully and the queue is immediately notified. This is the
safest case, cause there is no risk that more threads the CPU can handle are
started accidentally.

However, a process might take long to complete or maybe the zeo client was
stopped while a task was being processed. These are the two scenarios the last
reason refers to. In such cases, the Queue does not know if the task is actually
running or is not. Still, the Queue needs to resume because otherwise, no
further tasks will ever be processed: the queue would enter into a dead-lock
status. The Timeout mechanism (see next section) prevents this to happen.


Timeout
-------

When system retries a task, it will increase the timeout for that specific task.
Timeout is the time in seconds the Queue will wait for the task to complete
before being discarded as failed. By default, this value is set to 120 seconds,
but can be changed in :ref:`QueueControlPanel`: *Maximum seconds*.

Given a value of timeout of 120 seconds, if a task fails the first time, the
system will increase the timeout for that task to 180 seconds. If it fails a
second time, it will increase its timeout to 270 seconds: the system multiplies
the seconds by a factor of 1.5 each time.

.. note:: Note that if *Maximum retries* is set to 5 and the timeout is 120
          seconds, the time in seconds the Queue will wait for the task to
          complete in the last attempt will be 608 seconds (10 minutes).
          Take this into account when configuring default values for
          *Maximum seconds* and *Maximum retries*.


Transaction commit conflicts
----------------------------

When a database transaction commit conflict takes place, the system retries the
same transaction up to 3 times as per Zope's default. However, if the last
transaction attempt cannot be completed, the Queue re-queues the task for
further attempts, up to the value defined in :ref:`QueueControlPanel`:
*Maximum retries*.
