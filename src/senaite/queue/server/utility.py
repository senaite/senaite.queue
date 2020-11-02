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
from bika.lims import APIError

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

    # TODO REMOVE (no longer required)
    def get_since_time(self):
        """Returns the time since epoch when the oldest task the queue contains
        was created, failed tasks excluded. Returns -1 if queue has no queued
        or running tasks
        """
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
            # Get the queued tasks
            queued = filter(lambda t: t.status == "queued", self._tasks)
            if not queued:
                # Maybe some tasks got stuck
                self._purge()

            consumer_tasks = self._get_consumer_tasks(consumer_id)
            if consumer_tasks:
                # This consumer has tasks running already, mark those that have
                # been running for more than 10s as failed. We assume here the
                # consumer always checks there is no thread running from his
                # side before doing a pop(). Thus, we consider that when a
                # consumer does a pop(), he did not succeed with running ones.
                for consumer_task in consumer_tasks:
                    started = consumer_task.get("started")
                    if not started or started + 10 < time.time():
                        msg = "Purged on pop ({})".format(consumer_id)
                        self._fail(consumer_task, error_message=msg)
                return None

            if self.is_busy():
                # We've reached the max number of tasks to process at same time
                return None

            # Get the names and paths of tasks that are currently running
            running_names = self.get_running_task_names()
            running_paths = self.get_running_context_paths()

            # Tasks are sorted from highest to lowest priority
            for task in queued:
                # Wait some secs before a task is available for pop. We do not
                # want to start processing the task while the life-cycle of the
                # request that added the task is still alive
                delay = capi.to_int(task.get("delay"), default=0)
                if task.created + delay > time.time():
                    continue

                # Be sure there is no other consumer working in a same type of
                # task and for the same path
                if task.name in running_names:
                    # There is another consumer processing a task of same type
                    if self.strip_path(task.context_path) in running_paths:
                        # Same path, skip
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
            # We do this dance because the task passed in is probably a copy,
            # but self._fail expects a reference to self._tasks
            task_uid = get_task_uid(task)
            task = filter(lambda t: t.task_uid == task_uid, self._tasks)
            if not task:
                raise ValueError("Task is not in the queue")

            # Label the task as failed
            self._fail(task[0], error_message=error_message)

    def timeout(self, task):
        """Notifies the queue that the processing of the task timed out.
        Increases the max_seconds to spend with this task in 1.5 and removes
        the task from the running tasks. If remaining retries, the task is
        eventually re-queued. Is added to the pool of failed otherwise
        :param task: task's unique id (task_uid) or QueueTask object
        """
        with self.__lock:
            # We do this dance because the task passed in is probably a copy,
            # but self._timeout expects a reference to self._tasks
            task_uid = get_task_uid(task)
            task = filter(lambda t: t.task_uid == task_uid, self._tasks)
            if not task:
                raise ValueError("Task is not in the queue")

            # Mark the task as failed by timeout
            self._timeout(task[0])

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
        task_uid = get_task_uid(task_uid)
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
        """Returns a list with the queued or running tasks the queue contains
        for the given context and name, if provided. Failed tasks are not
        considered
        :param context_or_uid: object/brain/uid to look for in the queue
        :param name: name of the type of the task to look for
        :return: list of QueueTask objects
        :rtype: list
        """
        try:
            uid = capi.get_uid(context_or_uid)
        except APIError:
            raise ValueError("{} is not supported".format(repr(context_or_uid)))

        tasks = []
        for task in self._tasks:
            if name and task.name != name:
                continue
            if task.context_uid == uid or uid in task.uids:
                tasks.append(copy.deepcopy(task))
        return tasks

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
        return any(tasks)

    def _get_consumer_tasks(self, consumer_id):
        """Returns the tasks the consumer is currently processing
        :param consumer_id: unique id of the consumer
        """
        running = filter(lambda t: t.status == "running", self._tasks)
        return filter(lambda t: t.get("consumer_id") == consumer_id, running)

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
        return len(parts) > 2 and parts[2] or ""

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
        """Returns the created time since epoch from oldest task. If no tasks,
        returns -1
        """
        # Update the since time (failed tasks are stored for traceability,
        # but they are excluded from everywhere unless explicitly requested
        active = filter(lambda t: t.status != "failed", self._tasks)
        created = map(lambda t: t.created, active)
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
        map(lambda t: self._timeout(t), stuck)

    def _fail(self, task, error_message=None):
        if task.retries > 0:
            # Update the status of the task. Note we directly update the task,
            # cause is a reference to the object stored in self._tasks
            # - Reduce the number of remaining retries
            # - Update the create time to make room for other tasks
            # - Reduce the chunk size for less change of a transaction conflict
            # - Add a delay of 5 seconds
            task.update({
                "error_message": error_message,
                "retries": task.retries - 1,
                "created": time.time(),
                "chunk_size": -(-task.get("chunk_size", 10) // 2),
                "status": "queued",
                "delay": 5,
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

    def _timeout(self, task):
        # Increase the max number of seconds to wait before this task is
        # being considered stuck
        max_seconds = task.get("max_seconds", 60)
        max_seconds = int(math.ceil(max_seconds * 1.5))
        task.update({
            "max_seconds": max_seconds,
        })

        # Label the task as failed
        self._fail(task, error_message="Timeout")

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
            raise ValueError("{} is not supported".format(repr(task)))

        # Don't add to the queue if the task is already in there
        if task in self._tasks:
            logger.warn("Task {} ({}) in the queue already"
                        .format(task.name, task.task_short_uid))
            return None

        # Do not add the task if unique and task for same context and name
        if task.get("unique", False):
            query = {"context_uid": task.context_uid, "name": task.name}
            if self.search(query):
                logger.debug("Task {} for {} in the queue already".format(
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

    def search(self, query):
        def is_match(task):
            for k, v in query.items():
                attr = getattr(task, k)
                if not attr or attr != v:
                    return False
            return True

        return copy.deepcopy(filter(is_match, self._tasks))
