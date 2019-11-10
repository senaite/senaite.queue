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

from Products.Five.browser import BrowserView
from bika.lims import api
from bika.lims.catalog.analysis_catalog import CATALOG_ANALYSIS_LISTING
from bika.lims.catalog.worksheet_catalog import CATALOG_WORKSHEET_LISTING
from senaite.queue import logger
from senaite.queue.interfaces import IQueued
from senaite.queue.storage import ActionQueueStorage
from senaite.queue.storage import QueueStorageTool
from senaite.queue.storage import WorksheetQueueStorage
from zope.interface import noLongerProvides


class QueueGCView(BrowserView):
    """View that collects Worksheets that are still in Queued status (there are
    analyses awaiting to be assigned) and assign them. If no analyses are found
    or analyses have all been assigned already, removes the IQueued marker from
    the Worksheet.
    """

    def __init__(self, context, request):
        super(QueueGCView, self).__init__(context, request)
        self.context = context
        self.request = request

    def __call__(self):
        if "fix" in self.request:
            self.fix_the_thing()
            return "Fixed"

        if "unlock" in self.request:
            queue = QueueStorageTool()
            queue.storage["processed"] = None
            queue.storage["tasks"].append(queue.current)
            queue.storage["current"] = None
            return "Unlocked"

        if "flush" in self.request:
            # Cleanup QueueStorage
            queue = QueueStorageTool()
            queue.flush()

        if "requeue" in self.request:
            queue = QueueStorageTool()
            processed = queue.storage["processed"]
            if processed:
                queue.storage["tasks"].append(processed)
                queue.storage["processed"] = None
                queue.storage["current"] = None
                return "Requeued"
            return "No processed task found"

        queue = QueueStorageTool()
        return json.dumps(queue.to_dict())

    def fix_the_thing(self):
        ws_processed = list()
        query = dict(portal_type="Analysis",
                     review_state=["unassigned",
                                   "assigned",
                                   "to_be_verified",
                                   "registered"])
        for brain in api.search(query, CATALOG_ANALYSIS_LISTING):
            analysis = api.get_object(brain)
            if IQueued.providedBy(analysis):
                noLongerProvides(analysis, IQueued)
            worksheet = analysis.getWorksheet()
            worksheet_uid = worksheet and api.get_uid(worksheet) or None
            if worksheet_uid and worksheet_uid not in ws_processed:
                self.purge_queue_storage_for(worksheet)
                ws_processed.append(worksheet_uid)

        query = dict(portal_type="Worksheet", review_state="open")
        for brain in api.search(query, CATALOG_WORKSHEET_LISTING):
            if api.get_uid(brain) in ws_processed:
                continue
            ws = api.get_object(brain)
            self.purge_queue_storage_for(ws)

        # Cleanup QueueStorage
        queue = QueueStorageTool()
        queue.flush()

    def purge_queue_storage_for(self, worksheet):
        if not worksheet:
            return
        logger.info("Purging worksheet {} ...".format(api.get_id(worksheet)))
        storage = WorksheetQueueStorage(worksheet)
        storage.flush()
        storage._p_changed = True

        storage = ActionQueueStorage(worksheet)
        storage.flush()
        storage._p_changed = True

        noLongerProvides(worksheet, IQueued)
