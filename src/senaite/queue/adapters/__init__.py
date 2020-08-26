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

from Products.Archetypes.interfaces.base import IBaseObject
from bika.lims import api as _api
from senaite.queue import api
from senaite.queue.interfaces import IQueuedTaskAdapter
from zope.component import adapts
from zope.interface import implements

from bika.lims.interfaces import IWorksheet
from bika.lims.interfaces.analysis import IRequestAnalysis
from bika.lims.workflow import doActionFor


class QueuedActionTaskAdapter(object):
    """Adapter for generic transitions
    """
    implements(IQueuedTaskAdapter)
    adapts(IBaseObject)

    def __init__(self, context):
        self.context = context

    def process(self, task):
        """Transition the objects from the task
        """
        # If there are too many objects to process, split them in chunks to
        # prevent the task to take too much time to complete
        chunks = api.get_chunks(task.name, task["uids"])

        # Process the first chunk
        objects = map(_api.get_object_by_uid, chunks[0])
        map(lambda obj: doActionFor(obj, task["action"]), objects)

        # Add remaining objects to the queue
        api.queue_action(chunks[1], task["action"], self.context)


class QueuedAssignAnalysesTaskAdapter(object):
    """Adapter for the assignment of analyses to a worksheet
    """
    implements(IQueuedTaskAdapter)
    adapts(IWorksheet)

    def __init__(self, context):
        self.context = context

    def process(self, task):
        """Transition the objects from the task
        """
        # The worksheet is the context
        worksheet = self.context

        # Get the Worksheet Template to use
        wst_uid = task.get("wst_uid")
        wst = _api.is_uid(wst_uid) and _api.get_object(wst_uid) or None

        # If there are too many objects to process, split them in chunks to
        # prevent the task to take too much time to complete
        chunks = api.get_chunks(task.name, task["uids"])

        # Process the first chunk
        analyses = map(_api.get_object_by_uid, chunks[0])

        # TODO Only interested in routine analyses for now
        analyses = filter(IRequestAnalysis.providedBy, analyses)

        # Calculate the slot where each analysis has to be stored and add
        for analysis in analyses:

            # Get the suitable slot for this analysis
            slot = self.get_slot_for(analysis, wst)

            # Add the analysis
            worksheet.addAnalysis(analysis, slot)

        # Add remaining objects to the queue
        api.queue_assign_analyses(worksheet, chunks[1], ws_template=wst_uid)

    def get_slot_for(self, analysis, wst=None, default=None):
        # The worksheet is the context
        worksheet = self.context

        # Does the worksheet contains the Sample the analysis belongs to?
        slot = self.get_container_slot_for(analysis.getRequestUID())
        if slot is not None:
            return slot

        # If no worksheet template defined, just use default's
        if not wst:
            return default

        # Get the slots for routine analyses defined in the wst
        slots = self.get_slots_by_type(wst, "a")

        # Get the slots from the worksheet that are already taken
        taken = worksheet.get_slot_positions(type="all")

        # Boil-out taken slots
        slots = filter(lambda slot: slot not in taken, slots)
        if not slots:
            return default

        # Slots are sorted from lowest to highest position, so is fine to
        # pick the first available slot
        return slots[0]

    def get_container_slot_for(self, container_uid):
        """Returns the slot occupied by the specified container
        """
        layout = self.context.getLayout()
        slot = filter(lambda sl: sl["container_uid"] == container_uid, layout)
        return slot and _api.to_int(slot[0].get("position")) or None

    def get_slots_by_type(self, worksheet_template_or_uid, type="a"):
        """Return the slots of the worksheet template by type
        """
        worksheet_template = _api.get_object(worksheet_template_or_uid)
        layout = worksheet_template.getLayout()
        slots = filter(lambda slot: slot["type"] == type, layout)
        slots = map(lambda slot: int(slot["pos"]), slots)
        return sorted(set(slots))
