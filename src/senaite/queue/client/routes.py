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

import time
from senaite.jsonapi import request as req
from senaite.jsonapi.v1 import add_route
from senaite.queue import api
from senaite.queue import logger
from senaite.queue.client import consumer
from senaite.queue.interfaces import IOfflineClientQueueUtility
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.request import fail
from senaite.queue.request import get_summary
from senaite.queue.request import handle_queue_errors
from zope.component import queryAdapter

from bika.lims import api as capi
from bika.lims.interfaces import IWorksheet
from zope.component import getUtility


@add_route("/queue_consumer/consume",
           "senaite.queue.consumer.consume", methods=["GET", "POST"])
@handle_queue_errors
def consume(context, request):
    """Endpoint to handle the consumption of a queued task, if any
    """
    # disable CSRF
    req.disable_csrf_protection()

    # start the consumer
    msg = consumer.consume_task()
    return get_summary(msg, "consume")


@add_route("/queue_consumer/process",
           "senaite.queue.consumer.process", methods=["GET", "POST"])
@add_route("/queue_consumer/process/<string:taskuid>",
           "senaite.queue.consumer.process", methods=["GET", "POST"])
@handle_queue_errors
def process(context, request, taskuid=None):
    """Processes the task passed-in
    """
    # disable CSRF
    req.disable_csrf_protection()

    # Maybe the task uid has been sent via POST
    taskuid = taskuid or req.get_json().get("taskuid")

    # Get the task
    task = get_task(taskuid)
    if task.username != capi.get_current_user().id:
        # 403 Authenticated, but user does not have access to the resource
        fail(403, "Forbidden")

    # Process
    t0 = time.time()
    task_context = task.get_context()
    if not task_context:
        fail(500, "Internal Server Error. Task's context not available")

    # Get the adapter able to process this specific type of task
    adapter = queryAdapter(task_context, IQueuedTaskAdapter, name=task.name)
    if not adapter:
        fail(501, "Not implemented. No adapter for {}".format(task.name))

    logger.info("Processing task {}: '{}' for '{}' ({}) ...".format(
        task.task_short_uid, task.name, capi.get_id(task_context),
        task.context_uid))

    # If the task refers to a worksheet, inject (ws_id) in params to make
    # sure guards (assign, unassign) return True
    if IWorksheet.providedBy(task_context):
        request = capi.get_request()
        request.set("ws_uid", capi.get_uid(task_context))

    # Process the task
    adapter.process(task)

    # Sleep a bit for minimum effect against userland threads
    # Better to have a transaction conflict here than in userland
    min_seconds = task.get("min_seconds", 3)
    while time.time() - t0 < min_seconds:
        time.sleep(0.5)

    return get_summary("Processed: {}".format(task.task_short_uid), "process")


@add_route("/queue_client/done", "senaite.queue.client.done", methods=["POST"])
@handle_queue_errors
def done(context, request):
    """Endpoint to notify that a task has been processed
    """
    return handle_server_notification(req.get_json(), "done")


@add_route("/queue_client/fail", "senaite.queue.client.fail", methods=["POST"])
@handle_queue_errors
def fail(context, request):
    """Endpoint to notify that a task has been discarded
    """
    return handle_server_notification(req.get_json(), "fail")


@add_route("/queue_client/delete", "senaite.queue.client.delete", methods=["POST"])
@handle_queue_errors
def delete(context, request):
    """Endpoint to notify that a task has been deleted
    """
    return handle_server_notification(req.get_json(), "delete")


def handle_server_notification(req_data, action):
    """Handles notifications received about tasks and queue status
    """
    task_uid = req_data.get("taskuid")
    senders = req_data.get("senders")

    # Get our cache pool utility
    utility = getUtility(IOfflineClientQueueUtility)

    # Remove the task
    func = utility.getattr(action)
    func(task_uid)

    # Add our friends, we might need them if server is stopped or idle
    utility.add_senders(senders)

    return get_summary("notified", action)


def get_task(task_uid):
    """Resolves the task for the given task uid
    """
    if not capi.is_uid(task_uid) and task_uid != "0":
        # 400 Bad Request, wrong task uid
        fail(400, "Bad Request. Task uid empty or no valid format")

    task = api.get_queue().get_task(task_uid)
    if not task:
        fail(404, "Task not found: {}".format(task_uid))

    if not capi.is_uid(task.context_uid):
        fail(500, "Internal Server Error. Task's context uid is not valid")

    return task
