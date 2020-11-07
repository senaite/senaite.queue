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
        if api.is_uid(context):
            context_uid = context
            context_path = kw.get("context_path")
            if not context_path:
                raise ValueError("context_path is missing")

        elif api.is_object(context):
            context_uid = api.get_uid(context)
            context_path = api.get_path(context)

        else:
            raise TypeError("No valid context object")

        # Set defaults
        kw = kw or {}
        task_uid = str(kw.get("task_uid", tmpID()))
        uids = map(str, kw.get("uids", []))
        created = api.to_float(kw.get("created"), default=time.time())
        status = kw.get("status", None)
        min_sec = api.to_int(kw.get("min_seconds"), default=get_min_seconds())
        max_sec = api.to_int(kw.get("max_seconds"), default=get_max_seconds())
        priority = api.to_int(kw.get("priority"), default=10)
        retries = api.to_int(kw.get("retries"), default=get_max_retries())
        unique = self._is_true(kw.get("unique", False))
        chunks = api.to_int(kw.get("chunk_size"), default=get_chunk_size(name))
        username = kw.get("username", self._get_authenticated_user(request))
        err_message = kw.get("error_message", None)

        self.update({
            "task_uid": task_uid,
            "name": name,
            "context_uid": context_uid,
            "context_path": context_path,
            "uids": uids,
            "created": created,
            "status": status and str(status) or None,
            "error_message": err_message and str(err_message) or None,
            "min_seconds": min_sec,
            "max_seconds": max_sec,
            "priority": priority,
            "retries": retries,
            "unique": unique,
            "chunk_size": chunks,
            "username": str(username),
        })

    def _is_true(self, val):
        """Returns whether the value passed in evaluates to True
        """
        return str(val).lower() in ["y", "yes", "1", "true"]

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
        return self["username"]

    @username.setter
    def username(self, value):
        self["username"] = value

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
    context_uid = task_dict.get("context_uid")
    context_path = task_dict.get("context_path")
    if not all([name, context_uid, context_path]):
        return None

    # Skip attrs that are assigned when the QueueTask is instantiated
    exclude = ["name", "request"]
    out_keys = filter(lambda k: k not in exclude, task_dict.keys())
    kwargs = dict(map(lambda k: (k, task_dict[k]), out_keys))

    # Create the Queue Task
    return QueueTask(name, api.get_request(), context_uid, **kwargs)


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


def get_chunks_for(task, items=None):
    """Returns the items splitted into a list. The first element contains the
    first chunk and the second element contains the rest of the items
    """
    if items is None:
        items = task.get("uids", [])

    chunk_size = get_chunk_size(task.name)
    return get_chunks(items, chunk_size)


def get_chunks(items, chunk_size):
    """Returns the items splitted into a list of two items. The first element
    contains the first chunk and the second element contains the rest of the
    items
    """
    if chunk_size <= 0 or chunk_size >= len(items):
        return [items, []]
    return [items[:chunk_size], items[chunk_size:]]


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
        raise ValueError("{} is not supported".format(repr(task_or_uid)))
    return default
