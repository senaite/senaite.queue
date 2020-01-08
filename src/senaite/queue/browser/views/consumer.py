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

import json

from Products.Five.browser import BrowserView
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.storage import QueueStorageTool
from zope.component import queryAdapter

from bika.lims.interfaces import IWorksheet


class QueueConsumerView(BrowserView):
    """View responsible of consuming a task from the queue
    """
    def __init__(self, context, request):
        super(QueueConsumerView, self).__init__(context, request)
        self.context = context
        self.request = request

    def __call__(self):
        # Get the task to be processed
        queue = QueueStorageTool()
        task = queue.current
        if not task:
            queue.release()
            return self.response("No task available", queue, log_mode="error")

        # Check if the task uid passed-in matches with the current task
        task_uid = self.request.get("tuid", None)
        if task.task_uid != task_uid:
            queue.requeue(task)
            msg = "TUID mismatch: {} <> {}".format(task_uid, task.task_uid)
            return self.response(msg, queue, log_mode="warn")

        # Check if current user matches with task's user
        if api.get_current_user().id != task.username:

            # Login as the user who initially fired the task and redirect to
            # consumer again for the authentication to be in force
            if self.login_as(task.username):
                base_url = api.get_url(api.get_portal())
                url = "{}/queue_consumer?tuid={}".format(base_url, task_uid)
                return self.request.response.redirect(url)

            else:
                # Cannot login as this user
                queue.fail(task)
                queue.release()
                msg = "Cannot login with '{}'".format(task.username)
                return self.response(msg, queue, log_mode="error")

        # Do the work
        # At this point, current user matches with task's user
        log_mode = "info"
        msg = "Task '{}' for '{}' processed".format(task.name, task.context_uid)
        try:
            if not self.process_task(task):
                msg = "Cannot process this task: {} [SKIP]".format(repr(task))
                raise RuntimeError(msg)
        except (RuntimeError, Exception) as e:
            queue.fail(task)
            log_mode = "error"
            msg = "{}: {} [SKIP]".format(task.name, e.message)

        # Release the queue
        queue.release()

        # Close the session for current user
        # Quite necessary for when this view is called directly from a browser
        # by an anonymous user that somehow, figured out the TUID
        acl = api.get_tool("acl_users")
        acl.resetCredentials(self.request, self.request.response)
        return self.response(msg, queue, log_mode=log_mode)

    def response(self, msg, queue, log_mode="info"):
        getattr(logger, log_mode)(msg)
        output = {"message": msg, "queue": queue.to_dict()}
        return json.dumps(output)

    def login_as(self, username):
        """
        Login Plone user (without password)
        """
        logger.info("Logging in as {} ...".format(username))
        acl_users = api.get_tool("acl_users")
        user_ob = acl_users.getUserById(username)
        if user_ob is None:
            return False
        acl_users.session._setupSession(username, self.request.response)
        return True

    def process_task(self, task):
        task_context = task.context

        # If the task refers to a worksheet, inject (ws_id) in params to make
        # sure guards (assign, unassign) return True
        if IWorksheet.providedBy(task_context):
            self.request.set("ws_uid", api.get_uid(task_context))

        # Get the adapter able to process this specific type of task
        adapter = queryAdapter(task_context, IQueuedTaskAdapter, name=task.name)
        if adapter:
            logger.info("Processing task '{}' for '{}' ({}) ...".format(
                task.name, api.get_id(task_context), task.context_uid))

            # Process the task
            return adapter.process(task, self.request)

        logger.error("Adapter for task {} and context {} not found!"
                     .format(task.name, task_context.portal_type))
        return False