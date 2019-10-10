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

from Products.Five.browser import BrowserView
from bika.lims import api
from senaite.queue import logger
from senaite.queue import is_queue_enabled
from senaite.queue.storage import QueueStorageTool
from senaite.queue.views.consumer import QueueConsumerView
import requests
import threading


class QueueDispatcherView(BrowserView):
    """View responsible of dispatching queued processes sequentially
    """

    def __init__(self, context, request):
        super(QueueDispatcherView, self).__init__(context, request)
        self.context = context
        self.request = request

    def __call__(self):
        logger.info("Starting Queue Dispatcher ...")

        # Get the queue from storage
        queue = QueueStorageTool()

        # Check the speed on how new objects are added to the queue as an
        # indicator of the overall activity of users. If the speed increases
        # rapidly, better to slow down a bit the dispatcher to prevent users to
        # experience db conflicts
        #speed = queue.speed()
        #logger.info("** SPEED: {}".format(speed))

        if not queue.lock():
            logger.info("Cannot lock the queue [SKIP]")
            return self.response("Cannot lock the queue", queue)

        # We can make the queue consumed async only if we have taskqueue
        if not is_queue_enabled():
            # No async. The job will be done in this same request
            logger.warn("*** No task-queue utility for 'queue-consumer'!")
            QueueConsumerView(self.context, self.request)()

        else:
            # Add to TaskQueue for async processing
            logger.info("*** Fire task-queue for 'queue-consumer'")
            portal = api.get_portal()
            task = queue.current
            username = task.request.get("AUTHENTICATED_USER")
            if username:
                url = "{}/queue_consumer?user={}".format(
                    api.get_url(portal), username)
                logger.info(url)
                thread = threading.Thread(target=requests.get, args=(url,))
                thread.start()
            else:
                logger.error("No user specified!")
                queue.fail(task)
                return self.response("No user specified", queue)

        # Return the detailed status of the queue
        return self.response("Consumer notified", queue)

    def response(self, msg, queue):
        output = {"message": msg,
                  "queue": queue.to_dict()}
        return json.dumps(output)

    def spoof_request(self, task):
        # Inject the PloneUser who started the task
        username = task.request.get("AUTHENTICATED_USER")
        if username:
            mt = api.get_tool("portal_membership")
            user = mt.getMemberById(username)
            user = user and user.getUser() or None
            if user:
                self.request["AUTHENTICATED_USER"] = user

        # Inject the __ac
        __ac = task.request.get("__ac")
        if __ac:
            self.request["__ac"] = __ac
            if hasattr(self.request, "cookies"):
                self.request.cookies["__ac"] = __ac

        remote_addr = task.request.get("REMOTE_ADDR")
        if remote_addr:
            self.request["REMOTE_ADDR"] = remote_addr

        # Copy HTTP-headers from request._orig_env
        self.request._orig_env.update(task._orig_env)
