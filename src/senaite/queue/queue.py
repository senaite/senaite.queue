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

    # Skip some attributes they are assigned when the QueueTask is instantiated
    exclude = ["task_uid", "name", "request", "context_uid", "context_path"]
    out_keys = filter(lambda k: k not in exclude, task_dict.keys())
    kwargs = dict(map(lambda k: (k, task_dict[k]), out_keys))

    # Create the Queue Task
    task = QueueTask(name, api.get_request(), context, **kwargs)
    task.update({
        "task_uid": task_dict.get("task_uid") or task.task_uid,
        "request": request,
    })
    return task


def is_task(task):
    return isinstance(task, QueueTask)
