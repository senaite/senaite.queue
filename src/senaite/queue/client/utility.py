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

import requests
import time
from cryptography.fernet import Fernet
from requests.auth import AuthBase
from senaite.jsonapi.exceptions import APIError
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IClientQueueUtility
from senaite.queue.interfaces import IOfflineClientQueueUtility
from senaite.queue.queue import get_task_uid
from senaite.queue.queue import to_task
from senaite.queue.server.utility import QueueUtility
from zope.component import getUtility
from zope.interface import implements

from bika.lims import api as capi


class ClientQueueUtility(object):
    implements(IClientQueueUtility)

    def add(self, task):
        """Adds a task to the queue
        :param task: the QueueTask to add
        """
        self._post("add", payload=task)

        # Add the task to the utility for operating offline
        utility = getUtility(IOfflineClientQueueUtility)
        return utility.add(task)

    def pop(self, consumer_id):
        """Returns the next task to process, if any
        :param consumer_id: id of the consumer thread that will process the task
        :return: the task to be processed or None
        :rtype: queue.QueueTask
        """
        payload = {"consumerid": consumer_id}
        task = self._post("pop", payload=payload)
        return to_task(task)

    def done(self, task):
        """Notifies the queue that the task has been processed successfully
        :param task: task's unique id (task_uid) or QueueTask object
        """
        payload = {"taskuid": get_task_uid(task)}
        self._post("done", payload=payload)

    def fail(self, task, error_message=None):
        """Notifies the queue that the processing of the task failed
        :param task: task's unique id (task_uid) or QueueTask object
        :param error_message: (Optional) the error/traceback
        """
        payload = {
            "taskuid": get_task_uid(task),
            "error_message": error_message or ""
        }
        self._post("fail", payload=payload)

    def delete(self, task):
        """Removes a task from the queue
        :param task: task's unique id (task_uid) or QueueTask object
        """
        payload = {"taskuid": get_task_uid(task)}
        self._post("delete", payload=payload)

    def get_task(self, task_uid):
        """Returns the task with the given tuid
        :param task_uid: task's unique id
        :return: the task from the queue
        :rtype: queue.QueueTask
        """
        try:
            task_uid = get_task_uid(task_uid)
            # Note the endpoint here is the task uid
            task = self._post(task_uid)
            if not task:
                return None
            return to_task(task)
        except APIError as e:
            if 500 <= e.status < 600:
                # Fallback to off-line mode
                logger.warn("[{}]. Fallback to off-line mode".format(e.status))
                utility = getUtility(IOfflineClientQueueUtility)
                return utility.get_task(task_uid)
            raise e

    def get_tasks(self, status=None):
        """Returns an iterable with the tasks from the queue
        :param status: (Optional) a string or list with status. If None, only
            "running" and "queued" are considered
        :return iterable of QueueTask objects
        :rtype: listiterator
        """
        query = {
            "status": status or "",
            "complete": True,
        }
        try:
            tasks = self._post("tasks", payload=query)
            tasks = tasks.get("items", [])
            for task in tasks:
                yield to_task(task)
        except APIError as e:
            if 500 <= e.status < 600:
                # Fallback to off-line mode
                logger.warn("[{}]. Fallback to off-line mode".format(e.status))
                utility = getUtility(IOfflineClientQueueUtility)
                for task in utility.get_tasks(status=status):
                    yield task
            raise e

    def get_uids(self, status=None):
        """Returns a list with the uids from the queue
        :param status: (Optional) a string or list with status. If None, only
            "running" and "queued" are considered
        :return list of uids
        :rtype: list
        """
        query = {"status": status or ""}
        try:
            uids = self._post("uids", payload=query)
            return uids.get("items", [])
        except APIError as e:
            if 500 <= e.status < 600:
                # Fallback to off-line mode
                logger.warn("[{}]. Fallback to off-line mode".format(e.status))
                utility = getUtility(IOfflineClientQueueUtility)
                return utility.get_uids(status=status)
            raise e

    def get_tasks_for(self, context_or_uid, name=None):
        """Returns an iterable with the queued or running tasks the queue
        contains for the given context and name, if provided.
        Failed tasks are not considered
        :param context_or_uid: object/brain/uid to look for in the queue
        :param name: name of the type of the task to look for
        :return: iterable of QueueTask objects
        :rtype: listiterator
        """
        query = {
            "uid": capi.get_uid(context_or_uid),
            "name": name or "",
            "complete": True,
        }
        try:
            tasks = self._post("search", payload=query)
            tasks = tasks.get("items", [])
            for task in tasks:
                yield to_task(task)
        except APIError as e:
            if 500 <= e.status < 600:
                # Fallback to off-line mode
                logger.warn("[{}]. Fallback to off-line mode".format(e.status))
                utility = getUtility(IOfflineClientQueueUtility)
                for task in utility.get_tasks(context_or_uid, name=name):
                    yield task
            raise e

    def has_task(self, task):
        """Returns whether the queue contains a task for the given tuid
        :param task: task's unique id (task_uid) or QueueTask object
        :return: True if the queue contains the task
        :rtype: bool
        """
        task_uid = get_task_uid(task)
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

    def is_empty(self):
        """Returns whether the queue is empty. Failed tasks are not considered
        :return: True if the queue does not have running nor queued tasks
        :rtype: bool
        """
        # TODO better to do a specific POST for is_empty
        response = self._post("uids")
        uids = response.get("items", [])
        return len(uids) == 0

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


class OfflineClientQueueUtility(QueueUtility):
    """Client queue utility for when the queue server is not reachable.
    It mimics the same behavior as the server's queue utility, except that
    is not allowed and fail always discard the task.

    This utility is feeded with new tasks each time the Client Queue utility
    sends a new task to the Queue server. Queue server sends notifications to
    the client who originally added the task, so they are tunneled into this
    utility to keep it up-to-date.

    The assumption is that a non-reachable queue server is a temporary
    situation. There is always the chance the connectivity with the server is
    lost anytime, but we need to ensure as much as possible the consistency of
    queued objects. For instance, we do want the system to think a given
    worksheet does not have analyses awaiting for assignment because we've
    temporarily lost the connectivity with the queue server
    """
    implements(IOfflineClientQueueUtility)

    def fail(self, task, error_message=None):
        self.delete(task.task_uid)

    def add_senders(self, senders):
        self._senders.update(senders)


class QueueAuth(AuthBase):
    """Attaches HTTP Queue Authentication to the given Request object
    """
    def __init__(self, username):
        self.username = username

    def __call__(self, r):
        # We want our key to be valid for 10 seconds only
        secs = time.time() + 10
        token = "{}:{}".format(secs, self.username)

        # Encrypt the token using our Fernet key
        key = capi.get_registry_record("senaite.queue.auth_key")
        auth_token = Fernet(str(key)).encrypt(token)

        # Modify and return the request
        r.headers["X-Queue-Auth-Token"] = auth_token
        return r
