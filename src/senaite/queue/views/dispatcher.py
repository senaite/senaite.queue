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
import threading

import requests
from Products.Five.browser import BrowserView
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueueDispatcher
from senaite.queue.storage import QueueStorageTool
from senaite.queue.views.consumer import QueueConsumerView
from zope.interface import implements


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

        # We can make the queue consumed async only if we have the named
        # utility 'queue-consumer' registered
        if not api.is_queue_enabled():
            # No async. The job will be done in this same request
            logger.warn("*** No utility found for 'queue_dispatcher'!")
            QueueConsumerView(self.context, self.request)()

        else:
            logger.info("*** Fire async process for 'queue_dispatcher'")
            utility = api.get_queue_utility()
            if not utility.process(queue):
                return self.response("Unable to process. Check the log", queue)

        # Return the detailed status of the queue
        return self.response("Consumer notified", queue)

    def response(self, msg, queue):
        output = {"message": msg,
                  "queue": queue.to_dict()}
        return json.dumps(output)


class QueueDispatcher(object):
    implements(IQueueDispatcher)

    def process(self, queue):
        portal = api.get_portal()
        task = queue.current
        username = task.request.get("AUTHENTICATED_USER")
        if username:
            url = "{}/queue_consumer?user={}".format(
                api.get_url(portal), username)
            logger.info(url)
            thread = threading.Thread(target=requests.get, args=(url,))
            thread.start()
            return True

        logger.error("No user specified!")
        queue.fail(task)
        return False
