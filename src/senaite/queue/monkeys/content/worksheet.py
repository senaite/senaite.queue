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
    new_sample_uids = []
    new_analyses = []

    for analysis in analyses:
        # SENAITE.QUEUE-Specific
        if api.is_queued(analysis):
            continue

        analysis = _api.get_object(analysis)

        if instrument and not analysis.isInstrumentAllowed(instrument):
            # WST's Instrument does not supports this analysis
            continue

        if method and not analysis.isMethodAllowed(method):
            # WST's method does not supports this analysis
            continue

        # Get the slot where analyses from this sample are located
        sample_uid = analysis.getRequestUID()
        slot = samples_slots.get(sample_uid)
        if not slot:
            if len(available_slots) == 0:
                # Maybe next analysis is from a sample with a slot assigned
                continue

            # Pop next available slot
            slot = available_slots.pop()

            # Feed the samples_slots
            samples_slots[sample_uid] = slot
            new_sample_uids.append(sample_uid)

        # Keep track of the analyses to add
        new_analyses.append((analysis, sample_uid))

    # Re-sort slots for new samples to display them in natural order
    new_slots = map(lambda s: samples_slots.get(s), new_sample_uids)
    sorted_slots = zip(sorted(new_sample_uids), sorted(new_slots))
    for sample_uid, slot in sorted_slots:
        samples_slots[sample_uid] = slot

    # SENAITE.QUEUE-SPECIFIC
    task_name = "task_assign_analyses"
    new_analyses = map(lambda a: (a[0], samples_slots[a[1]]), new_analyses)
    if api.is_queue_writable(task_name):
        # Queue the assignment of analyses
        analyses, slots = zip(*new_analyses)
        api.add_assign_task(self, analyses=analyses, slots=slots)

        # Reindex the worksheet to update the WorksheetTemplate meta column
        self.reindexObject()

    else:
        map(lambda a: self.addAnalysis(a[0], a[1]), new_analyses)


def addAnalyses(self, analyses):
    """Adds a collection of analyses to the Worksheet at once
    """
    to_queue = list()
    queue_enabled = api.is_queue_writable("task_assign_analyses")
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
