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

from senaite.queue import get_action_task_name, get_chunk_size
from senaite.queue.interfaces import IQueued
from senaite.queue.storage import ActionQueueStorage
from senaite.queue.storage import QueueStorageTool
from senaite.queue.storage import WorksheetQueueStorage
from zope.interface import alsoProvides


def queue_action(context, request, action, objects, chunk_size=None):
    """
    Adds a given action to the queue for async processing
    :param context: the object where the tasks are handled
    :param request: httprequest
    :param action: action to be performed
    :param objects: objects, brains or uids the action to be taken against to
    :param chunk_size: max number of objects to process in a single batch
    :return: whether the action was successfully queued or not
    """
    task_name = get_action_task_name(action)
    chunk_size = chunk_size or get_chunk_size(task_name)

    # Assign the uids and action to context's annotation
    storage = ActionQueueStorage(context)
    storage.queue(objects, chunk_size=chunk_size, action=action)

    # Add to the generic queue
    return queue_task(task_name, request, context)


def queue_assign_analyses(worksheet, request, uids, slots, chunk_size=None, wst_uid=None):
    """Adds analyses to the queue for analyses assignment
    """
    task_name = "task_assign_analyses"
    chunk_size = chunk_size or get_chunk_size(task_name)

    # Assign the uids to Worksheet annotation
    storage = WorksheetQueueStorage(worksheet)
    storage.queue(uids, chunk_size=chunk_size, slots=slots, wst_uid=wst_uid)

    # Add to the generic queue
    return queue_task(task_name, request, worksheet)


def queue_task(name, request, context):
    """Adds a task to general queue storage
    """
    queue = QueueStorageTool()
    queued = queue.append(name, request, context)

    # Mark context as queued and reindex
    if not IQueued.providedBy(context):
        alsoProvides(context, IQueued)
        context.reindexObject(idxs="is_queued")
    return queued
