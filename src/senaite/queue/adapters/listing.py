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

from senaite.queue import api
from senaite.queue import messageFactory as _
from senaite.queue.interfaces import IQueued
from senaite.queue.storage import WorksheetQueueStorage
from senaite.core.listing.interfaces import IListingView
from senaite.core.listing.interfaces import IListingViewAdapter
from zope.component import adapts
from zope.interface import implements


class QueuedWorksheetsViewAdapter(object):
    """Disables the worksheets with analyses awaiting for assignment
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
        if IQueued.providedBy(api.get_object(obj)):
            item["disabled"] = True
            icon = api.get_queue_image("queued.gif", width="55px")
            item["replace"]["state_title"] = _("Queued")
            item["replace"]["Progress"] = icon
        return item


class QueuedWorksheetAnalysesViewAdapter(object):
    """Disables the analyses if the worksheet still contains analyses awaiting
    for being assigned
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority
    priority_order = 1010

    @property
    def in_queue(self):
        return IQueued.providedBy(self.context)

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        return

    def folder_item(self, obj, item, index):
        if self.in_queue:
            item["disabled"] = True
        return item


class QueuedAddAnalysesViewAdapter(object):
    """Displays the analyses assigned to this (queued) worksheet, but disabled
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority of this subscriber adapter over others
    priority_order = 1010
    queued_analyses_uids = list()

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        storage = WorksheetQueueStorage(self.context)
        self.queued_analyses_uids = storage.uids
        return

    def folder_item(self, obj, item, index):
        if IQueued.providedBy(self.context):
            # If the worksheet is in the queue, do not display analyses, but
            # those to be added and disabled
            if api.get_uid(obj) in self.queued_analyses_uids:
                item["disabled"] = True
            else:
                item.clear()
        elif IQueued.providedBy(api.get_object(obj)):
            # Return an empty dict, so listing machinery won't render this item
            item.clear()
        return item


class QueuedAnalysesViewAdapter(object):
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
        if IQueued.providedBy(api.get_object(obj)):
            item["disabled"] = True
            icon = api.get_queue_image("queued.gif", title=_("Queued"),
                                      width="55px")
            item["replace"]["state_title"] = icon
        return item


class QueuedSampleAnalysisServicesViewAdapter(object):
    """Disables the analyses services for which the current context (Sample) has
    at least one analysis awaiting for assignment (IQueued)
    """
    adapts(IListingView)
    implements(IListingViewAdapter)

    # Order of priority
    priority_order = 1010

    def __init__(self, listing, context):
        self.listing = listing
        self.context = context

    def before_render(self):
        analyses = self.context.getAnalyses(full_objects=True)
        analyses = filter(lambda an: IQueued.providedBy(an), analyses)
        self.uids = map(lambda an: an.getServiceUID(), analyses)
        return

    def folder_item(self, obj, item, index):
        if api.get_uid(obj) in self.uids:
            item["disabled"] = True
        return item


class QueuedSamplesViewAdapter(object):
    """Disables the checkbox for samples that provide IQueued and displays
    a loading icon in progress bar column
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
        if IQueued.providedBy(api.get_object(obj)):
            item["disabled"] = True
            icon = api.get_queue_image("queued.gif", width="55px")
            item["replace"]["state_title"] = _("Queued")
            item["replace"]["Progress"] = icon
        return item
