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

import six
from BTrees.OOBTree import OOBTree
from senaite.queue import logger
from senaite.queue.interfaces import IQueueUtility
from zope.annotation.interfaces import IAnnotations
from zope.interface import implements

from bika.lims import api
from bika.lims.utils import tmpID

# The id of the storage for queued tasks
TASKS_QUEUE_STORAGE_TOOL_ID = "senaite.queue.main.storage.tasks"

# Maximum number of concurrent tasks to be processed at a time
MAX_CONCURRENT_TASKS = 1


class QueueStorage(object):
    """Storage that provides access to the tasks from a queue
    """

    @property
    def container(self):
        """The container the annotations storage belongs to
        """
        return api.get_setup()

    @property
    def annotations(self):
        """Returns the annotation's storage of the queue
        """
        annotations = IAnnotations(self.container)
        if annotations.get(TASKS_QUEUE_STORAGE_TOOL_ID) is None:
            annotations[TASKS_QUEUE_STORAGE_TOOL_ID] = OOBTree()
        return annotations[TASKS_QUEUE_STORAGE_TOOL_ID]

    def get(self, key, default=None):
        return self.annotations.get(key, default)

    def set(self, key, value):
        annotations = self.annotations
        annotations[key] = value
        annotations._p_changed = True

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

    def __init__(self):
        self.__lock = threading.Lock()
        self._storage = QueueStorage()

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
            # No running tasks got stuck. Do nothing
            return

        # Re-queue or add to pool of failed
        map(lambda t: self._fail(t, "Timeout"), stuck)

    def pop(self):
        """Returns the next task to process, if any. Otherwise, return None
        """
        with self.__lock:
            tasks = self._storage.tasks
            if len(tasks) <= 0:
                return None

            # Pop the task with more priority
            task = tasks.pop()

            # Assign the tasks to the queue
            self._storage.tasks = tasks

            # Add the task to the running tasks
            task.update({
                "started": time.time(),
                "status": "running"}
            )
            running = self._storage.running_tasks
            running.append(task)
            self._storage.running_tasks = running

            # Return the task
            logger.info("Pop task {}: {}".format(task.name, task.context_path))
            return task

    def fail(self, task, error_message=None):
        """Removes the task from the running tasks. Is re-queued if there are
        remaining retries still. Otherwise, adds the task to the pool of failed
        """
        with self.__lock:
            self._fail(task, error_message=error_message)

    def _fail(self, task, error_message=None):
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
                logger.warn("Failed task {}: {}".format(task.name,
                                                        task.context_path))

    def success(self, task):
        """Removes the task from the running tasks
        """
        with self.__lock:
            # Get the running tasks, but the current one
            tasks = self._storage.running_tasks
            other_tasks = filter(lambda t: t.task_uid != task.task_uid, tasks)
            if len(other_tasks) != len(tasks):
                # Remove the task from the pool of running tasks
                self._storage.running_tasks = other_tasks

    def get_task(self, task_uid):
        """Returns the task for for the TUID passed in
        """
        tasks = self._storage.tasks + self._storage.running_tasks + \
                self._storage.failed_tasks
        for task in tasks:
            if task.task_uid == task_uid:
                return task
        return None

    def has_task(self, task):
        """Returns whether the queue contains the task passed in by tuid
        """
        out_task = self.get_task(task.task_uid)
        if out_task:
            return True
        return False

    def get_tasks_for(self, context_or_uid, name=None):
        """Returns an iterable with the tasks the queue contains for the given
        context and name if provided
        """
        uid = api.get_uid(context_or_uid)

        # Look into both queued and running tasks
        tasks = self._storage.tasks + self._storage.running_tasks
        for task in tasks:
            if name and name != task.name:
                continue

            # Check whether the context passed-in matches with the task's
            # context or with other objects involved in this task
            if uid == task.context_uid or uid in task.get("uids", []):
                yield task

    def has_tasks_for(self, context_or_uid, name=None):
        """Returns whether the queue contains a task for the given context and
        name if provided.
        """
        tasks = self.get_tasks_for(context_or_uid, name=name)
        return any(tasks)

    def add(self, task, unique=False):
        """Adds a task to the queue
        """
        with self.__lock:
            return self._add(task, unique=unique)

    def remove(self, task_uid):
        """Removes a task from the queue
        """
        with self.__lock:
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

    def _add(self, task, unique=False):
        # Only QueueTask type is supported
        if not isinstance(task, QueueTask):
            raise TypeError("Not supported: {}".format(repr(type(task))))

        # Don't add to the queue if the task is already in there
        if self.has_task(task):
            logger.warn(
                "Task {} ({}) in the queue already".format(
                task.task_uid, task.name))
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

        logger.info("Added task {}: {}".format(task.name, task.context_path))
        return task


class QueueTask(dict):
    """A task for queueing
    """

    def __init__(self, name, request, context, *arg, **kw):
        super(QueueTask, self).__init__(*arg, **kw)
        if not api.is_object(context):
            raise TypeError("No valid context object")
        kw = kw or {}
        self.update({
            "task_uid": tmpID(),
            "name": name,
            "context_uid": api.get_uid(context),
            "context_path": api.get_path(context),
            "request": self._get_request_data(request),
            "retries": kw.get("retries", 3),
            "priority": api.to_int(kw.get("priority"), default=10),
            "uids": kw.get("uids", []),
            "created": time.time(),
            "status": None,
            "error_message": None,
        })

    def _get_request_data(self, request):
        data = {
            "__ac": request.get("__ac") or "",
            "_orig_env": self._get_orig_env(request),
            "_ZopeId": request.get("_ZopeId") or "",
            "X_FORWARDED_FOR": request.get("X_FORWARDED_FOR") or "",
            "X_REAL_IP": request.get("X_REAL_IP") or "",
            "REMOTE_ADDR": request.get("REMOTE_ADDR") or "",
            "HTTP_USER_AGENT": request.get("HTTP_USER_AGENT") or "",
            "HTTP_REFERER": request.get("HTTP_REFERER") or "",
            "AUTHENTICATED_USER": self._get_authenticated_user(request),
        }
        return data

    def _get_orig_env(self, request):
        env = {}
        if hasattr(request, "_orig_env"):
            env = getattr(request, "_orig_env", {})
            if not env and hasattr(request, "__dict__"):
                env = self._get_orig_env(request.__dict__)
        elif isinstance(request, dict):
            env = request.get("_orig_env", {})
        elif hasattr(request, "__dict__"):
            env = self._get_orig_env(request.__dict__)
        return env

    def _get_authenticated_user(self, request):
        authenticated_user = request.get("AUTHENTICATED_USER")
        if authenticated_user:
            if hasattr(authenticated_user, "getId"):
                return authenticated_user.getId()
            if isinstance(authenticated_user, six.string_types):
                return authenticated_user

        # Pick current user
        current_user = api.get_current_user()
        return current_user and current_user.id or ""

    @property
    def name(self):
        return self["name"]

    @property
    def task_uid(self):
        return self["task_uid"]

    @property
    def context_uid(self):
        return self["context_uid"]

    @property
    def request(self):
        return self["request"]

    @property
    def priority(self):
        return self["priority"]

    @property
    def status(self):
        return self["status"]

    @property
    def created(self):
        return self["created"]

    @property
    def retries(self):
        return self["retries"]

    @retries.setter
    def retries(self, value):
        self["retries"] = value

    @property
    def username(self):
        return self.request["AUTHENTICATED_USER"]

    @username.setter
    def username(self, value):
        self["request"]["AUTHENTICATED_USER"] = value

    @property
    def context_path(self):
        return self["context_path"]

    def get_context(self):
        return api.get_object_by_uid(self.context_uid)

    def __eq__(self, other):
        return other and self.task_uid == other.task_uid
