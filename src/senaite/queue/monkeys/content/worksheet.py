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
from senaite.queue import logger

from bika.lims import api as _api
from bika.lims.catalog import CATALOG_ANALYSIS_LISTING
from bika.lims.interfaces.analysis import IRequestAnalysis


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
    # Get the services from the Worksheet Template
    service_uids = wst.getRawService()
    if not service_uids:
        # No service uids assigned to this Worksheet Template, skip
        logger.warn("Worksheet Template {} has no services assigned"
                    .format(_api.get_path(wst)))
        return

    # Search for unassigned analyses
    query = {
        "portal_type": "Analysis",
        "getServiceUID": service_uids,
        "review_state": "unassigned",
        "isSampleReceived": True,
        "is_active": True,
        "sort_on": "getPrioritySortkey"
    }
    analyses = _api.search(query, CATALOG_ANALYSIS_LISTING)
    if not analyses:
        return

    # Available slots for routine analyses
    available_slots = self.resolve_available_slots(wst, 'a')
    available_slots.sort(reverse=True)

    # If there is an instrument assigned to this Worksheet Template, take
    # only the analyses that allow this instrument into consideration.
    instrument = wst.getRawInstrument()

    # If there is method assigned to the Worksheet Template, take only the
    # analyses that allow this method into consideration.
    method = wst.getRawRestrictToMethod()

    # Map existing sample uids with slots
    samples_slots = dict(self.get_containers_slots())

    # Keep track of the UIDs of pre-existing Samples
    existing = samples_slots.keys()

    new_analyses = []

    for analysis in analyses:
        if api.is_queued(analysis):
            continue

        analysis = _api.get_object(analysis)

        if analysis.getWorksheet():
            # TODO FIX IN CORE, duplicate record or bad value for review_state?
            continue

        if instrument and not analysis.isInstrumentAllowed(instrument):
            # Template's Instrument does not support this analysis
            continue

        if method and not analysis.isMethodAllowed(method):
            # Template's method does not support this analysis
            continue

        # Get the slot where analyses from this sample are located
        sample = analysis.getRequest()
        sample_uid = _api.get_uid(sample)
        slot = samples_slots.get(sample_uid)
        if not slot:
            if len(available_slots) == 0:
                # Maybe next analysis is from a sample with a slot assigned
                continue

            # Pop next available slot
            slot = available_slots.pop()

        # Keep track of the slot where analyses from this sample must live
        samples_slots[sample_uid] = slot

        # Keep track of the analyses to add
        analysis_info = {
            "analysis": analysis,
            "sample_uid": sample_uid,
            "sample_id": _api.get_id(sample),
            "slot": slot,
        }
        new_analyses.append(analysis_info)

    if not new_analyses:
        # No analyses to add
        return

    # No need to sort slots for analyses with a pre-existing sample/slot
    with_samp = filter(lambda a: a["sample_uid"] in existing, new_analyses)
    analyses_slots = map(lambda s: (s["analysis"], s["slot"]), with_samp)

    # Re-sort slots for analyses without a pre-existing sample/slot
    # Analyses retrieved from database are sorted by priority, but we want them
    # to be displayed in natural order in the worksheet
    without_samp = filter(lambda a: a not in with_samp, new_analyses)
    # Sort the items by sample id
    without_samp.sort(key=lambda a: a["sample_id"])
    # Extract the list of analyses (sorted by sample id)
    without_samp_analyses = map(lambda a: a["analysis"], without_samp)
    # Extract the list of assigned slots and sort them in natural order
    without_samp_slots = sorted(map(lambda a: a["slot"], without_samp))
    # Generate the tuple (analysis, slot)
    without_samp_slots = zip(without_samp_analyses, without_samp_slots)
    # Append to those non sorted because of pre-existing slots
    analyses_slots.extend(without_samp_slots)

    if api.is_queue_ready("task_assign_analyses"):
        # Queue the assignment of analyses
        analyses, slots = zip(*analyses_slots)

        # Be sure that nobody else other than us is applying a template and add
        # some delay to prevent the consumers to start processing while the
        # life-cycle of current request has not yet finished
        kwargs = {"unique": True, "delay": 5}
        api.add_assign_task(self, analyses=analyses, slots=slots, **kwargs)

        # Reindex the worksheet to update the WorksheetTemplate meta column
        self.reindexObject()
        return

    # Queue is not ready, add the analyses as usual
    map(lambda a: self.addAnalysis(a[0], a[1]), analyses_slots)


def addAnalyses(self, analyses):  # noqa non-lowercase func name
    """Adds a collection of analyses to the Worksheet at once
    """
    to_queue = list()
    queue_enabled = api.is_queue_ready("task_assign_analyses")
    for num, analysis in enumerate(analyses):
        analysis = _api.get_object(analysis)
        if not queue_enabled:
            self.addAnalysis(analysis)
        elif not IRequestAnalysis.providedBy(analysis):
            self.addAnalysis(analysis)
        else:
            to_queue.append(analysis)

    # Add them to the queue
    if to_queue:
        api.add_assign_task(self, analyses=to_queue)
