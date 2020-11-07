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
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.request import fail as _fail
from senaite.queue.request import get_message_summary
from senaite.queue.request import handle_queue_errors
from zope.component import queryAdapter

from bika.lims import api as capi
from bika.lims.interfaces import IWorksheet


@add_route("/queue_consumer/consume",
           "senaite.queue.consumer.consume", methods=["GET", "POST"])
@handle_queue_errors
def consume(context, request):  # noqa
    """Endpoint to handle the consumption of a queued task, if any
    """
    # disable CSRF
    req.disable_csrf_protection()

    # start the consumer
    msg = consumer.consume_task()
    return get_message_summary(msg, "consumer.consume")


@add_route("/queue_consumer/process",
           "senaite.queue.consumer.process", methods=["GET", "POST"])
@add_route("/queue_consumer/process/<string:task_uid>",
           "senaite.queue.consumer.process", methods=["GET", "POST"])
@handle_queue_errors
def process(context, request, task_uid=None):  # noqa
    """Processes the task passed-in
    """
    # disable CSRF
    req.disable_csrf_protection()

    # Maybe the task uid has been sent via POST
    task_uid = task_uid or req.get_json().get("task_uid")

    # Get the task
    task = get_task(task_uid)
    if task.username != capi.get_current_user().id:
        # 403 Authenticated, but user does not have access to the resource
        _fail(403)

    # Process
    t0 = time.time()
    task_context = task.get_context()
    if not task_context:
        _fail(500, "Task's context is not available")

    # Get the adapter able to process this specific type of task
    adapter = queryAdapter(task_context, IQueuedTaskAdapter, name=task.name)
    if not adapter:
        _fail(501, "No adapter found for {}".format(task.name))

    logger.info("Processing task {}: '{}' for '{}' ({}) ...".format(
        task.task_short_uid, task.name, capi.get_id(task_context),
        task.context_uid))

    # If the task refers to a worksheet, inject (ws_id) in params to make
    # sure guards (assign, un-assign) return True
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

    msg = "Processed: {}".format(task.task_short_uid)
    return get_message_summary(msg, "consumer.process")


def get_task(task_uid):
    """Resolves the task for the given task uid
    """
    if not capi.is_uid(task_uid) or task_uid == "0":
        # 400 Bad Request, wrong task uid
        _fail(412, "Task uid empty or no valid format")

    task = api.get_queue().get_task(task_uid)
    if not task:
        _fail(404, "Task {}".format(task_uid))

    if not capi.is_uid(task.context_uid):
        _fail(500, "Task's context uid is not valid")

    return task
