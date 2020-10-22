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

from senaite.core.listing.interfaces import IListingView
from senaite.core.listing.interfaces import IListingViewAdapter
from senaite.queue import api
from senaite.queue import messageFactory as _
from senaite.queue.mixin import IsQueuedMixin
from zope.component import adapts
from zope.interface import implements


class QueuedWorksheetsViewAdapter(IsQueuedMixin):
    """Disables the worksheets with analyses awaiting for assignment (queued)
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority of this subscriber adapter over others
    priority_order = 1010

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        return

    def folder_item(self, obj, item, index):
        # Don't do anything if senaite.queue is not enabled
        if not self.is_queue_readable():
            return

        if self.is_queued(obj):
            item["disabled"] = True
            icon = api.get_queue_image("queued.gif", width="55px")
            item["replace"]["state_title"] = _("Queued")
            item["replace"]["getProgressPercentage"] = icon
        return item


class QueuedWorksheetAnalysesViewAdapter(IsQueuedMixin):
    """Disables the analyses if the worksheet still contains analyses awaiting
    for being assigned
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority
    priority_order = 1010

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        return

    def folder_item(self, obj, item, index):
        # Don't do anything if senaite.queue is not enabled
        if not self.is_queue_readable():
            return

        if self.is_queued(self.context):
            item["disabled"] = True
        return item


class QueuedAddAnalysesViewAdapter(IsQueuedMixin):
    """Displays the analyses assigned to this (queued) worksheet, but disabled
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority of this subscriber adapter over others
    priority_order = 1010

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        return

    def folder_item(self, obj, item, index):
        # Don't do anything if senaite.queue is not enabled
        if not self.is_queue_readable():
            return

        if self.is_queued(self.context):
            # If the worksheet is in the queue, do not display analyses, but
            # those to be added and disabled
            if self.is_queued(obj):
                item["disabled"] = True
            else:
                item.clear()
        elif self.is_queued(obj):
            # Return an empty dict, so listing machinery won't render this item
            item.clear()
        return item


class QueuedAnalysesViewAdapter(IsQueuedMixin):
    """Disables the worksheets with analyses awaiting for assignment/action
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority of this subscriber adapter over others
    priority_order = 1010

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        return

    def folder_item(self, obj, item, index):
        # Don't do anything if senaite.queue is not enabled
        if not self.is_queue_readable():
            return

        if self.is_queued(obj):
            item["disabled"] = True
            icon = api.get_queue_image("queued.gif", title=_("Queued"),
                                      width="55px")
            item["replace"]["state_title"] = icon
        return item


class QueuedSampleAnalysisServicesViewAdapter(IsQueuedMixin):
    """Disables the analyses services for which the current context (Sample) has
    at least one analysis awaiting for assignment
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority
    priority_order = 1010

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        return

    def folder_item(self, obj, item, index):
        # Don't do anything if senaite.queue is not enabled
        if not self.is_queue_readable():
            return

        if self.is_queued(obj):
            item["disabled"] = True
        return item


class QueuedSamplesViewAdapter(IsQueuedMixin):
    """Disables the checkbox for queued samples and displays a loading icon in
    progress bar column
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority
    priority_order = 1010

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        return

    def folder_item(self, obj, item, index):
        # Don't do anything if senaite.queue is not enabled
        if not self.is_queue_readable():
            return

        if self.is_queued(obj):
            item["disabled"] = True
            icon = api.get_queue_image("queued.gif", width="55px")
            item["replace"]["state_title"] = _("Queued")
            item["replace"]["Progress"] = icon
        return item
