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

import copy

import math
import threading
import time
from senaite.queue import logger
from senaite.queue.interfaces import IServerQueueUtility
from senaite.queue.queue import get_task_uid
from senaite.queue.queue import is_task
from zope.interface import implements  # noqa

from bika.lims import api as capi

# Maximum number of concurrent tasks to be processed at a time
MAX_CONCURRENT_TASKS = 4


class ServerQueueUtility(object):
    """General utility acting as a singleton that provides the basic actions to
    handle a queue of tasks
    """
    implements(IServerQueueUtility)

    def __init__(self):
        self._tasks = []
        self._since_time = -1
        self.__lock = threading.Lock()

    def get_since_time(self):
        return self._since_time

    def add(self, task):
        """Adds a task to the queue
        :param task: the QueueTask to add
        """
        with self.__lock:
            return self._add(task)

    def pop(self, consumer_id):
        """Returns the next task to process, if any
        :param consumer_id: id of the consumer thread that will process the task
        :return: the task to be processed or None
        :rtype: queue.QueueTask
        """
        with self.__lock:
            if self.is_busy():
                # We've reached the max number of tasks to process at same time
                return None

            # Get the queued tasks
            queued = filter(lambda t: t.status == "queued", self._tasks)
            if not queued or self.get_consumer_tasks(consumer_id):
                # Queue does not have tasks available or consumer is already
                # processing some. Maybe there are some that got stack though
                self._purge()
                return None

            # If other consumers are processing tasks, pick the one with
            # more priority, but with different context_path and different name
            # to prevent unnecessary conflicts on transaction.commit
            task_names = self.get_running_task_names()
            paths = self.get_running_context_paths()

            # Tasks are sorted from highest to lowest priority
            for task in queued:
                if task.name in task_names:
                    continue
                if self.strip_path(task.context_path) in paths:
                    continue

                # Update and return the task
                task.update({
                    "started": time.time(),
                    "status": "running",
                    "consumer_id": consumer_id,
                })
                return copy.deepcopy(task)
            return None

    def done(self, task):
        """Notifies the queue that the task has been processed successfully
        :param task: task's unique id (task_uid) or QueueTask object
        """
        self.delete(task)

    def fail(self, task, error_message=None):
        """Notifies the queue that the processing of the task failed. Removes
        the task from the running tasks. Is re-queued if there are remaining
        retries still. Otherwise, adds the task to the pool of failed
        :param task: task's unique id (task_uid) or QueueTask object
        :param error_message: (Optional) the error/traceback
        """
        with self.__lock:
            if is_task(task):
                task_uid = task.task_uid
            elif capi.is_uid(task):
                task_uid = task
            else:
                raise ValueError("Type not supported")

            # We do this dance because the task passed in is probably a copy,
            # but self._fail expects a reference to self._tasks
            task = filter(lambda t: t.task_uid == task_uid, self._tasks)
            if not task:
                raise ValueError("Task is not in the queue")

            # Label the task as failed
            self._fail(task[0], error_message=error_message)

    def delete(self, task):
        """Removes a task from the queue
        :param task: task's unique id (task_uid) or QueueTask object
        """
        with self.__lock:
            task_uid = get_task_uid(task)
            self._delete(task_uid)

    def get_task(self, task_uid):
        """Returns the task with the given task uid
        :param task_uid: task's unique id
        :return: the task from the queue
        :rtype: queue.QueueTask
        """
        for task in self._tasks:
            if task.task_uid == task_uid:
                return copy.deepcopy(task)
        return None

    def get_tasks(self, status=None):
        """Returns a deep copy list with the tasks from the queue
        :param status: (Optional) a string or list with status. If None, only
            "running" and "queued" are considered
        :return list of QueueTask objects
        :rtype: list
        """
        if not isinstance(status, (list, tuple)):
            status = [status]
        status = filter(None, status)
        status = status or ["running", "queued"]
        tasks = filter(lambda t: t.status in status, self._tasks)
        # We don't want self._tasks to be modified from outside!
        return copy.deepcopy(tasks)

    def get_uids(self, status=None):
        """Returns a list with the uids from the queue
        :param status: (Optional) a string or list with status. If None, only
            "running" and "queued" are considered
        :return list of uids
        :rtype: list
        """
        out = set()
        for task in self.get_tasks(status=status):
            uids = [task.context_uid] + filter(None, task.uids)
            out.update(uids)
        return list(out)

    def get_tasks_for(self, context_or_uid, name=None):
        """Returns an iterable with the queued or running tasks the queue
        contains for the given context and name, if provided.
        Failed tasks are not considered
        :param context_or_uid: object/brain/uid to look for in the queue
        :param name: name of the type of the task to look for
        :return: iterable of QueueTask objects
        :rtype: iterator
        """
        # TODO Make this to return a list instead of an iterable
        uid = capi.get_uid(context_or_uid)
        for task in self._tasks:
            if name and task.name != name:
                continue
            if task.context_uid == uid or uid in task.uids:
                yield copy.deepcopy(task)

    def has_task(self, task):
        """Returns whether the queue contains a given task
        :param task: task's unique id (task_uid) or QueueTask object
        :return: True if the queue contains the task
        :rtype: bool
        """
        if self.get_task(get_task_uid(task)):
            return True
        return False

    def has_tasks_for(self, context_or_uid, name=None):
        """Returns whether the queue contains a task for the given context and
        name if provided.
        """
        tasks = self.get_tasks_for(context_or_uid, name=name)
        return any(list(tasks))

    def get_consumer_tasks(self, consumer_id):
        """Returns the tasks the consumer is currently processing
        :param consumer_id: unique id of the consumer
        """
        tasks = self.get_tasks(status="running")
        return filter(lambda t: t.get("consumer_id") == consumer_id, tasks)

    def get_running_context_paths(self):
        """Returns a list with the context paths of the tasks that are running.
        Levels 0 and 1 (site path and paths immediately below) are excluded
        """
        tasks = filter(lambda t: t.status == "running", self._tasks)
        paths = map(lambda t: self.strip_path(t.context_path), tasks)
        return filter(None, paths)

    def strip_path(self, context_path):
        """Strips levels 0 and 1 from the context path passed-in
        """
        parts = context_path.strip("/").split("/")
        if len(parts) > 2:
            return "/".join(parts[2:])
        return ""

    def get_running_task_names(self):
        """Returns a list with the names of the tasks that are running
        """
        names = map(lambda t: t.name, self.get_tasks(status="running"))
        return list(set(names))

    def __len__(self):
        with self.__lock:
            # get_tasks returns a deepcopy. Is faster this way
            status = ["queued", "running"]
            return len(filter(lambda t: t.status in status, self._tasks))

    def update_since_time(self):
        """Returns the created value from oldest task. If no tasks, returns -1
        """
        created = map(lambda t: t.created, self._tasks)
        self._since_time = created and min(created) or -1

    def is_empty(self):
        """Returns whether there are no remaining tasks in the queue
        """
        return self.__len__() <= 0

    def is_busy(self):
        """Returns whether a task is being processed
        """
        running = filter(lambda t: t.status == "running", self._tasks)
        return len(running) >= MAX_CONCURRENT_TASKS

    def purge(self):
        """Purges running tasks that got stuck for too long
        """
        with self.__lock:
            self._purge()

    def _purge(self):
        def is_stuck(task):
            if task.get("status") != "running":
                return False
            max_sec = task.get("max_seconds", 60)
            started = task.get("started", time.time() - max_sec - 1)
            return started + max_sec < time.time()

        # Get tasks that got stuck
        stuck = filter(is_stuck, self._tasks)

        # Re-queue or add to pool of failed
        map(lambda t: self._fail(t, "Timeout"), stuck)

    def _fail(self, task, error_message=None):
        if task.retries > 0:
            # Increase the max number of seconds to wait before this task is
            # being considered stuck. Might happen the task is considered
            # failed because there was no enough time for the task to complete
            max_seconds = task.get("max_seconds", 60)
            max_seconds = int(math.ceil(max_seconds * 1.5))

            # Update the create time millis to make room for other tasks, even
            # if it keeps failing again and again (create is used to sort tasks,
            # together with priority)
            created = time.time()

            # Update the status of the task. Note we directly update the task,
            # cause is a reference to the object stored in self._tasks
            task.update({
                "error_message": error_message,
                "retries": task.retries - 1,
                "max_seconds": max_seconds,
                "created": created,
            })
        else:
            # Consider the task as failed
            task.update({
                "status": "failed",
                "error_message": error_message
            })

        # Update the since time (failed tasks are stored for traceability,
        # but they are excluded from everywhere unless explicitly requested
        self.update_since_time()

    def _delete(self, task_uid):
        task = self.get_task(task_uid)
        if not task:
            return
        idx = self._tasks.index(task)
        del(self._tasks[idx])
        self.update_since_time()

    def _add(self, task):
        # Only QueueTask type is supported
        if not is_task(task):
            raise TypeError("Not supported: {}".format(repr(type(task))))

        # Don't add to the queue if the task is already in there
        if task in self._tasks:
            logger.warn("Task {} ({}) in the queue already"
                        .format(task.name, task.task_short_uid))
            return None

        # Do not add the task if unique and task for same context and name
        unique = task.get("unique", False)
        if unique and self.has_tasks_for(task.context_uid, name=task.name):
            logger.debug("Task for {} and {} in the queue already".format(
                    task.name, task.context_path))
            return None

        # Update task status and append to the list of tasks
        task.update({"status": "queued"})
        self._tasks.append(task)

        # Sort by priority + created reverse
        # We multiply the priority for 300 sec. (5 minutes) and then we sum the
        # result to the time the task was created. This way, we ensure tasks
        # priority at the same time we guarantee older, with low priority
        # tasks don't fall through the cracks.
        # TODO: Make this 300 sec. configurable?
        self._tasks.sort(key=lambda t: (t.created + (300 * t.priority)))

        # Update the since time
        if self._since_time < 0 or self._since_time > task.created:
            self._since_time = task.created

        logger.info("Added task {} ({}): {}"
                    .format(task.name, task.task_short_uid, task.context_path))
        return task
