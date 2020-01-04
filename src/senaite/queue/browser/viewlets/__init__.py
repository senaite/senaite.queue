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

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.queue.interfaces import IQueued
from senaite.queue.storage import ActionQueueStorage
from senaite.queue.storage import WorksheetQueueStorage
from plone.app.layout.viewlets import ViewletBase


class QueuedAnalysesViewlet(ViewletBase):
    """ Print a viewlet to display a message stating there are some analyses
    pending to be assigned to this worksheet
    """
    template = ViewPageTemplateFile("templates/queued_analyses_viewlet.pt")

    def __init__(self, context, request, view, manager=None):
        super(QueuedAnalysesViewlet, self).__init__(
            context, request, view, manager=manager)
        self.context = context
        self.request = request
        self.view = view

    def render(self):
        return self.template()

    def get_num_pending(self):
        assign = self.get_num_analyses_pending()
        actions = self.get_num_analyses_action_pending()
        return assign + actions

    def get_num_analyses_pending(self):
        """Returns the number of analyses pending
        """
        if not IQueued.providedBy(self.context):
            return 0

        # Worksheet-specific storage
        storage = WorksheetQueueStorage(self.context)
        return len(storage.uids)

    def get_num_analyses_action_pending(self):
        # Actions-specific storage
        if not IQueued.providedBy(self.context):
            return 0
        storage = ActionQueueStorage(self.context)
        return len(storage.uids)


class QueuedAnalysesSampleViewlet(ViewletBase):
    """Prints a viewlet to display a message stating there are some analyses
    that are in queue to be assigned to a worksheet
    """
    template = ViewPageTemplateFile("templates/queued_analyses_sample_viewlet.pt")

    def __init__(self, context, request, view, manager=None):
        super(QueuedAnalysesSampleViewlet, self).__init__(
            context, request, view, manager=manager)
        self.context = context
        self.request = request
        self.view = view

    def render(self):
        return self.template()

    def get_num_analyses_pending(self):
        """Returns the number of analyses pending
        """
        analyses = self.context.getAnalyses(full_objects=True)
        queued = filter(IQueued.providedBy, analyses)
        return len(queued)
