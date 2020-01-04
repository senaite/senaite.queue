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
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueued
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.queue import queue_action
from senaite.queue.queue import queue_assign_analyses
from senaite.queue.storage import ActionQueueStorage
from senaite.queue.storage import WorksheetQueueStorage
from zope.component import adapts
from zope.interface import implements
from zope.interface import noLongerProvides

from bika.lims.interfaces import IWorksheet
from bika.lims.interfaces.analysis import IRequestAnalysis
from bika.lims.workflow import doActionFor


class QueuedTaskAdapter(object):
    """Generic adapter for queued tasks
    """
    implements(IQueuedTaskAdapter)

    def __init__(self, context):
        self.context = context


class QueuedUIDsTaskAdapter(QueuedTaskAdapter):
    """Generic adapter for queued tasks with uids stored in their own storage
    """
    _storage = None

    @property
    def storage(self):
        raise NotImplementedError("Property storage not implemented")

    @property
    def uids(self):
        """uids of the objects to be transitioned
        """
        return self.storage.uids

    def flush(self, task):
        """Discards this task
        """
        self.storage.flush()


class QueuedActionTaskAdapter(QueuedUIDsTaskAdapter):
    """Adapter for generic transitions
    """
    adapts(IBaseObject)

    @property
    def storage(self):
        if not self._storage:
            self._storage = ActionQueueStorage(self.context)
        return self._storage

    @property
    def action(self):
        """Returns the id of the transition to be performed
        """
        return self.storage.action

    def process(self, task, request):
        """Transition the objects and/or queue some of them in accordance with
        the parameters defined in the task passed-in
        """
        if self.context != task.context:
            logger.error("Task's context does not match with self.context")
            return False

        # Process the first chunk
        num_objects = len(self.uids)
        chunks = api.get_chunks(task.name, self.uids)
        self.do_action(self.action, chunks[0])

        # Queue the rest
        if chunks[1]:
            # More items to process, just queue them and exit
            queue_action(self.context, request, self.action, chunks[1])
        else:
            # There are no more items to queue, all items queued for this
            # context have been transitioned already
            self.storage.flush()

        logger.info("*** Processed: {}/{}".format(len(chunks[0]), num_objects))
        return True

    def do_action(self, action, uid_or_uids):
        """Transition the object(s) for the passed-in uid(s) without delay
        """
        if isinstance(uid_or_uids, basestring):
            uid_or_uids = [uid_or_uids]

        for uid in uid_or_uids:
            obj = api.get_object_by_uid(uid, default=None)
            if not obj:
                logger.error("Object not found for UID {}".format(uid))
                return

            # Remove the marker interface to ensure the object can transition
            noLongerProvides(obj, IQueued)

            # Do the action
            current_user = api.get_current_user()
            logger.info("Action: '{}' Actor: '{}' Object: '{}'"
                        .format(action, current_user.id, obj.getId()))
            doActionFor(obj, action)


class QueuedAssignAnalysesTaskAdapter(QueuedUIDsTaskAdapter):
    """Adapter for the assignment of analyses to a worksheet
    """
    adapts(IWorksheet)

    @property
    def storage(self):
        if not self._storage:
            self._storage = WorksheetQueueStorage(self.context)
        return self._storage

    @property
    def slots(self):
        return self.storage.slots

    @property
    def wst_uid(self):
        return self.storage.wst_uid

    def process(self, task, request):
        if not self.uids:
            logger.error("No UIDs defined")
            return False

        if len(self.uids) != len(self.slots):
            logger.error("Length of uids and slots does not match")
            return False

        if self.context != task.context:
            logger.error("Task's context does not match with self.context")
            return False

        # Process the first chunk
        num_objects = len(self.uids)
        chunks = api.get_chunks(task.name, self.uids)
        self.do_assign(chunks[0], wst_uid=self.wst_uid)

        # Queue the rest
        if chunks[1]:
            # More items to process, just queue them and exit
            queue_assign_analyses(self.context, request, chunks[1], chunks[1],
                                  wst_uid=self.wst_uid)
        else:
            # There are no more items to queue, all items queued for this
            # context have been transitioned already
            self.storage.flush()

        logger.info("*** Processed: {}/{}".format(len(chunks[0]), num_objects))
        return True

    def do_assign(self, uid_or_uids, wst_uid=None):
        """Transition the object(s) for the passed-in uid(s) without delay
        """
        if not uid_or_uids:
            return

        if isinstance(uid_or_uids, basestring):
            uid_or_uids = [uid_or_uids]

        # The worksheet is the context
        worksheet = self.context

        # Get the Worksheet Template to use
        wst = api.is_uid(wst_uid) and api.get_object(wst_uid) or None

        # Get the analyses to be added. We do this way (instead of querying by
        # all UIDs) because we want to keep same order
        analyses = map(api.get_object_by_uid, uid_or_uids)

        # TODO Only interested in routine analyses for now
        analyses = filter(IRequestAnalysis.providedBy, analyses)

        # Calculate the slot where each analysis has to be stored and add
        for analysis in analyses:

            # Get the suitable slot for this analysis
            slot = self.get_slot_for(analysis, wst)

            # Remove the marker interface so the object can be transitioned
            noLongerProvides(analysis, IQueued)

            # Add the analysis
            worksheet.addAnalysis(analysis, slot)

    def get_slot_for(self, analysis, wst=None, default=None):
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
        worksheet = self.context
        layout = worksheet.getLayout()
        slot = filter(lambda sl: sl["container_uid"] == container_uid, layout)
        if len(slot) > 0:
            return api.to_int(slot[0]["position"])
        return None

    def get_slots_by_type(self, worksheet_template_or_uid, type="a"):
        worksheet_template = api.get_object(worksheet_template_or_uid)
        layout = worksheet_template.getLayout()
        slots = filter(lambda slot: slot["type"] == type, layout)
        slots = map(lambda slot: int(slot["pos"]), slots)
        return sorted(set(slots))
