# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.QUEUE.
#
# SENAITE.QUEUE is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2019-2020 by it's authors.
# Some rights reserved, see README and LICENSE.

import threading
import time

from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueueUtility
from senaite.queue.queue import QueueTask
from zope.interface import implements

from bika.lims import api as capi

# Maximum number of concurrent tasks to be processed at a time
MAX_CONCURRENT_TASKS = 1


class QueueStorage(object):
    """Storage that provides access to the tasks from a queue
    """

    _tasks = {}

    def get(self, key, default=None):
        return self._tasks.get(key, default)

    def set(self, key, value):
        self._tasks[key] = value

    @property
    def tasks(self):
        """The outstanding tasks from the queue
        """
        return self.get("tasks", default=[])[:]

    @property
    def running_tasks(self):
        """The ongoing tasks
        """
        return self.get("running_tasks", default=[])[:]

    @property
    def failed_tasks(self):
        """The ongoing tasks
        """
        return self.get("failed_tasks", default=[])[:]

    @tasks.setter
    def tasks(self, value):
        self.set("tasks", value)

    @running_tasks.setter
    def running_tasks(self, value):
        self.set("running_tasks", value)

    @failed_tasks.setter
    def failed_tasks(self, value):
        self.set("failed_tasks", value)


class QueueUtility(object):
    """General utility acting as a singleton that provides the basic actions to
    handle a queue of tasks
    """
    implements(IQueueUtility)

    _storage = None
    _senders = set()

    def __init__(self):
        self.__lock = threading.Lock()
        self._storage = QueueStorage()

    # TODO unique param not declared in the interface
    def add(self, task, unique=False):
        """Adds a task to the queue
        :param task: the QueueTask to add
        """
        with self.__lock:
            # Add the sender to the _senders pool
            self._senders.add(task.sender)
            return self._add(task, unique=unique)

    def pop(self, consumer_id):
        """Returns the next task to process, if any
        :param consumer_id: id of the consumer thread that will process the task
        :return: the task to be processed or None
        :rtype: queue.QueueTask
        """
        with self.__lock:
            tasks = self._storage.tasks
            if len(tasks) <= 0:
                return None

            # Maybe this consumer is processing a task already?
            running = filter(lambda t: t.get("consumer_id") == consumer_id,
                             self._storage.running_tasks)
            if running:
                return None

            # Pop the task with more priority
            task = tasks.pop()

            # Assign the tasks to the queue
            self._storage.tasks = tasks

            # Add the task to the running tasks
            task.update({
                "started": time.time(),
                "status": "running",
                "consumer_id": consumer_id,
            })
            running = self._storage.running_tasks
            running.append(task)
            self._storage.running_tasks = running

            # Return the task
            logger.info("Pop task {} ({}): {}"
                        .format(task.name, task.task_short_uid,
                                task.context_path))
            return task

    def done(self, task):
        """Notifies the queue that the task has been processed successfully
        :param task: task's unique id (task_uid) or QueueTask object
        """
        self.delete(task)

    def success(self, task):
        """Removes the task from the queue
        """
        # TODO REMOVE this function
        logger.warn("Use 'done' instead!")
        self.done(task)

    def fail(self, task, error_message=None):
        """Notifies the queue that the processing of the task failed. Removes
        the task from the running tasks. Is re-queued if there are remaining
        retries still. Otherwise, adds the task to the pool of failed
        :param task: task's unique id (task_uid) or QueueTask object
        :param error_message: (Optional) the error/traceback
        """
        with self.__lock:
            task_uid = api.get_task_uid(task)
            self._fail(task_uid, error_message=error_message)

    def delete(self, task):
        """Removes a task from the queue
        :param task: task's unique id (task_uid) or QueueTask object
        """
        with self.__lock:
            task_uid = api.get_task_uid(task)
            self._delete(task_uid)

    def get_task(self, task_uid):
        """Returns the task with the given tuid
        :param task_uid: task's unique id
        :return: the task from the queue
        :rtype: queue.QueueTask
        """
        tasks = self._storage.tasks + self._storage.running_tasks + \
                self._storage.failed_tasks
        for task in tasks:
            if task.task_uid == task_uid:
                return task
        return None

    def get_tasks(self, status=None):
        """Returns an iterable with the tasks from the queue
        :param status: (Optional) a string or list with status. If None, only
            "running" and "queued" are considered
        :return iterable of QueueTask objects
        :rtype: listiterator
        """
        if not isinstance(status, (list, tuple)):
            status = [status]
        status = filter(None, status)
        status = status or ["running", "queued"]

        # all tasks
        tasks = self._storage.running_tasks + self._storage.tasks + \
                self._storage.failed_tasks
        for task in tasks:
            if task.status in status:
                yield task

    def get_uids(self, status=None):
        """Returns a list with the uids from the queue
        :param status: (Optional) a string or list with status. If None, only
            "running" and "queued" are considered
        :return list of uids
        :rtype: list
        """
        out = set()
        for task in self.get_tasks(status=status):
            uids = [task.context_uid] + filter(None, task.get("uids"))
            out.update(uids)
        return list(out)

    def get_tasks_for(self, context_or_uid, name=None):
        """Returns an iterable with the queued or running tasks the queue
        contains for the given context and name, if provided.
        Failed tasks are not considered
        :param context_or_uid: object/brain/uid to look for in the queue
        :param name: name of the type of the task to look for
        :return: iterable of QueueTask objects
        :rtype: listiterator
        """
        uid = capi.get_uid(context_or_uid)

        # Look into both queued and running tasks
        tasks = self._storage.tasks + self._storage.running_tasks
        for task in tasks:
            if name and name != task.name:
                continue

            # Check whether the context passed-in matches with the task's
            # context or with other objects involved in this task
            if uid == task.context_uid or uid in task.get("uids", []):
                yield task

    def has_task(self, task):
        """Returns whether the queue contains a task for the given tuid
        :param task: task's unique id (task_uid) or QueueTask object
        :return: True if the queue contains the task
        :rtype: bool
        """
        task_uid = api.get_task_uid(task)
        out_task = self.get_task(task_uid)
        if out_task:
            return True
        return False

    def has_tasks_for(self, context_or_uid, name=None):
        """Returns whether the queue contains a task for the given context and
        name if provided.
        """
        tasks = self.get_tasks_for(context_or_uid, name=name)
        return any(tasks)

    def get_senders(self):
        """Returns the urls of the clients that have sent at least one task to
        the queue server, except ourselves
        """
        current_url = capi.get_url(capi.get_portal()).lower()

        def is_colleague(host):
            if not host:
                return False
            if current_url.lower().startswith(host.lower()):
                return False
            return True

        return filter(is_colleague, list(self._senders))

    def __len__(self):
        with self.__lock:
            return len(self._storage.tasks)

    def is_empty(self):
        """Returns whether there are no remaining tasks in the queue
        """
        return self.__len__() <= 0

    def is_busy(self):
        """Returns whether a task is being processed
        """
        with self.__lock:
            # Check if the number of running tasks is above max
            return len(self._storage.running_tasks) >= MAX_CONCURRENT_TASKS

    def purge(self):
        """Purges running tasks that got stuck for too long
        """
        with self.__lock:
            self._purge()

    def _purge(self):
        def is_stuck(task):
            max_sec = task.get("max_seconds", 60)
            started = task.get("started", time.time() - max_sec - 1)
            return started + max_sec < time.time()

        # Get non-stuck tasks
        tasks = self._storage.running_tasks
        stuck = filter(is_stuck, tasks)
        if not stuck:
            # No running tasks got stuck
            return

        # Re-queue or add to pool of failed
        map(lambda t: self._fail(t, "Timeout"), stuck)

    def _fail(self, task_uid, error_message=None):
        task = self.get_task(task_uid)
        if not task:
            return

        # Get the running tasks, but the current one
        tasks = self._storage.running_tasks
        other_tasks = filter(lambda t: t.task_uid != task.task_uid, tasks)
        if len(other_tasks) != len(tasks):
            # Remove the task from the pool of running tasks
            self._storage.running_tasks = other_tasks

            # Set the error message
            task["error_message"] = error_message

            # Check if we've reached the max number of remaining retries
            if task.retries > 0:
                task["retries"] -= 1
                # Increase the max number of seconds to wait before this task
                # is being considered stuck. Might happen the task is considered
                # failed because there was no enought time for the task to
                # complete
                max_sec = task.get("max_seconds", 60)

                # Update the create timemillis to make room for other tasks,
                # even if it keeps failing again and again (create is used to
                # sort tasks, together with priority)
                created = time.time()
                task.update({
                    "created": created,
                    "max_seconds": max_sec * 2
                })
                self._add(task)
            else:
                # Add in failed tasks
                failed_tasks = self._storage.failed_tasks
                task.update({"status": "failed"})
                failed_tasks.append(task)
                self._storage.failed_tasks = failed_tasks
                logger.warn("Failed task {} ({}): {}"
                            .format(task.name, task.task_short_uid,
                                    task.context_path))

    def _delete(self, task_uid):
        task = self.get_task(task_uid)
        if not task:
            return

        if task.status == "queued":
            self._storage.tasks = filter(
                lambda t: t.task_uid != task_uid,
                self._storage.tasks)

        elif task.status == "failed":
            self._storage.failed_tasks = filter(
                lambda t: t.task_uid != task_uid,
                self._storage.failed_tasks)

        elif task.status == "running":
            self._storage.running_tasks = filter(
                lambda t: task_uid != task_uid,
                self._storage.running_tasks)

    def _add(self, task, unique=False):
        # Only QueueTask type is supported
        if not isinstance(task, QueueTask):
            raise TypeError("Not supported: {}".format(repr(type(task))))

        # Don't add to the queue if the task is already in there
        if self.has_task(task):
            logger.warn("Task {} ({}) in the queue already"
                        .format(task.name, task.task_short_uid))
            return None

        # Do not add the task if unique and task for same context and name
        if unique and self.has_tasks_for(task.context_uid, name=task.name):
            logger.debug("Task for {} and {} in the queue already".format(
                    task.name, task.context_path))
            return None

        # Append to the list of tasks
        tasks = self._storage.tasks
        task.update({"status": "queued"})
        tasks.append(task)

        # Sort by priority + created reverse
        # We multiply the priority for 300 sec. (5 minutes) and then we sum the
        # result to the time the task was created. This way, we ensure tasks
        # priority at the same time we guarantee older, with low priority
        # tasks don't fall into the cracks.
        # We sort the list reversed because pop() always return the last item
        # of the list and we are sorting by priority (lesser value, the better)
        tasks = sorted(tasks, key=lambda t: (t.created + (300 * t.priority)),
                       reverse=True)

        # Assign the tasks to the queue
        # Note _storage does a _p_changed already
        self._storage.tasks = tasks

        logger.info("Added task {} ({}): {}"
                    .format(task.name, task.task_short_uid, task.context_path))
        return task

