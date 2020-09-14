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
            # Purge the queue from tasks that got stuck. It also unlocks the
            # queue if it has been in a dead-lock status for too long
            self.queue.purge()
            logger.info("Queue is busy [SKIP]")
            return "Queue is busy"

        if self.queue.is_empty():
            logger.info("Queue is empty [SKIP]")
            return "Queue is empty"

        # Check if the site is accessible first. We do not want to knock-out the
        # zeo client with more work!. For this we just visit an static resource
        # to make the thing faster, with a timeout of 2 seconds
        dummy_url = api.get_queue_image_url("queued.gif")
        try:
            response = requests.get(dummy_url, timeout=2)
            response.raise_for_status()
        except Exception as e:
            logger.info("{}: {}".format("Server not available", e.message))
            return "Cannot notify the consumer. Server not available"

        # Safe-lock the queue. Dispatcher has been called by a clock, and
        # another thread might be waken-up while we were here, so is awaiting
        # (see synchronized decorator), but will enter as soon as we exit from
        # this function. However, for the changes to take effect, the whole
        # HTTPResponse life-cycle has to resume first. If we don't lock the
        # queue with a timeout,  we are at risk that other threads that are now
        # waiting, will notify consumer as soon as we leave this call.
        # In such case, we would end up with different consumers working at
        # same time.
        # The queue is unlocked automatically as soon as the consumer notifies
        # that a task has failed or succeeded. If the client was stopped while
        # processing a task, the queue automatically unlocks on purge when
        # notices the queue was locked the timeout seconds ago.
        timeout = api.get_max_seconds_task()
        self.queue.lock(timeout)

        # Notify the consumer. We do this because even that we can login with
        # the user that fired the task here, the new user session will only
        # take effect after this request life-cycle. We cannot redirect to a
        # new url here, because dispatcher is automatically called by a client
        # worker. Thus, we open a new thread and call the consumer view, that
        # does not require privileges, except that will check the tuid with the
        # task to be processed and login with the proper user thereafter.
        base_url = _api.get_url(_api.get_portal())
        url = "{}/queue_consumer".format(base_url)
        kwargs = dict(url=url, allow_redirects=True, timeout=5)
        consumer = threading.Thread(target=requests.get, kwargs=kwargs)
        consumer.start()

        return "Consumer notified"
