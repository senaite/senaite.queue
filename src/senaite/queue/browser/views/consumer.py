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

import time
import traceback

from Products.Five.browser import BrowserView
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueuedTaskAdapter
from zope.component import queryAdapter

from bika.lims import api as _api
from bika.lims.interfaces import IWorksheet

# If the tasks is performed very rapidly, the task will get priority over a
# transaction done from userland. In case of conflict, the transaction from
# userland will fail and will be retried 3 times. We do not want the user to
# experience delays because of the queue, so we make the consumer to take its
# time to complete.
MIN_SECONDS_TASK = 2


class QueueConsumerView(BrowserView):
    """View responsible of consuming a task from the queue
    """
    def __init__(self, context, request):
        super(QueueConsumerView, self).__init__(context, request)
        self.context = context
        self.request = request

    @property
    def queue(self):
        return api.get_queue()

    def get_task(self):
        """Returns the task to be processed
        """
        task_uid = self.request.get("tuid")
        if task_uid:
            task = self.queue.get_task(task_uid)
            if task and task.status != "running":
                return None
            return task
        return self.queue.pop()

    def __call__(self):
        task = self.get_task()
        if not task:
            # No tasks remaining or task not found, do nothing
            return self.response("No task available", log_mode="info")

        # Check if current user matches with task's user
        if _api.get_current_user().id != task.username:

            # Login as the user who initially fired the task and redirect to
            # consumer again for the authentication to be in force
            if self.login_as(task.username):
                base_url = _api.get_url(_api.get_portal())
                url = "{}/queue_consumer?tuid={}".format(base_url, task.task_uid)
                return self.request.response.redirect(url)
            else:
                # Cannot login as this user!
                msg = "Cannot login with '{}'".format(task.username)
                self.queue.fail(task, error_message=msg)
                return self.response(msg, log_mode="error")

        # Do the work
        # At this point, current user matches with task's user
        log_mode = "info"
        msg = "Task '{}' for '{}' processed".format(task.name, task.context_path)
        try:
            # Process the task
            self.process_task(task)

            # Mark the task as succeded
            self.queue.success(task)

        except (RuntimeError, Exception) as e:
            self.queue.fail(task)
            tbex = traceback.format_exc()
            self.queue.fail(task, error_message="\n".join([e.mesage, tbex]))
            log_mode = "error"
            msg = "{}: {} [SKIP]\n{}".format(task.name, e.message, tbex)

        # Close the session for current user
        # Quite necessary for when this view is called directly from a browser
        # by an anonymous user that somehow, figured out the TUID
        acl = _api.get_tool("acl_users")
        acl.resetCredentials(self.request, self.request.response)
        return self.response(msg, log_mode=log_mode)

    def response(self, msg, log_mode="info"):
        getattr(logger, log_mode)(msg)
        return msg

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
