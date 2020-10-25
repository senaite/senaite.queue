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

import six
import time

from bika.lims import api
from bika.lims.utils import tmpID

_marker = object()


class QueueTask(dict):
    """A task for queueing
    """

    def __init__(self, name, request, context, *arg, **kw):
        super(QueueTask, self).__init__(*arg, **kw)
        if not api.is_object(context):
            raise TypeError("No valid context object")
        kw = kw or {}
        # Set defaults
        self.update({
            "task_uid": kw.get("task_uid") or tmpID(),
            "name": name,
            "request": self._get_request_data(request),
            "context_uid": api.get_uid(context),
            "context_path": api.get_path(context),
            "uids": kw.get("uids", []),
            "created": kw.get("created", time.time()),
            "status": kw.get("status", None),
            "error_message": kw.get("error_message", None),
            "min_seconds": kw.get("min_seconds", get_min_seconds()),
            "max_seconds": kw.get("max_seconds", get_max_seconds()),
            "priority": api.to_int(kw.get("priority"), default=10),
            "retries": kw.get("retries", get_max_retries()),
            "unique": kw.get("unique", False),
            "chunk_size": kw.get("chunk_size", get_chunk_size(name))
        })

    def _get_request_data(self, request):
        # TODO All this is no longer required!
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
    def task_short_uid(self):
        return self.task_uid[:9]

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
    def uids(self):
        return self["uids"]

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


def new_task(name, context, **kw):
    """Creates a QueueTask
    :param name: the name of the task
    :param context: the context the task is bound or relates to
    :param min_seconds: (optional) int, minimum seconds to book for the task
    :param max_seconds: (optional) int, maximum seconds to wait for the task
    :param retries: (optional) int, maximum number of retries on failure
    :param username: (optional) str, the name of the user assigned to the task
    :param priority: (optional) int, the priority value for this task
    :param unique: (optional) bool, if True, the task will only be added if
            there is no other task with same name and for same context
    :param chunk_size: (optional) the number of items to process asynchronously
            at once from this task (if it contains multiple elements)
    :return: :class:`QueueTask <QueueTask>`
    :rtype: senaite.queue.queue.QueueTask
    """
    # Skip attrs that are assigned when the QueueTask is instantiated
    exclude = ["task_uid", "name", "request", "context_uid", "context_path"]
    out_keys = filter(lambda k: k not in exclude, kw.keys())
    kwargs = dict(map(lambda k: (k, kw[k]), out_keys))

    # Create the Queue Task
    task = QueueTask(name, api.get_request(), context, **kwargs)

    # Set the username (if provided in kw)
    task.username = kw.get("username", task.username)
    return task


def to_task(task_dict):
    """Converts a dict representation of a task to a QueueTask object
    :param task_dict: dict that represents a task
    :return: the QueueTask object the passed-in task_dict represents
    :rtype: QueueTask
    """
    name = task_dict.get("name")
    request = task_dict.get("request")
    context_uid = task_dict.get("context_uid")
    if not all([name, request, context_uid]):
        return None

    # The task must have a valid context
    context = api.get_object_by_uid(context_uid, default=None)
    if not context:
        return None

    # Skip attrs that are assigned when the QueueTask is instantiated
    exclude = ["name", "request", "context_uid", "context_path"]
    out_keys = filter(lambda k: k not in exclude, task_dict.keys())
    kwargs = dict(map(lambda k: (k, task_dict[k]), out_keys))

    # Create the Queue Task
    task = QueueTask(name, api.get_request(), context, **kwargs)

    # Update with the original request
    task.update({"request": request})
    return task


def is_task(task):
    """Returns whether the value passed in is a task
    """
    return isinstance(task, QueueTask)


def get_min_seconds(default=3):
    """Returns the minimum number of seconds to book per task
    """
    registry_id = "senaite.queue.min_seconds_task"
    min_seconds = api.get_registry_record(registry_id)
    min_seconds = api.to_int(min_seconds, default=default)
    return min_seconds >= 1 and min_seconds or default


def get_max_seconds(default=120):
    """Returns the max number of seconds to wait for a task to finish
    """
    registry_id = "senaite.queue.max_seconds_unlock"
    max_seconds = api.get_registry_record(registry_id)
    max_seconds = api.to_int(max_seconds, default=default)
    return max_seconds >= 30 and max_seconds or default


def get_max_retries(default=3):
    """Returns the number of retries before considering a task as failed
    """
    registry_id = "senaite.queue.max_retries"
    max_retries = api.get_registry_record(registry_id)
    max_retries = api.to_int(max_retries, default=default)
    return max_retries >= 1 and max_retries or default


def get_chunk_size(name_or_action=None):
    """Returns the number of items to process at once for the given task name
    :param name_or_action: task name or workflow action id
    :returns: the number of items from the task to process async at once
    :rtype: int
    """
    chunk_size = api.get_registry_record("senaite.queue.default")
    chunk_size = api.to_int(chunk_size, 0)
    if chunk_size <= 0:
        # Queue disabled
        return 0

    if name_or_action:
        # TODO Retrieve task-specific chunk-sizes via adapters
        pass

    if chunk_size < 0:
        chunk_size = 0

    return chunk_size


def get_task_uid(task_or_uid, default=_marker):
    """Returns the task unique identifier
    :param task_or_uid: QueueTask/task uid/dict
    :param default: (Optional) fallback value
    :return: the task's unique identifier
    """
    if api.is_uid(task_or_uid) and task_or_uid != "0":
        return task_or_uid
    if isinstance(task_or_uid, QueueTask):
        return get_task_uid(task_or_uid.task_uid, default=default)
    if isinstance(task_or_uid, dict):
        task_uid = task_or_uid.get("task_uid", None)
        return get_task_uid(task_uid, default=default)
    if default is _marker:
        raise ValueError("Not supported type: {}".format(task_or_uid))
    return default
