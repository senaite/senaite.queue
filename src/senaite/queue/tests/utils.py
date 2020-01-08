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

import transaction
from DateTime import DateTime
from senaite.queue import api
from senaite.queue.browser.views.consumer import QueueConsumerView
from senaite.queue.storage import QueueStorageTool

from bika.lims.browser.workflow import WorkflowActionHandler
from bika.lims.utils.analysisrequest import create_analysisrequest
from bika.lims.workflow import doActionFor as do_action_for


def handle_action(context, items_or_uids, action):
    """Simulates the handling of an action when multiple items from a list are
    selected and the action button is pressed
    """
    if not isinstance(items_or_uids, (list, tuple)):
        items_or_uids = [items_or_uids]
    items_or_uids = map(api.get_uid, items_or_uids)
    request = api.get_request()
    request.set("workflow_action", action)
    request.set("uids", items_or_uids)
    WorkflowActionHandler(context, request)()


def create_sample(services, client, contact, sample_type, receive=True):
    """Creates a new sample with the specified services
    """
    request = api.get_request()
    values = {
        'Client': client.UID(),
        'Contact': contact.UID(),
        'DateSampled': DateTime().strftime("%Y-%m-%d"),
        'SampleType': sample_type.UID()
    }
    service_uids = map(api.get_uid, services)
    sample = create_analysisrequest(client, request, values, service_uids)
    if receive:
        do_action_for(sample, "receive")
    return sample


def get_queue_tool():
    """Returns the queue storage tool
    """
    return QueueStorageTool()


def dispatch(request=None):
    """Triggers the Queue Dispatcher
    """
    # Do a transaction commit first. In a test environment, all happens within
    # the same request life-cycle, while in a real environment, the dispatch is
    # always called by a dedicated worker, through an independent thread.
    transaction.commit()
    portal = api.get_portal()
    if not request:
        request = api.get_request()

    # I simulate here the behavior of QueueDispatcher, haven't found any other
    # solution to deal with the fact the queue utility opens a new Thread by
    # calling requests module and nohost is not available. I need to do more
    # research on this topic....
    queue = get_queue_tool()
    if not queue.lock():
        return "Cannot lock the queue"

    # Pop the task to process
    task = queue.pop()
    request.set("tuid", task.task_uid)

    return QueueConsumerView(portal, request)()


def filter_by_state(brains_or_objects, state):
    """Filters the objects passed in by state
    """
    objs = map(api.get_object, brains_or_objects)
    return filter(lambda obj: api.get_review_status(obj) == state, objs)
