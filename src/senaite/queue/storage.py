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
from datetime import datetime

from BTrees.OOBTree import OOBTree
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueued
from senaite.queue.interfaces import IQueuedTaskAdapter
from zope.annotation.interfaces import IAnnotations
from zope.component import queryAdapter
from zope.interface import alsoProvides
from zope.interface import noLongerProvides

# The id of the main tool for queue management of tasks
MAIN_QUEUE_STORAGE_TOOL_ID = "senaite.queue.main.storage"

# The id of the storage of queued tasks. Having a different storage for the
# queue itself and the tasks reduces the chance of database conflicts when a
# task is added to the queue while another task is being processed
TASKS_QUEUE_STORAGE_TOOL_ID = "senaite.queue.main.storage.tasks"

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
    def tasks_storage(self):
        annotations = IAnnotations(self.container)
        if annotations.get(TASKS_QUEUE_STORAGE_TOOL_ID) is None:
            annotations[TASKS_QUEUE_STORAGE_TOOL_ID] = OOBTree()
        return annotations[TASKS_QUEUE_STORAGE_TOOL_ID]

    @property
    def tasks(self):
        """The outstanding tasks from the queue
        """
        if self.tasks_storage.get("tasks") is None:
            self.tasks_storage["tasks"] = list()
        tasks = map(self._task_obj, self.tasks_storage["tasks"])
        return filter(None, tasks)

    @property
    def current(self):
        """The task that is being processed at this time
        """
        current = self.storage.get("current")
        return current and self._task_obj(current) or None

    @property
    def processed(self):
        """The last task being processed or that has been processed
        """
        processed = self.storage.get("processed")
        return processed and self._task_obj(processed) or None

    @property
    def failed(self):
        """List of failed tasks
        """
        if self.storage.get("failed") is None:
            self.storage["failed"] = list()
        tasks = map(self._task_obj, self.storage["failed"])
        return filter(None, tasks)

    @property
    def statistics(self):
        """Statistics information about the queue
        """
        statistics = self.storage.get("statistics")
        if not statistics:
            entry = self.get_statistics_entry()
            entry["queued"] = len(self.tasks)
            statistics = [entry]
            self.storage["statistics"] = statistics
        return statistics

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
        # providing the interface IQueued and there is no other task awaiting
        # for same context, then we assume that the process routine finished,
        # but without success
        obj = processed.context
        if obj and IQueued.providedBy(obj):
            return self.contains_tasks_for(obj)

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

        # Get the maximum seconds for a process to finish before force unlock
        max_seconds = api.get_max_seconds_unlock()
        if max_seconds < 120:
            logger.warn(
                "Seconds to wait before unlock: {}s. Processes might take more "
                "time to complete. Please consider to increase this value!. "
                "Recommended value is 600s".format(max_seconds))

        return diff.total_seconds() > max_seconds

    def sync(self):
        """Synchronizes the queue with the current data from db
        """
        to_sync = [self.container, self.storage, self.tasks_storage]
        for obj in to_sync:
            p_jar = obj._p_jar
            if p_jar is not None:
                p_jar.sync()

    def lock(self):
        """Tries to lock the queue and returns whether it succeeded or not
        """
        with self.__lock:
            if self.is_locked():
                if self.is_stucked():
                    # The queue is in stucked status: we've been waiting for
                    # the current task to finish for too much long. Force the
                    # release to make room to other tasks
                    logger.warn("*** Queue stacked: {}".format(repr(self.current)))
                    if not self.contains(self.current):
                        self.tasks_storage["tasks"].append(self.current)
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
                    self.tasks_storage["tasks"].append(self.processed)

            if len(self.tasks) == 0:
                # No tasks in the queue
                logger.info("*** Cannot lock. Queue is empty")
                return False

            # Lock the queue by assigning the current task to be processed and
            # shifting the tasks in the pool (FIFO)
            self.storage["current"] = self.tasks[0]
            self.storage["processed"] = None
            self.tasks_storage["tasks"] = self.tasks[1:]
            self.storage["locked"] = time.time()
            self.storage._p_changed = True
            self.tasks_storage._p_changed = True
            logger.info("*** Queue locked")
            return True

    def pop(self):
        """Returns the task allocated for being processed
        """
        with self.__lock:
            self.storage["processed"] = self.current
            self.storage._p_changed = True

            # Remove the IQueued interface so it can be transitioned
            context = self.current.context
            if IQueued.providedBy(context):
                noLongerProvides(context, IQueued)

            return self.current

    def release(self):
        """Notifies that the current task has been finished
        """
        with self.__lock:
            # Remove IQueued if there are no more tasks for the context
            if self.current:
                context = self.current.context
                if context:
                    self._handle_queued_marker_for(context)

            # Update statistics
            self.add_stats("processed")
            self.storage["current"] = None
            self.storage["locked"] = None
            self.storage._p_changed = True
            logger.info("*** Queue released")

    def append(self, task):
        """Appends a new task to the queue
        """
        with self.__lock:
            # Don't add to the queue if the task is already in there,
            # even if is in processed or current
            if self.contains(task):
                return False

            # Apply the IQueued marker to the context the task applies to
            context = task.context
            if not IQueued.providedBy(context):
                alsoProvides(context, IQueued)

            # Append the task to the queue
            self.tasks_storage["tasks"].append(task)

            # Update statistics
            self.add_stats("added")

            self.tasks_storage._p_changed = True
            logger.info("*** Queued new task for {}: {}"
                        .format(api.get_id(context), task.name))
            return True

    def add_stats(self, key):
        """Increases the statistics value for the key passed-in in one unit and
        recalculates the total number of queued tasks
        """
        stats = self.statistics
        minute = datetime.now().minute
        if stats[-1]["minute"] == minute:
            stats[-1][key] += 1
        else:
            # New minute, add a new statistics entry
            entry = self.get_statistics_entry(minute=minute)
            entry[key] += 1
            stats.append(entry)

            # We don't want to keep statistics indefinitely!
            record_key = "senaite.queue.max_stats_hours"
            max_hours = api.get_registry_record(record_key, default=4)
            if max_hours < 1:
                max_hours = 1

            # Remove all entries from statistics
            max_entries = max_hours * 60
            stats = stats[-max_entries:]

        # Recalculate queued
        # The number of "added" tasks is a subgroup of tasks that are in queue,
        # but we want to keep track of the tasks added within a given time-frame
        # so the sum of added+queued returns the total number of tasks handled
        # by the queue at the end of that time-frame window.
        added = stats[-1]["added"]
        queued = len(self.tasks_storage["tasks"]) - added
        if queued < 0:
            # This is necessary because a task can be added and processed
            # within the same time-frame window. In such case, at the end of the
            # life-cycle you get 0 tasks in the queue, 1 added and 1 processed.
            queued = 0
        stats[-1]["queued"] = queued
        self.storage["statistics"] = stats

    def get_statistics_entry(self, minute=None):
        """Returns an empty entry for statistics
        """
        entry = {
            "minute": datetime.now().minute,
            "added": 0,
            "removed": 0,
            "processed": 0,
            "queued": 0,
            "failed": 0,
        }
        if minute is not None and 0 <= minute <= 59:
            entry["minute"] = minute
        return entry

    def _handle_queued_marker_for(self, context):
        """Applies/Removes the IQueued marker interface to the context. The
        context gets marked with IQueued if there is still a task awaiting for
        the context passed-in. Removes the marker IQueued otherwise
        """
        if self.contains_tasks_for(context):
            # The queue still contains a task for the context. Add IQueued
            if not IQueued.providedBy(context):
                alsoProvides(context, IQueued)

        elif IQueued.providedBy(context):
            # There is no task awaiting for the context. Remove IQueued
            noLongerProvides(context, IQueued)

    def requeue(self, task):
        """Re-queues the task passed-in
        """
        self.remove(task)
        self.append(task)

    def remove(self, task):
        """Removes the task passed-in from the queue
        """
        with self.__lock:
            # Remove the task from the tasks list
            active_tasks = self.tasks
            if task in active_tasks:
                active_tasks = filter(lambda t: t.task_uid != task.task_uid,
                                      active_tasks)
                self.tasks_storage["tasks"] = active_tasks
                self.tasks_storage._p_changed = True

            # Remove the task from the list of failed tasks
            failed_tasks = self.failed
            if task in failed_tasks:
                failed_tasks = filter(lambda t: t.task_uid != task.task_uid,
                                      failed_tasks)
                self.storage["failed"] = failed_tasks

            # Remove the task from current/processed
            if task == self.current:
                self.storage["current"] = None
            if task == self.processed:
                self.storage["processed"] = None

            # Update statistics
            self.add_stats("removed")

            # Apply the changes
            self.storage._p_changed = True

            # Call the adapter in charge of restoring initial state, if any
            context = task.context
            adapter = queryAdapter(context, IQueuedTaskAdapter, name=task.name)
            if adapter and hasattr(adapter, "flush"):
                try:
                    adapter.flush(task)
                except:
                    # Don't care if something went wrong here (we are probably
                    # removing this task because is somehow corrupted already)
                    logger.warn("Cannot flush {} for {}".format(
                        task.name, repr(context)))

            # Remove IQueued if there are no more tasks queued for the context
            context = task.context
            self._handle_queued_marker_for(context)

            logger.info("*** Removed task for {}: {}".format(
                api.get_id(context), task.name))

    def contains_tasks_for(self, context):
        """Finds tasks in queue for the context passed in
        """
        uid = api.get_uid(context)
        for task in self.tasks:
            if task.context_uid == uid:
                return True
        return False

    def get_task(self, task_or_obj_uid, task_name=None):
        """Returns the tasks for the given uid, that can be either from a task
        or from the context to which the task is bound to
        """
        def is_target_task(candidate, uid, name=None):
            if not candidate:
                return False
            if name and candidate.name != name:
                return False
            return uid in [candidate.task_uid, candidate.context_uid]

        tasks = [self.current] + self.tasks + self.failed
        for task in tasks:
            if is_target_task(task, task_or_obj_uid, task_name):
                return task

        return None

    def contains(self, task, include_locked=False):
        """Checks if the queue contains the task passed-in
        """
        tasks = self.tasks
        if include_locked:
            tasks.extend([self.current, self.processed])
        return task in tasks

    def fail(self, task):
        """Marks a task as failed
        """
        # Update statistics
        self.add_stats("failed")

        # Does the task needs to be reprocessed?
        max_retries = api.get_max_retries()
        if task.retries >= max_retries:
            # Remove task from the queue
            self.remove(task)
            # Add the task to the list of failed
            self.storage["failed"] = self.failed + [task]
        else:
            # Re-queue the task
            task.retries += 1
            self.requeue(task)

    def _task_obj(self, task_dict):
        """Converts a dict representation of a Task to a QueueTask object
        """
        if not task_dict:
            return None
        name = task_dict["name"]
        req = task_dict.get("request")
        context = task_dict["context_uid"]
        task_uid = task_dict["task_uid"]
        retries = task_dict.get("retries", 0)
        return QueueTask(name, req, context, task_uid, retries=retries)

    def to_dict(self):
        """A dict representation of the queue
        """
        return {
            "id": self.id,
            "container": api.get_path(self.container),
            "tasks": self.tasks,
            "current": self.current,
            "locked": self.storage.get("locked"),
            "processed": self.processed, }

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

    def flush(self):
        # Inner objects
        for uid in self.uids:
            obj = api.get_object_by_uid(uid)
            if IQueued.providedBy(obj):
                noLongerProvides(obj, IQueued)

        # Container
        container = self.container
        if IQueued.providedBy(container):
            noLongerProvides(container, IQueued)

        # Flush annotations
        super(ActionQueueStorage, self).flush()


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

    def __init__(self, name, request, context, task_uid, retries=0, *arg, **kw):
        super(QueueTask, self).__init__(*arg, **kw)
        self["name"] = name
        self["context_uid"] = api.get_uid(context)
        self["request"] = self._get_request_data(request).copy()
        self["task_uid"] = task_uid
        self["retries"] = retries

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
                data["AUTHENTICATED_USER"] = authenticated_user
            if isinstance(authenticated_user, basestring):
                data["AUTHENTICATED_USER"] = authenticated_user
        else:
            current_user = api.get_current_user()
            if current_user:
                data["AUTHENTICATED_USER"] = current_user.id

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

    @property
    def retries(self):
        return self["retries"]

    @property
    def task_uid(self):
        return self["task_uid"]

    @property
    def username(self):
        return self.request.get("AUTHENTICATED_USER", None)

    @username.setter
    def username(self, value):
        self["request"]["AUTHENTICATED_USER"] = value

    @retries.setter
    def retries(self, value):
        self["retries"] = value

    def __eq__(self, other):
        return other and self.task_uid == other.task_uid
