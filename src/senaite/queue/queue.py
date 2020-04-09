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
from senaite.queue.storage import ActionQueueStorage
from senaite.queue.storage import QueueStorageTool
from senaite.queue.storage import QueueTask
from senaite.queue.storage import WorksheetQueueStorage

from bika.lims.utils import tmpID


def queue_action(context, request, action, objects):
    """
    Adds a given action to the queue for async processing
    :param context: the object where the tasks are handled
    :param request: httprequest
    :param action: action to be performed
    :param objects: objects, brains or uids the action to be taken against to
    :return: whether the action was successfully queued or not
    """
    if not objects:
        return False

    # Assign the uids and action to context's annotation
    storage = ActionQueueStorage(context)
    storage.queue(objects, action=action)

    # Add to the generic queue
    task_name = api.get_action_task_name(action)
    return queue_task(task_name, request, context)


def queue_assign_analyses(worksheet, request, uids, slots, wst_uid=None):
    """Adds analyses to the queue for analyses assignment
    """
    # Assign the uids to Worksheet annotation
    storage = WorksheetQueueStorage(worksheet)
    storage.queue(uids, slots=slots, wst_uid=wst_uid)

    # Add to the generic queue
    return queue_task("task_assign_analyses", request, worksheet)


def queue_task(name, request, context, username=None, unique=False,
               priority=10):
    """Adds a task to general queue storage
    :param name: the name of the task
    :param request: the HTTPRequest
    :param context: the context the task is bound to
    :param username: user responsible of the task. Fallback to request's user
    :param unique: whether if only one task for the given name and context
    must be added. If True, the task will only be added if there is no other
    task with same name and context
    :param priority: priority of this task over others. Lower values have more
    priority over higher values
    """
    if not name:
        # Name is mandatory
        return False

    if unique and in_queue(context, name=name):
        # The task is already in the queue, do not add
        return False

    queue = QueueStorageTool()
    task = QueueTask(name, request, context, tmpID(), priority=priority)
    if username:
        task.username = username
    return queue.append(task)


def in_queue(context, name=None):
    """Returns whether a task for the given name and context is in the queue
    """
    return QueueStorageTool().contains_tasks_for(context, name=name)
