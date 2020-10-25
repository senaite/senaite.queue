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

import requests
import time
from cryptography.fernet import Fernet
from requests.auth import AuthBase
from requests.exceptions import ConnectionError
from requests.exceptions import HTTPError
from requests.exceptions import Timeout
from requests.exceptions import TooManyRedirects
from senaite.jsonapi.exceptions import APIError
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IClientQueueUtility
from senaite.queue.queue import get_task_uid
from senaite.queue.queue import to_task
from zope.interface import implements  # noqa

from bika.lims import api as capi


class ClientQueueUtility(object):
    implements(IClientQueueUtility)

    # Local store of tasks that is kept up-to-date with queue server
    _tasks = []

    # Synchronization frequency with the queue server in seconds
    # This is used to keep the local store of tasks up-to-date
    _sync_frequency = 2

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

    def sync(self):
        """Synchronizes the local pool of tasks with the server queue

        The synchronization process asks the queue server for tasks that are
        newer than the newest task we have in the pool (created timestamp).
        The queue server returns the new tasks that have been added since then,
        along with the timestamp of the oldest task it holds. Therefore, the
        synchronization only implies the download of newest tasks only and is
        able to drop those from the local store that no longer exist.
        """
        # We are not interested on failed tasks
        created = map(lambda t: t.created, self._tasks)
        since = created and max(created) or 0
        query = {
            "status": ["queued", "running"],
            "since": since,
            "complete": True,
        }
        try:
            response = self._post("tasks", payload=query)
        except (ConnectionError, Timeout, TooManyRedirects) as e:
            msg = "{}: {}".format(type(e).__name__, str(e))
            logger.warn("{} (Operating in headless mode)".format(msg))
            request = capi.get_request()
            request.response.setStatus(200)
            self._sync_frequency = 5
            self._last_sync = time.time()
            return
        except HTTPError as e:
            status = e.response.status_code or 500
            message = e.response.json() or {}
            msg = "{}: {}".format(status, message.get("message", str(e)))
            if 500 <= status < 600:
                logger.warn("{} (Operating in headless mode".format(msg))
                request = capi.get_request()
                request.response.setStatus(200)
                # Increase sync frequency
                self._sync_frequency = 5
                self._last_sync = time.time()
                return
            raise e
        except APIError as e:
            if 500 <= e.status < 600:
                # Server is not reachable, enter in headless mode
                logger.warn("{}: {} (Operating in headless mode)".format(
                    e.status, e.message
                ))
                # Increase sync frequency
                self._sync_frequency = 5
                self._last_sync = time.time()
                e.setStatus(200)
                return
            raise e

        # Restore sync_frequency (just in case)
        self._sync_frequency = 2

        # Get the time of the oldest task the queue server contains and remove
        # our older tasks, so we only need the diff to be in-sync
        oldest = response.get("since_time", 0)
        if oldest < 0:
            # Server Queue does not have tasks. Remove all
            self._tasks = []
        else:
            self._tasks = filter(lambda t: t.created >= oldest, self._tasks)

        # Add the new tasks
        tasks = map(to_task, response.get("items", []))
        tasks = filter(None, tasks)
        self._tasks.extend(tasks)

        # Update the last synchronization time
        self._last_sync = time.time()

    def add(self, task):
        """Adds a task to the queue. It pushes the task directly to the queue
        server via POST and stores the task in the local pool as well
        :param task: the QueueTask to add
        :return: the added QueueTask object
        :rtype: queue.QueueTask
        """
        # Add the task to the queue server
        self._post("add", payload=task)

        # Add the task to our local pool
        self._tasks.append(task)
        return task

    def pop(self, consumer_id):
        """Returns the next task to process, if any. Sends a POST to the queue
        server and updates the task from the local pool as well
        :param consumer_id: id of the consumer thread that will process the task
        :return: the task to be processed or None
        :rtype: queue.QueueTask
        """
        # Pop the task from the queue server
        payload = {"consumer_id": consumer_id}
        task = self._post("pop", payload=payload)
        task = to_task(task)
        if not task:
            return None

        # Update the task from our local pool or add
        tasks = filter(lambda t: t == task, self._tasks)
        if tasks:
            tasks[0].update(task)
        else:
            self._tasks.append(task)

        # Return the task
        return copy.deepcopy(task)

    def done(self, task):
        """Notifies the queue that the task has been processed successfully.
        Sends a POST to the queue server and removes the task from local pool
        :param task: task's unique id (task_uid) or QueueTask object
        """
        # Tell the queue server the task is done
        task_uid = get_task_uid(task)
        payload = {"task_uid": task_uid}
        self._post("done", payload=payload)

        # Remove from local pool
        self._tasks = filter(lambda t: t.task_uid != task_uid, self._tasks)

    def fail(self, task, error_message=None):
        """Notifies the queue that the processing of the task failed. Sends a
        POST to the queue server, but keeps the local pool untouched
        :param task: task's unique id (task_uid) or QueueTask object
        :param error_message: (Optional) the error/traceback
        """
        payload = {
            "task_uid": get_task_uid(task),
            "error_message": error_message or ""
        }
        self._post("fail", payload=payload)

    def delete(self, task):
        """Removes a task from the queue. Sends a POST to the queue server and
        removes the task from the local pool of tasks
        :param task: task's unique id (task_uid) or QueueTask object
        """
        task_uid = get_task_uid(task)
        payload = {"task_uid": task_uid}
        self._post("delete", payload=payload)

        # Remove from our pool
        self._tasks = filter(lambda t: t.task_uid != task_uid, self._tasks)

    def get_task(self, task_uid):
        """Returns the task with the given task uid. Retrieves the task from
        the local pool if exists. Otherwise, fetches the task from the Queue
        server via POST and updates the local pool
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
        task = self._post(task_uid)
        if not task:
            return None
        return to_task(task)

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
        if not status:
            return copy.deepcopy(self._tasks)

        if "failed" in status:
            # We only keep running and queued tasks in our local pool
            query = {
                "status": status or "",
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
        response = requests.post(url, json=payload, auth=auth, timeout=timeout)

        # Check the request is successful. Raise exception otherwise
        response.raise_for_status()

        # Return the result
        return response.json()


class QueueAuth(AuthBase):
    """Attaches HTTP Queue Authentication to the given Request object
    """
    def __init__(self, username):
        self.username = username

    def __call__(self, r):
        # We want our key to be valid for 10 seconds only
        secs = time.time() + 10
        token = "{}:{}".format(secs, self.username)

        # Encrypt the token using our symmetric auth key
        key = capi.get_registry_record("senaite.queue.auth_key")
        auth_token = Fernet(str(key)).encrypt(token)

        # Modify and return the request
        r.headers["X-Queue-Auth-Token"] = auth_token
        return r
