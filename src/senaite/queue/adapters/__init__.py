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
# Copyright 2019-2021 by it's authors.
# Some rights reserved, see README and LICENSE.

from Products.Archetypes.interfaces.base import IBaseObject
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.queue import get_chunks_for
from zope.component import adapts
from zope.interface import implements

from bika.lims import api as _api
from bika.lims.interfaces import IWorksheet
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
        chunks = get_chunks_for(task)

        # Process the first chunk
        objects = map(_api.get_object_by_uid, chunks[0])
        map(lambda obj: doActionFor(obj, task["action"]), objects)

        # Add remaining objects to the queue and keep properties
        due = chunks[1]
        if due:
            api.add_copy(task, context=self.context, uids=due, unique=False)


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

        uids = task.get("uids", [])
        slots = task.get("slots", [])

        # Sanitize the slots list and pad with empties
        slots = map(lambda s: _api.to_int(s, None) or "", slots)
        slots += [""] * abs(len(uids) - len(slots))

        # Sort analyses so those with an assigned slot are added first
        # Note numeric values get precedence over strings, empty strings here
        uids_slots = zip(uids, slots)
        uids_slots = sorted(uids_slots, key=lambda i: i[1])

        # Remove those with no valid uids
        uids_slots = filter(lambda us: _api.is_uid(us[0]), uids_slots)

        # Remove duplicate uids while keeping the order
        seen = set()
        uids_slots = filter(lambda us: not (us[0] in seen or seen.add(us[0])),
                            uids_slots)

        # Remove uids that are already in the worksheet (just in case)
        layout = filter(None, worksheet.getLayout() or [])
        existing = map(lambda r: r.get("analysis_uid"), layout)
        uids_slots = filter(lambda us: us[0] not in existing, uids_slots)

        # If there are too many objects to process, split them in chunks to
        # prevent the task to take too much time to complete
        chunks = get_chunks_for(task, items=uids_slots)

        # Process the first chunk
        for uid, slot in chunks[0]:
            # Add the analysis
            slot = slot or None
            analysis = _api.get_object_by_uid(uid)
            worksheet.addAnalysis(analysis, slot)

        # Reindex the worksheet
        worksheet.reindexObject()

        if chunks[1]:
            # Unpack the remaining analyses-slots and add them to the queue
            uids, slots = zip(*chunks[1])
            api.add_assign_task(worksheet, analyses=uids, slots=slots)


class QueueObjectSecurityAdapter(object):
    """Adapter in charge of doing a reindexObjectSecurity recursively
    """
    implements(IQueuedTaskAdapter)
    adapts(IBaseObject)

    def __init__(self, context):
        self.context = context

    def process(self, task):
        """Process the task from the queue
        """
        # Reindex the objects
        uids = task["uids"]
        if not uids:
            return

        # Get the UID of the oldest object to reindex
        oldest_uid = uids[-1]

        # UID of the top-level node from the tree hierarchy to reindex
        top_uid = task.get("top_uid", oldest_uid)

        # Reindex the objects
        map(self.reindex_security, uids)

        if top_uid not in uids:
            # We have not processed yet the top-level node, keep reindexing
            # further objects from the hierarchy tree
            kwargs = {
                "top_uid": top_uid,
                "priority": task.priority,
            }
            api.add_reindex_obj_security_task(oldest_uid, **kwargs)

    def reindex_security(self, uid):
        """Reindex object security for the object passed-in
        """
        obj = _api.get_object(uid, None)
        if obj:
            obj_path = _api.get_path(obj)
            logger.info("Reindex security: {}".format(obj_path))
            obj.reindexObject(idxs=["allowedRolesAndUsers", ])
