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

from Products.Five.browser import BrowserView
from bika.lims.interfaces import IWorksheet
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.storage import QueueStorageTool
from zope.component import queryAdapter


class QueueConsumerView(BrowserView):
    """The view in charge of consuming tasks dispatched by the dispatcher
    """

    def __init__(self, context, request):
        super(QueueConsumerView, self).__init__(context, request)
        self.context = context
        self.request = request

    def __call__(self):
        username = self.request.get("user")
        if username:
            logger.info("Logging in as '{}'".format(username))
            if not (self.login_as(username)):
                logger.error("Cannot login as '{}'".format(username))

            portal = api.get_portal()
            path = "{}/queue_consumer".format(api.get_path(portal))
            return self.request.response.redirect(path)

        logger.info("Starting Queue Consumer ...")
        user = api.get_current_user()
        logger.info("Logged in as '{}'".format(user.id))

        # Get the task to be processed
        queue = QueueStorageTool()
        task = queue.pop()
        if not task:
            logger.error("No task available ... [SKIP]")
            return "No task available ... [SKIP]"

        # Process the task
        try:
            if not self.process_task(task):
                msg = "Cannot process this task: {}".format(repr(task))
                raise RuntimeError(msg)
        except (RuntimeError, Exception) as e:
            msg = "Exception while processing the queued task '{}': {}"\
                .format(task.name, str(e.args[0]))
            logger.error(msg)

            # Notify the queue machinery this task has not succeed
            queue.fail(task)
            queue.release()
            return msg

        # Allow other tasks to be processed
        queue.release()
        msg = "Task '{}' for '{}' processed".format(task.name, task.context_uid)
        logger.info(msg)
        return msg

    def process_task(self, task):
        task_context = task.context

        # If the task refers to a worksheet, inject (ws_id) in params to make
        # sure guards (assign, unassign) return True
        if IWorksheet.providedBy(task_context):
            self.request.set("ws_uid", api.get_uid(task_context))

        adapter = queryAdapter(task_context, IQueuedTaskAdapter, name=task.name)
        if adapter:
            # Process the task
            logger.info("Processing task '{}' for '{}' ({}) ...".format(
                task.name, api.get_id(task_context), task.context_uid))
            return adapter.process(task, self.request)

        logger.error("Adapter for task {} and context {} not found!"
                     .format(task.name, task_context.portal_type))
        return False

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
