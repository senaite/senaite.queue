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

import itertools
import requests
import time
from plone.app.layout.viewlets import ViewletBase
from plone.memoize import ram
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.queue import api
from senaite.queue import is_installed


class QueuedAnalysesViewlet(ViewletBase):
    """ Print a viewlet to display a message stating there are some analyses
    pending to be assigned to this worksheet
    """
    index = ViewPageTemplateFile("templates/queued_analyses_viewlet.pt")

    def __init__(self, context, request, view, manager=None):
        super(QueuedAnalysesViewlet, self).__init__(
            context, request, view, manager=manager)
        self.context = context
        self.request = request
        self.view = view

    def get_num_pending(self):
        if not api.is_queue_enabled():
            return 0

        # We are only interested in tasks with uids
        queue = api.get_queue()
        uids = map(lambda t: t.get("uids"), queue.get_tasks_for(self.context))
        uids = filter(None, list(itertools.chain.from_iterable(uids)))
        return len(set(uids))


class QueuedAnalysesSampleViewlet(ViewletBase):
    """Prints a viewlet to display a message stating there are some analyses
    that are in queue to be assigned to a worksheet
    """
    index = ViewPageTemplateFile("templates/queued_analyses_sample_viewlet.pt")

    def __init__(self, context, request, view, manager=None):
        super(QueuedAnalysesSampleViewlet, self).__init__(
            context, request, view, manager=manager)
        self.context = context
        self.request = request
        self.view = view

    def get_num_analyses_pending(self):
        """Returns the number of analyses pending
        """
        if not api.is_queue_enabled():
            return 0

        analyses = self.context.getAnalyses()
        queued = filter(api.is_queued, analyses)
        return len(queued)


def _server_status_cache_key(method, self):
    """Returns a tuple with current's queue server url and floor division of
    time since epoch by 60 - it's value changes every 60 seconds
    """
    return api.get_server_url(), time.time() // 60


class QueueServerStatusViewlet(ViewletBase):
    """Prints a viewlet to display a message when the status of the queue
    server is not suitable
    """
    index = ViewPageTemplateFile("templates/queue_server_status.pt")

    def __init__(self, context, request, view, manager=None):
        super(QueueServerStatusViewlet, self).__init__(
            context, request, view, manager=manager)
        self.context = context
        self.request = request
        self.view = view

    @ram.cache(_server_status_cache_key)
    def get_server_status(self):
        """Returns the current status of the queue server
        """
        if not is_installed():
            return "ok"

        if api.is_queue_server():
            return "ok"

        server_url = api.get_server_url()
        if not server_url:
            # Server url is not valid
            return "invalid"

        # Ping
        url = "{}/@@API/senaite/v1/version".format(server_url)
        try:
            # Check the request was successful. Raise exception otherwise
            r = requests.get(url, timeout=1)
            r.raise_for_status()
            return "ok"
        except:  # noqa don't care about the response, want a ping only
            return "timeout"
