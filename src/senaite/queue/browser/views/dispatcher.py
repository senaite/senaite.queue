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

import threading
import time

import requests
from Products.Five.browser import BrowserView
from senaite.queue import api
from senaite.queue import logger

from bika.lims import api as _api
from bika.lims.decorators import synchronized


# Prefix for the name of the thread in charge of notifying consumer
CONSUMER_THREAD_PREFIX = "queue.consumer."


class QueueDispatcherView(BrowserView):
    """View responsible of dispatching queued processes sequentially
    """

    def __init__(self, context, request):
        super(QueueDispatcherView, self).__init__(context, request)
        self.context = context
        self.request = request

    @property
    def queue(self):
        """Returns the queue utility
        """
        return api.get_queue()

    @synchronized(max_connections=1)
    def __call__(self):
        logger.info("Starting Queue Dispatcher ...")

        consumer_thread = self.get_consumer_thread()
        if consumer_thread:
            # There is a consumer working already
            name = consumer_thread.getName()
            logger.info("Consumer running: {} [SKIP]".format(name))
            return "Consumer running"

        if self.queue.is_busy():
            # Purge the queue from tasks that got stuck
            self.queue.purge()
            logger.info("Queue is busy [SKIP]")
            return "Queue is busy"

        if self.queue.is_empty():
            logger.info("Queue is empty [SKIP]")
            return "Queue is empty"

        # Notify the consumer. We do this because even that we can login with
        # the user that fired the task here, the new user session will only
        # take effect after this request life-cycle. We cannot redirect to a
        # new url here, because dispatcher is automatically called by a client
        # worker. Thus, we open a new thread and call the consumer view, that
        # does not require privileges, except that will check the tuid with the
        # task to be processed and login with the proper user thereafter.
        consumer = self.start_consumer_thread()

        msg = "Consumer notified: {}".format(consumer.getName())
        logger.info(msg)
        return msg

    def start_consumer_thread(self):
        """Starts an returns a new thread that notifies the consumer
        """
        base_url = _api.get_url(_api.get_portal())
        url = "{}/queue_consumer".format(base_url)
        name = "{}.{}".format(CONSUMER_THREAD_PREFIX, int(time.time()))
        kwargs = dict(url=url, timeout=api.get_max_seconds_task())
        t = threading.Thread(name=name, target=requests.get, kwargs=kwargs)
        t.start()
        return t

    def get_consumer_thread(self):
        """Returns whether there the consumer thread is running
        """
        def is_consumer_thread(t):
            return t.getName().startswith(CONSUMER_THREAD_PREFIX)

        threads = filter(is_consumer_thread, threading.enumerate())
        if len(threads) > 0:
            return threads[0]
        return None
