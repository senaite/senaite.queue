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
# Copyright 2018-2019 by it's authors.
# Some rights reserved, see README and LICENSE.

import threading
import time
from datetime import datetime

from BTrees.OOBTree import OOBTree
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueued
from zope.annotation.interfaces import IAnnotations
from zope.interface import alsoProvides

# The id of the main tool for queue management of tasks
MAIN_QUEUE_STORAGE_TOOL_ID = "senaite.queue.main.storage"

# The id of the tool for queue management of action-like tasks in a container
ACTION_QUEUE_STORAGE_TOOL_ID = "senaite.queue.action.storage"

# The id of the tool for queue management of worksheet-specific tasks
WORKSHEET_QUEUE_STORAGE_TOOL_ID = "senaite.queue.worksheet.storage"


class BaseStorageTool(object):

    @property
    def id(self):
        raise NotImplementedError("BaseStorageTool.id not implemented")

    @property
    def container(self):
        raise NotImplementedError("BaseStorageTool.container not implemented")

    @property
    def storage(self):
        """The annotations storage this tool is bound to
        """
        annotations = IAnnotations(self.container)
        if annotations.get(self.id) is None:
            annotations[self.id] = OOBTree()
        return annotations[self.id]

    def flush(self):
        annotations = IAnnotations(self.container)
        if annotations.get(self.id) is not None:
            del annotations[self.id]


class QueueStorageTool(BaseStorageTool):
    """Storage tool for the management of queue of tasks to be
    done asynchronously
    """

    _container = None
    __lock = threading.Lock()

    @property
    def id(self):
        """The id of this storage in annotations
        """
        return MAIN_QUEUE_STORAGE_TOOL_ID

    @property
    def container(self):
        """The container the annotations storage belongs to
        """
        if not self._container:
            self._container = api.get_setup()
        return self._container

    @property
    def tasks(self):
        """The outstanding tasks from the queue
        """
        if self.storage.get("tasks") is None:
            self.storage["tasks"] = list()
        tasks = map(self._task_obj, self.storage["tasks"])
        return filter(None, tasks)

    @property
    def current(self):
        """The task that is being processed at this time
        """
        current = self.storage.get("current")
        return current and self._task_obj(current) or None

    @property
    def processed(self):
        """The last task being processed or that was processed
        """
        processed = self.storage.get("processed")
        return processed and self._task_obj(processed) or None

    @property
    def speed(self):
        """Number of tasks added since the last time the queue was locked
        """
        speed = self.storage.get("speed")
        return speed and speed or 0

    def is_empty(self):
        """Returns whether the queue is empty and healthy
        """
        if len(self.tasks) == 0:
            return self.is_healthy()
        return False

    def is_locked(self):
        """Checks whether a task from the queue is actually under process
        """
        if self.current:
            # A task is being processed
            return True
        return False

    def is_healthy(self):
        """Checks whether the last task succeeded or not
        """
        processed = self.processed
        if not processed:
            # No task has been processed yet
            return True

        elif processed and self.current:
            # A task is being processed
            return True

        # If the context object of the task marked as "processed" is still
        # providing the interface IQueued, then we assume that the process
        # routine finished, but without success
        obj = processed.context
        if obj and IQueued.providedBy(obj):
            return False

        # If there is no object associated to this task or the object does not
        # provide IQueued, we don't have any chance to know if whether the task
        # succeed or not. Assume is healthy
        return True

    def is_stucked(self):
        """Checks whether the queue is stucked or not, meaning stucked when the
        current task has not been yet finished after the maximum allowed time
        for a task to complete
        """
        if not self.current:
            return False

        # Get the timestamp when last lock took place
        since = self.storage.get("locked")
        if not since:
            self.storage["locked"] = time.time()
            return False

        # Calculate the difference between current time and time when the queue
        # was locked for the last time
        now = time.time()
        diff = datetime.fromtimestamp(now) - datetime.fromtimestamp(since)
        return diff.total_seconds() > api.get_max_seconds_unlock()

    def lock(self):
        """Tries to lock the queue and returns whether it succeeded or not
        """
        with self.__lock:
            if self.is_locked():
                if self.is_stucked():
                    # The queue is in stucked status: we've been waiting for
                    # the current task to finish for too much long. Force the
                    # release to make room to other tasks
                    logger.warn("*** Queue stucked: {}".format(repr(self.current)))
                    if not self.contains(self.current):
                        self.storage["tasks"].append(self.current)
                else:
                    # A task is actually under process and hasn't been finished
                    # yet, so it cannot be unlocked
                    logger.info("*** Cannot lock. Task undergoing")
                    return False

            elif not self.is_healthy():
                # The queue is not healthy, so the previous task did not
                # finish successfully. Requeue the task at the end, just to
                # prevent the queue processing to be blocked because of a task
                # that is always failing
                logger.warn("*** Queue not healthy: {}".format(repr(self.processed)))
                if not self.contains(self.processed):
                    self.storage["tasks"].append(self.processed)

            if len(self.tasks) == 0:
                # No tasks in the queue
                logger.info("*** Cannot lock. Queue is empty")
                return False

            # Update the speed
            self.storage["speed"] = len(self) - self.speed

            # Lock the queue by assigning the current task to be processed and
            # shifting the tasks in the pool (FIFO)
            self.storage["current"] = self.tasks[0]
            self.storage["processed"] = None
            self.storage["tasks"] = self.tasks[1:]
            self.storage["locked"] = time.time()
            self.storage._p_changed = True
            logger.info("*** Queue locked")
            return True

    def pop(self):
        """Returns the task allocated for being processed
        """
        with self.__lock:
            self.storage["processed"] = self.current
            self.storage._p_changed = True
            return self.current

    def release(self):
        """Notifies that the current task has been finished
        """
        with self.__lock:
            self.storage["current"] = None
            self.storage["locked"] = None
            self.storage._p_changed = True
            logger.info("*** Queue released")

    def append(self, name, request, context):
        """Adds a new task at the end of the queue
        """
        with self.__lock:
            # Don't add to the queue if the task is already in there,
            # even if is in processed or current
            alsoProvides(context, IQueued)
            task = QueueTask(name, request, context)
            if self.contains(task):
                return False
            # Append the task to the queue
            self.storage["tasks"].append(task)
            self.storage._p_changed = True
            logger.info("*** Queued new task for {}: {}"
                        .format(api.get_id(context), name))
            return True

    def contains(self, task, include_locked=False):
        """Checks if the queue contains the task passed-in
        """
        tasks = self.tasks
        if include_locked:
            tasks.extend([self.current, self.processed])
        return task in tasks

    def fail(self, task, message=None):
        """Marks a task as failed
        """
        context = task.context
        #alsoProvides(context, IQueued)
        msg = "*** Queued task failed for {}: {}".format(
            api.get_id(context), task.name)
        if message:
            msg = "{} ({})".format(msg, message)
        logger.info(msg)

    def _task_obj(self, task_dict):
        """Converts a dict representation of a Task to a QueueTask object
        """
        if not task_dict:
            return None
        name = task_dict["name"]
        req = task_dict.get("request")
        context = task_dict["context_uid"]
        return QueueTask(name, req, context)

    def to_dict(self):
        """A dict representation of the queue
        """
        return {
            "id": self.id,
            "container": api.get_path(self.container),
            "tasks": self.tasks,
            "current": self.current,
            "locked": self.storage.get("locked"),
            "processed": self.processed,
            "speed": self.speed }

    def __len__(self):
        return len(self.tasks)

    def __repr__(self):
        return repr(self.to_dict())


class ActionQueueStorage(BaseStorageTool):
    """A tool for the management of actions to take place in a queued manner
    for several objects from a given container/context
    """

    def __init__(self, container):
        self._container = container

    @property
    def container(self):
        """The container the annotations storage belongs to
        """
        if not self._container:
            self._container = api.get_setup()
        return self._container

    @property
    def id(self):
        return ACTION_QUEUE_STORAGE_TOOL_ID

    @property
    def uids(self):
        return self.storage.get("uids") or []

    @property
    def action(self):
        return self.storage.get("action") or None

    def _queue_obj(self, obj):
        """Queues the object into the container
        """
        obj = api.get_object(obj)
        if not IQueued.providedBy(obj):
            # Mark the objects to be transitioned with IQueued so they are
            # displayed as disabled in listings
            alsoProvides(obj, IQueued)
        return api.get_uid(obj)

    def queue(self, uids_or_objects, **kwargs):
        if not uids_or_objects:
            return False

        # Mark the objects to transition with IQueued
        queued_uids = map(self._queue_obj, uids_or_objects)
        queued_uids = filter(None, queued_uids)
        if not queued_uids:
            return False

        if kwargs is not None:
            for key, value in kwargs.iteritems():
                self.storage[key] = value

        self.storage["uids"] = queued_uids
        self.storage._p_changed = True


class WorksheetQueueStorage(ActionQueueStorage):
    """A tool for handling worksheet-related specific tasks such as assignment
    of analyses
    """

    @property
    def id(self):
        return WORKSHEET_QUEUE_STORAGE_TOOL_ID

    @property
    def slots(self):
        return map(lambda slot: api.to_int(slot, default=None),
                   self.storage.get("slots") or [])

    @property
    def wst_uid(self):
        return self.storage.get("wst_uid") or None


class QueueTask(dict):
    """A task for queuing
    """

    def __init__(self, name, request, context, *arg, **kw):
        super(QueueTask, self).__init__(*arg, **kw)
        self["name"] = name
        self["context_uid"] = api.get_uid(context)
        self["request"] = self._get_request_data(request).copy()

    def _get_request_data(self, request):
        env = getattr(request, "_orig_env", None) or {}
        if not env and hasattr(request, "__dict__"):
            env = request.__dict__.get("_orig_env", None) or {}
        elif request and "_orig_env" in request:
            env = request.get("_orig_env")

        data = {
            "_orig_env": env,
            "X_FORWARDED_FOR": request.get("X_FORWARDED_FOR") or "",
            "X_REAL_IP": request.get("X_REAL_IP") or "",
            "REMOTE_ADDR": request.get("REMOTE_ADDR") or "",
            "HTTP_USER_AGENT": request.get("HTTP_USER_AGENT") or "",
            "HTTP_REFERER": request.get("HTTP_REFERER") or "",
        }

        # Get auth values
        authenticated_user = request.get("AUTHENTICATED_USER")
        if authenticated_user:
            if hasattr(authenticated_user, "getId"):
                authenticated_user = authenticated_user.getId()
            if isinstance(authenticated_user, basestring):
                data["AUTHENTICATED_USER"] = authenticated_user

        __ac = request.get("__ac")
        if __ac:
            data["__ac"] = __ac

        _ZopeId = request.get("_ZopeId")
        if _ZopeId:
            data["_ZopeId"] = _ZopeId

        return data

    @property
    def context_uid(self):
        return self["context_uid"]

    @property
    def context(self):
        return api.get_object_by_uid(self.context_uid, default=None)

    @property
    def request(self):
        return self["request"].copy()

    @property
    def name(self):
        return self["name"]

    @property
    def _orig_env(self):
        return self.request["_orig_env"]

    @property
    def headers(self):
        orig_req = self.request
        del(orig_req["_orig_env"])
        return orig_req

    def __eq__(self, other):
        if not isinstance(other, QueueTask):
            return False
        if self.context_uid != other.context_uid:
            return False
        return True
