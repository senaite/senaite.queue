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
import requests
import time
from requests.exceptions import ConnectionError
from requests.exceptions import HTTPError
from requests.exceptions import Timeout
from requests.exceptions import TooManyRedirects
from senaite.jsonapi.exceptions import APIError
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IClientQueueUtility
from senaite.queue.pasplugin import QueueAuth
from senaite.queue.queue import get_task_uid
from senaite.queue.queue import is_task
from senaite.queue.queue import to_task
from zope.interface import implements  # noqa

from bika.lims import api as capi


class ClientQueueUtility(object):
    implements(IClientQueueUtility)

    # The HTTP requests handler
    _req = requests

    # Local store of tasks that is kept up-to-date with queue server
    _tasks = []

    # Synchronization frequency with the queue server in seconds
    # This is used to keep the local store of tasks up-to-date
    _sync_frequency = 2

    # Maximum seconds to wait before requests when no server response
    # System keeps increasing the frequency until this value is reached
    _sync_frequency_max = 30

    # Last synchronization time millis
    _last_sync = None

    def is_out_of_date(self):
        """Returns whether this client queue utility is out-of-date and requires
        a synchronization of tasks with the queue server
        :return: True if this utility is out-of-date
        """
        if self._last_sync is None:
            return True
        return self._last_sync + self._sync_frequency < time.time()

    # TODO Add a synchronize decorator here?
    def sync(self):
        """Synchronizes the local pool of tasks with the queue server

        The synchronization comprehends two processes:

        a) *pull*: downloads data from the queue server to keep the local pool
            of tasks up-to-date. The system asks to queue server for tasks that
            are newer than the newest task we have in the pool. The queue server
            returns the new tasks that have been added since then, along with
            the timestamp of the oldest task it holds. Therefore, the pull only
            implies the download of newest tasks only and is able to drop those
            from the local store that no longer exist.

        b) *push*: uploads the tasks that have been added or labeled as done
            locally while the connectivity with the queue server was lost.

        In any of the two processes, exceptions related with connectivity and
        bad response from the queue server are handled gracefully so tasks can
        eventually be re-processed later, as soon as the connectivity with the
        queue server is re-established.

        However, the assumption is that loosing connectivity with the queue
        server is not the norm, rather a temporary scenario that has to be
        considered in order to not bother users unnecessarily. Each zeo client
        has it's own local pool of tasks and this synchronization does not do
        any kind of sync among them.
        """
        # Download new tasks from server
        self._sync_pull()

        # Push tasks that have been handled offline
        self._sync_push()

    def _sync_pull(self):
        """Updates the local tasks with those from the queue server
        """
        # Tell the server the task uids we have in our local pool, but those
        # with status running (always pull running tasks)
        queued = filter(lambda t: t.status == "queued", self._tasks)
        query = {
            "uids": map(lambda t: t.task_uid, queued),
            "status": ["queued", "running"],
            "complete": True,
        }

        err = None
        data = None
        try:
            data = self._post("diff", payload=query)
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            err = "{}: {}".format(type(e).__name__, str(e))

        except HTTPError as e:
            status = e.response.status_code or 500
            if status < 500 or status >= 600:
                raise e
            message = e.response.json() or {}
            err = "{}: {}".format(status, message.get("message", str(e)))

        except APIError as e:
            if e.status < 500 or e.status >= 600:
                raise e
            err = "{}: {}".format(e.status, e.message)

        # If handled error, increase the sync frequency (up to 30 seconds), set
        # the HTTP response status to 200 and do nothing else
        if err:
            logger.warn("{} (Operating in server-less mode)".format(err))
            self._sync_frequency = math.ceil(self._sync_frequency * 1.5)
            self._sync_frequency = min([self._sync_frequency_max,
                                        self._sync_frequency])
            self._last_sync = time.time()
            capi.get_request().response.setStatus(200)
            return False

        # Restore sync_frequency
        self._sync_frequency = 2

        # Get the stale task uids from the response
        stale = filter(None, data.get("stale", []))

        # Get the new tasks retrieved from the server
        new_tasks = filter(None, map(to_task, data.get("items", [])))

        def keep(task):
            if task.task_uid in stale:
                # This task is no longer valid
                return False

            if task in new_tasks:
                # Server's task has priority over local's unless the local
                # task is labeled with "offline" wildcard
                if task.get("offline"):
                    return True
                return False

            if task.status in "running":
                # Always drop running tasks
                return False

            # In sync or unknown by server
            return True

        # Keep unknowns and remove stales or more recent tasks
        self._tasks = filter(keep, self._tasks)

        # Extend with the new tasks retrieved from the server
        self._tasks.extend(new_tasks)

        # Sort by priority + created
        self._tasks.sort(key=lambda t: (t.created + (300 * t.priority)))

        # Update the last synchronization time
        self._last_sync = time.time()
        return True

    def _sync_push(self):
        """Pushes the tasks modified locally to the queue server
        """
        for task in filter(lambda t: t.get("offline"), self._tasks):
            action = task.get("offline")
            action_func = getattr(self, action)
            try:
                task.pop("offline")
                action_func(task)
            except Exception as e:
                # push is not critical to operate, dismiss
                err = "{}: {}".format(type(e).__name__, str(e))
                logger.error(err)
                capi.get_request().response.setStatus(200)

    def add(self, task):
        """Adds a task to the queue. It pushes the task directly to the queue
        server via POST and stores the task in the local pool as well
        :param task: the QueueTask to add
        :return: the added QueueTask object
        :rtype: queue.QueueTask
        """
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
            if self.get_tasks_for(task.context_uid, name=task.name):
                logger.debug("Task {} for {} in the queue already".format(
                        task.name, task.context_path))
                return None

        # Add the task to the queue server
        err = None
        try:
            self._post("add", payload=task)
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            err = "{}: {}".format(type(e).__name__, str(e))

        except HTTPError as e:
            status = e.response.status_code or 500
            if status < 500 or status >= 600:
                raise e
            message = e.response.json() or {}
            err = "{}: {}".format(status, message.get("message", str(e)))

        except APIError as e:
            if e.status < 500 or e.status >= 600:
                raise e
            err = "{}: {}".format(e.status, e.message)

        if err:
            # Not able to add the task to the queue server. Keep it locally
            # so it can be synchronized as soon as we have connectivity again
            logger.warn(err)
            capi.get_request().response.setStatus(200)
            task.update({"offline": "add"})

        # Add the task to our local pool
        task.update({"status": "queued"})
        if task not in self._tasks:
            self._tasks.append(task)

            # Sort by priority + created
            self._tasks.sort(key=lambda t: (t.created + (300 * t.priority)))

        return task

    def pop(self, consumer_id):
        """Returns the next task to process, if any. Sends a POST to the queue
        server and updates the local pool accordingly
        :param consumer_id: id of the consumer thread that will process the task
        :return: the task to be processed or None
        :rtype: queue.QueueTask
        """
        payload = {"consumer_id": consumer_id}
        task = self._post("pop", payload=payload)
        task = to_task(task)
        # Always sync on pop (tasks might be purged by server)
        self.sync()
        return task

    def done(self, task):
        """Notifies the queue that the task has been processed successfully.
        Sends a POST to the queue server and removes the task from local pool
        :param task: task's unique id (task_uid) or QueueTask object
        """
        # Tell the queue server the task is done
        task_uid = get_task_uid(task)
        payload = {"task_uid": task_uid}
        err = None
        try:
            self._post("done", payload=payload)
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            err = "{}: {}".format(type(e).__name__, str(e))

        except HTTPError as e:
            status = e.response.status_code or 500
            if status < 500 or status >= 600:
                raise e
            message = e.response.json() or {}
            err = "{}: {}".format(status, message.get("message", str(e)))

        except APIError as e:
            if e.status < 500 or e.status >= 600:
                raise e
            err = "{}: {}".format(e.status, e.message)

        if err:
            # Not able to tell the queue server. Keep it locally so it can be
            # synchronized as soon as we have connectivity again
            logger.warn(err)
            capi.get_request().response.setStatus(200)
            task_uid = get_task_uid(task_uid)
            tasks = filter(lambda t: t.task_uid == task_uid, self._tasks)
            if tasks:
                task = tasks[0]
            else:
                self._tasks.append(task)
            task.update({"offline": "done"})
            return

        # Remove from local pool
        self._tasks = filter(lambda t: t.task_uid != task_uid, self._tasks)

    def fail(self, task, error_message=None):
        """Notifies the queue that the processing of the task failed. Sends a
        POST to the queue server and updates the local pool accordingly
        :param task: task's unique id (task_uid) or QueueTask object
        :param error_message: (Optional) the error/traceback
        """
        task_uid = get_task_uid(task)
        payload = {"task_uid": task_uid, "error_message": error_message or ""}
        self._post("fail", payload=payload)
        # Always sync on fail (task might be re-queued or failed by server)
        self.sync()

    def timeout(self, task):
        """Notifies the queue that the processing of the task timed out. Sends a
        POST to the queue server and updates the local pool accordingly
        :param task: task's unique id (task_uid) or QueueTask object
        """
        payload = {"task_uid": get_task_uid(task)}
        self._post("timeout", payload=payload)
        # Always sync on timeout (task might be re-queued or failed by server)
        self.sync()

    def delete(self, task):
        """Removes a task from the queue. Sends a POST to the queue server and
        removes the task from the local pool of tasks
        :param task: task's unique id (task_uid) or QueueTask object
        """
        task_uid = get_task_uid(task)
        payload = {"task_uid": task_uid}
        try:
            self._post("delete", payload=payload)
        except HTTPError as e:
            # If not found (404), return None instead of exception to make this
            # client utility to behave as server's
            if e.response.status_code != 404:
                raise e

        # Remove from our pool
        self._tasks = filter(lambda t: t.task_uid != task_uid, self._tasks)

    def get_task(self, task_uid):
        """Returns the task with the given task uid. Retrieves the task from
        the local pool if exists. Otherwise, fetches the task from the Queue
        server via POST
        :param task_uid: task's unique id
        :return: the task from the queue
        :rtype: queue.QueueTask
        """
        # Search first in our local pool
        task_uid = get_task_uid(task_uid)
        task = filter(lambda t: t.task_uid == task_uid, self._tasks)
        if task:
            return copy.deepcopy(task[0])

        # Ask the queue server (maybe we are searching for a failed)
        task_uid = get_task_uid(task_uid)
        try:
            task = self._post(task_uid)
        except HTTPError as e:
            # If not found (404), return None instead of exception to make this
            # utility to behave as server's
            if e.response.status_code != 404:
                raise e
        except Exception as e:
            raise e
        if not task:
            return None
        return to_task(task)

    def get_tasks(self, status=None):
        """Returns a deep copy list with the tasks from the queue
        :param status: (Optional) a string or list with status: If None, only
            "running" and "queued" are considered
        :return list of QueueTask objects
        :rtype: list
        """
        if not isinstance(status, (list, tuple)):
            status = [status]
        status = filter(None, status)
        if not status:
            return copy.deepcopy(self._tasks)

        # "ghost" and "failed" statuses require a POST to queue server, cause
        # we only keep running and queued tasks in our local pool
        ask_server = any(map(lambda s: s in status, ["ghost", "failed"]))
        if ask_server:
            query = {
                "status": status,
                "complete": True,
            }
            tasks = self._post("tasks", payload=query)
            return map(to_task, tasks.get("items", []))

        # Filter by status
        tasks = filter(lambda t: t.status in status, self._tasks)
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
        except capi.APIError:
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

    def is_empty(self):
        """Returns whether the queue is empty. Failed tasks are not considered
        :return: True if the queue does not have running nor queued tasks
        :rtype: bool
        """
        return len(self._tasks) <= 0

    def _post(self, endpoint, resource=None, payload=None, timeout=10):
        """Sends a POST request to SENAITE's Queue Server
        Raises an exception if the response status is not HTTP 2xx or timeout
        :param endpoint: the endpoint to POST against
        :param resource: (Optional) resource from the endpoint to POST against
        :param payload: (Optional) hashable payload for the POST
        """
        server_url = api.get_server_url()
        parts = "/".join(filter(None, [endpoint, resource]))
        url = "{}/@@API/senaite/v1/queue_server/{}".format(server_url, parts)
        logger.info("** POST: {}".format(url))

        # HTTP Queue Authentication to be added in the request
        auth = QueueAuth(capi.get_current_user().id)

        # Additional information to the payload
        request = capi.get_request()
        if payload is None:
            payload = {}
        payload.update({"__zeo": request.get("SERVER_URL")})

        # This might rise exceptions (e.g. TimeoutException)
        response = self._req.post(url, json=payload, auth=auth, timeout=timeout)

        # Check the request is successful. Raise exception otherwise
        response.raise_for_status()

        # Return the result
        return response.json()

    def __len__(self):
        return len(self._tasks)
