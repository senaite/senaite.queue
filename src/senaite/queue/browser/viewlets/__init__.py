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

from plone.app.layout.viewlets import ViewletBase
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.queue import api
from senaite.queue.mixin import IsQueuedMixin


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
        if not api.is_queue_readable():
            return 0

        # We are only interested in tasks with uids
        queue = api.get_queue()
        uids = map(lambda t: t.get("uids"), queue.get_tasks_for(self.context))
        uids = filter(None, list(itertools.chain.from_iterable(uids)))
        return len(set(uids))


class QueuedAnalysesSampleViewlet(ViewletBase, IsQueuedMixin):
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
        if not self.is_queue_readable():
            return 0

        analyses = self.context.getAnalyses()
        queued = filter(self.is_queued, analyses)
        return len(queued)
