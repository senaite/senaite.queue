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

import requests
from Products.Five.browser import BrowserView
from senaite.queue import api
from senaite.queue import logger

from bika.lims import api as _api
from bika.lims.decorators import synchronized


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
        base_url = _api.get_url(_api.get_portal())
        url = "{}/queue_consumer".format(base_url)

        # We set a timeout of 300 to prevent the thread to hang indefinitely
        # in case the url happens to be not reachable for some reason
        kwargs = dict(url=url, allow_redirects=True, timeout=300)
        consumer = threading.Thread(target=requests.get, kwargs=kwargs)
        consumer.start()

        return "Consumer notified"
