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
# Copyright 2018-2019 by it's authors.
# Some rights reserved, see README and LICENSE.

import json

import transaction
from Products.Five.browser import BrowserView
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.storage import QueueStorageTool
from zope.component import queryAdapter

from bika.lims.decorators import synchronized
from bika.lims.interfaces import IWorksheet


class QueueDispatcherView(BrowserView):
    """View responsible of dispatching queued processes sequentially
    """

    def __init__(self, context, request):
        super(QueueDispatcherView, self).__init__(context, request)
        self.context = context
        self.request = request

    @synchronized(max_connections=1)
    def __call__(self):
        logger.info("Starting Queue Dispatcher ...")

        # Lock the queue to prevent race-conditions
        queue = QueueStorageTool()
        if not queue.lock():
            return self.response("Cannot lock the queue [SKIP]", queue)

        # Get the task to process
        output = self.process_queue(queue)

        # Ensure next thread starts working with latest data
        transaction.commit()

        return output

    def process_queue(self, queue):
        task = queue.pop()
        if not task:
            queue.release()
            msg = "No task available [SKIP]"
            return self.response(msg, queue, log_mode="error")

        # Get the user who fired the task
        user_id = task.request.get("AUTHENTICATED_USER")
        if not user_id:
            queue.fail(task)
            queue.release()
            msg = "Task without user: {} [SKIP]".format(task.task_uid)
            return self.response(msg, queue, log_mode="error")

        # Try to authenticate as the original user
        if not self.login_as(user_id):
            msg = "Cannot login with '{}' [SKIP]".format(user_id)
            logger.warn(msg)

        # Process the task
        try:
            if not self.process_task(task):
                msg = "Cannot process this task: {} [SKIP]".format(repr(task))
                raise RuntimeError(msg)

        except (RuntimeError, Exception) as e:
            msg = "Exception while processing '{}': {} [SKIP]" \
                .format(task.name, e.message)

            # Notify the queue machinery this task has not succeed
            queue.fail(task)
            queue.release()
            return self.response(msg, queue, log_mode="error")

        # Release the queue to make room for others
        queue.release()

        # Return the detailed status of the queue
        msg = "Task '{}' for '{}' processed".format(task.name, task.context_uid)
        return self.response(msg, queue)

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
