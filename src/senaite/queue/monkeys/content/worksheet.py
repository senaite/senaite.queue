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

from bika.lims.catalog.worksheet_catalog import CATALOG_WORKSHEET_LISTING
from bika.lims.interfaces.analysis import IRequestAnalysis
from senaite.queue import api
from senaite.queue.interfaces import IQueued
from senaite.queue.queue import queue_assign_analyses


def _apply_worksheet_template_routine_analyses(self, wst):
    """Add routine analyses to worksheet according to the worksheet template
    layout passed in w/o overwriting slots that are already filled.

    If the template passed in has an instrument assigned, only those
    routine analyses that allows the instrument will be added.

    If the template passed in has a method assigned, only those routine
    analyses that allows the method will be added

    :param wst: worksheet template used as the layout
    :returns: None
    """
    bac = api.get_tool("bika_analysis_catalog")
    services = wst.getService()
    wst_service_uids = [s.UID() for s in services]
    query = {
        "portal_type": "Analysis",
        "getServiceUID": wst_service_uids,
        "review_state": "unassigned",
        "isSampleReceived": True,
        "is_active": True,
        "sort_on": "getPrioritySortkey"
    }
    # Filter analyses their Analysis Requests have been received
    analyses = bac(query)

    # No analyses, nothing to do
    if not analyses:
        return

    # Available slots for routine analyses. Sort reverse, cause we need a
    # stack for sequential assignment of slots
    available_slots = self.resolve_available_slots(wst, 'a')
    available_slots.sort(reverse=True)

    # If there is an instrument assigned to this Worksheet Template, take
    # only the analyses that allow this instrument into consideration.
    instrument = wst.getRawInstrument()

    # If there is method assigned to the Worksheet Template, take only the
    # analyses that allow this method into consideration.
    method = wst.getRawRestrictToMethod()

    # This worksheet is empty?
    num_routine_analyses = len(get_routine_analyses(self))

    # Group Analyses by Analysis Requests
    ar_analyses = dict()
    ar_slots = dict()
    ar_fixed_slots = dict()

    for brain in analyses:
        obj = api.get_object(brain)

        # SENAITE.QUEUE-Specific
        # Discard analyses that are in a processing queue
        if IQueued.providedBy(obj):
            continue

        arid = obj.getRequestID()

        if instrument and not obj.isInstrumentAllowed(instrument):
            # Exclude those analyses for which the worksheet's template
            # instrument is not allowed
            continue

        if method and not obj.isMethodAllowed(method):
            # Exclude those analyses for which the worksheet's template
            # method is not allowed
            continue

        slot = ar_slots.get(arid, None)
        if not slot:
            # We haven't processed other analyses that belong to the same
            # Analysis Request as the current one.
            if len(available_slots) == 0 and num_routine_analyses == 0:
                # No more slots available for this worksheet/template, so
                # we cannot add more analyses to this WS. Also, there is no
                # chance to process a new analysis with an available slot.
                break

            if num_routine_analyses == 0:
                # This worksheet is empty, but there are slots still
                # available, assign the next available slot to this analysis
                slot = available_slots.pop()
            else:
                # This worksheet is not empty and there are slots still
                # available.
                slot = self.get_slot_position(obj.getRequest())
                if slot:
                    # Prefixed slot position
                    ar_fixed_slots[arid] = slot
                    if arid not in ar_analyses:
                        ar_analyses[arid] = list()
                    ar_analyses[arid].append(obj)
                    continue

                # This worksheet does not contain any other analysis
                # belonging to the same Analysis Request as the current
                if len(available_slots) == 0:
                    # There is the chance to process a new analysis that
                    # belongs to an Analysis Request that is already
                    # in this worksheet.
                    continue

                # Assign the next available slot
                slot = available_slots.pop()

        ar_slots[arid] = slot
        if arid not in ar_analyses:
            ar_analyses[arid] = list()
        ar_analyses[arid].append(obj)

    # Sort the analysis requests by sortable_title, so the ARs will appear
    # sorted in natural order. Since we will add the analysis with the
    # exact slot where they have to be displayed, we need to sort the slots
    # too and assign them to each group of analyses in natural order
    sorted_ar_ids = sorted(ar_analyses.keys())
    slots = sorted(ar_slots.values(), reverse=True)

    # SENAITE.QUEUE-SPECIFIC
    queue_uids = list()
    queue_slots = list()
    num = 0
    chunk_size = api.get_chunk_size("task_assign_analyses")
    queue = chunk_size > 0 and api.is_queue_enabled()

    # Add regular analyses
    for ar_id in sorted_ar_ids:
        slot = ar_fixed_slots.get(ar_id, None)
        if not slot:
            slot = slots.pop()
        ar_ans = ar_analyses[ar_id]
        for ar_an in ar_ans:
            # SENAITE.QUEUE-SPECIFIC
            # was: self.addAnalysis(ar_an, slot)
            if num < chunk_size:
                self.addAnalysis(ar_an, slot)

            elif not IRequestAnalysis.providedBy(ar_an):
                # Handle reference analyses (controls + blanks)
                self.addAnalysis(ar_an, slot)

            elif not queue:
                self.addAnalysis(ar_an, slot)

            else:
                queue_uids.append(api.get_uid(ar_an))
                queue_slots.append(str(slot))

            num += 1

    # Mark the worksheet with IQueued and send to async job
    if queue_uids:
        wst_uid = wst and api.get_uid(wst) or None
        queue_assign_analyses(self, api.get_request(), queue_uids, queue_slots,
                              wst_uid=wst_uid)


def get_routine_analyses(worksheet):
    """Returns the routine analyses assigned to the worksheet passed-in
    """
    query = dict(portal_type="Analysis",
                 getWorksheetUID=api.get_uid(worksheet))
    return api.search(query, CATALOG_WORKSHEET_LISTING)


def addAnalyses(self, analyses):
    """Adds a collection of analyses to the Worksheet at once
    """
    queue_uids = list()
    queue_slots = list()
    chunk_size = api.get_chunk_size("task_assign_analyses")
    queue = chunk_size > 0 and api.is_queue_enabled()
    for num, analysis in enumerate(analyses):
        analysis = api.get_object(analysis)
        if num < chunk_size:
            self.addAnalysis(analysis)
        elif not queue:
            self.addAnalysis(analysis)
        elif not IRequestAnalysis.providedBy(analysis):
            self.addAnalysis(analysis)
        else:
            queue_uids.append(api.get_uid(analysis))
            queue_slots.append(None)

    if queue_uids:
        queue_assign_analyses(self, api.get_request(), queue_uids, queue_slots)
