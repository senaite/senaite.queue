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
import traceback

import time
from Products.Five.browser import BrowserView
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueuedTaskAdapter
from zope.component import queryAdapter

from bika.lims import api as _api
from bika.lims.interfaces import IWorksheet

_marker = object()

ALLOWED_ACTIONS = ["process", "success", "fail"]


# If the tasks is performed very rapidly, the task will get priority over a
# transaction done from userland. In case of conflict, the transaction from
# userland will fail and will be retried 3 times. We do not want the user to
# experience delays because of the queue, so we make the consumer to take its
# time to complete.
MIN_SECONDS_TASK = 2


class TaskProcessorView(BrowserView):
    """View responsible of processing tasks from the queue
    """

    def __init__(self, context, request):
        super(TaskProcessorView, self).__init__(context, request)
        self.context = context
        self.request = request
        self._task = _marker

    @property
    def queue(self):
        """Returns the queue utility
        """
        return api.get_queue()

    @property
    def task_uid(self):
        """Returns the task uid param value from the request
        """
        return self.request.get("uid") or None

    @property
    def action(self):
        """Returns the action param value from the request
        """
        return self.request.get("action") or None

    @property
    def task(self):
        """Returns the task to process, if any
        """
        if self._task is _marker:
           task = self.task_uid and self.queue.get_task(self.task_uid) or None
           if task and task.status == "running":
               # TODO Check consumer thread id here!
               self._task = task
           else:
               self._task = None

        return self._task

    def __call__(self):
        # Is there any valid action passed-in?
        action_func = self.get_action_func()
        if not action_func:
            return "No valid action"

        # Is there any valid task passed-in?
        if not self.task:
            return "No valid task"

        # Is an authorized user
        if not self.is_authorized():
            # Try to authorize
            return self.auth()

        # Call the process function
        result = action_func()

        # Close the session for current user
        acl = _api.get_tool("acl_users")
        acl.resetCredentials(self.request, self.request.response)

        return result

    def get_action_func(self):
        """Returns the function to use for task processing
        """
        if self.action in ALLOWED_ACTIONS:
            return getattr(self, self.action)
        return None

    def is_authorized(self):
        """Returns whether the current user is authorized or not
        """
        return _api.get_current_user().id == self.task.username

    def auth(self):
        """Tries to authenticate with the user that triggered the task
        """
        if self.login_as(self.task.username):
            # Redirect to the processor, but logged as new user
            base_url = _api.get_url(_api.get_portal())
            url = "{}/queue_task_processor?uid={}&action={}".format(
                base_url, self.task_uid, self.action)
            return self.request.response.redirect(url)
        else:
            # Cannot login as this user!
            msg = "Cannot login with '{}'".format(self.task.username)
            self.queue.fail(self.task, error_message=msg)
            return self.response(msg, log_mode="error")

    def process(self):
        """Process the task passed-in through the request
        """
        try:
            self.process_task(self.task)
            return self.response("Task {} processed".format(self.task_uid))
        except (RuntimeError, Exception) as e:
            # Label the task as failed
            tbex = traceback.format_exc()
            self.queue.fail(self.task, error_message="\n".join([e.message, tbex]))
            msg = "{}: {} [SKIP]\n{}".format(self.task.name, e.message, tbex)
            return self.response(msg, log_mode="error")

    def success(self):
        """Labels the task passed-in through the request as succeeded
        """
        self.queue.success(self.task)
        return self.response("Task {} succeeded".format(self.task_uid))

    def fail(self):
        """Labels the task passed-in through the request as failed
        """
        self.queue.fail(self.task)
        return self.response("Task {} labeled as failed".format(self.task_uid))

    def login_as(self, username):
        """Login Plone user (without password)
        """
        logger.info("Logging in as {} ...".format(username))
        user_ob = self.get_senaite_user(username)
        if user_ob is None:
            if self.get_zope_user(username):
                logger.error("User '{}' belongs to Zope's acl_users root!"
                             .format(username))
            else:
                logger.error("No valid user '{}'".format(username))
            return False
        acl_users = _api.get_tool("acl_users")
        acl_users.session._setupSession(username, self.request.response)
        return True

    def get_senaite_user(self, username):
        """Returns whether the current username matches with a user that
        belongs to Senaite's acl_users
        """
        acl_users = _api.get_tool("acl_users")
        return acl_users.getUserById(username)

    def get_zope_user(self, username):
        """Returns whether the current username matches with a user that
        belongs to Zope acl_users root
        """
        portal = _api.get_portal()
        zope_acl_users = portal.getPhysicalRoot().acl_users
        return zope_acl_users.getUserById(username)

    def response(self, msg, log_mode="info"):
        getattr(logger, log_mode)(msg)
        return msg

    def process_task(self, task):
        # Start the timer
        t0 = time.time()

        # Get the context
        task_context = task.get_context()

        # Get the adapter able to process this specific type of task
        adapter = queryAdapter(task_context, IQueuedTaskAdapter, name=task.name)
        if not adapter:
            raise RuntimeError(
                "No IQueuedTaskAdapter found for task {} and context {}".format(
                    task.name, task.context_path)
            )

        logger.info("Processing task '{}' for '{}' ({}) ...".format(
            task.name, _api.get_id(task_context), task.context_uid))

        # If the task refers to a worksheet, inject (ws_id) in params to make
        # sure guards (assign, unassign) return True
        if IWorksheet.providedBy(task_context):
            self.request.set("ws_uid", _api.get_uid(task_context))

        # Process the task
        adapter.process(task)

        # Sleep a bit for minimum effect against userland threads
        # Better to have a transaction conflict here than in userland
        min_seconds = task.get("min_seconds") or api.get_min_seconds_task()
        while time.time() - t0 < min_seconds:
            time.sleep(0.5)
