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
import threading

import requests
import transaction
from Products.Five.browser import BrowserView
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.storage import QueueStorageTool

from bika.lims.decorators import synchronized


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

        # Sync, cause maybe a previous thread modified the queue while we were
        # waiting for that thread to finish due to the synchronized decorator
        queue = QueueStorageTool()
        queue.sync()

        # Lock the queue to prevent other threads not using this dispatcher
        # (it should never happen) to process tasks while we are on it. This
        # guarantees the tasks are always processed sequentially
        if not queue.lock():
            return self.response("Cannot lock the queue [SKIP]", queue)

        # Pop the task to process
        task = queue.pop()

        # Ensure next thread starts working with latest data. We need to ensure
        # the data is stored in the database before we leave the function to
        # allow the next thread that might be awaiting because of synchronized
        # decorator to sync the queue with latest data
        transaction.commit()

        # Notify the consumer. We do this because even that we can login with
        # the user that fired the task here, the new user session will only
        # take effect after this request life-cycle. We cannot redirect to a
        # new url here, because dispatcher is automatically called by a client
        # worker. Thus, we open a new thread and call the consumer view, that
        # does not require privileges, except that will check the tuid with the
        # task to be processed and login with the proper user thereafter.
        self.notify_consumer(task)
        return self.response("Consumer notified", queue)

    def notify_consumer(self, task):
        """Requests for the consumer view in a new thread
        """
        task_uid = task and task.task_uid or "empty"
        base_url = api.get_url(api.get_portal())
        url = "{}/queue_consumer?tuid={}".format(base_url, task_uid)
        thread = threading.Thread(target=requests.get, args=(url,))
        thread.start()

    def response(self, msg, queue):
        output = {"message": msg, "queue": queue.to_dict()}
        return json.dumps(output)
