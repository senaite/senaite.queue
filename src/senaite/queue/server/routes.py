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

import requests

from senaite.jsonapi import api as japi
from senaite.jsonapi import request as req
from senaite.jsonapi.v1 import add_route
from senaite.queue import api as qapi
from senaite.queue.client.utility import QueueAuth
from senaite.queue.queue import is_task
from senaite.queue.queue import to_task
from senaite.queue.request import fail as _fail
from senaite.queue.request import handle_queue_errors

from bika.lims import api
from senaite.queue import logger


_marker = object()


def check_server(func):
    """Decorator that checks the current client is configured to act as server
    """
    def wrapper(*args, **kwargs):
        logger.info(">>>>> {}".format(api.get_request().URL))
        if not qapi.is_queue_server():
            _fail(400, "Bad Request. Not a Queue Server")
        return func(*args, **kwargs)
    return wrapper


def notify(host, endpoint, task_uid):
    """Sends a notification to the client's queue endpoint for the task uid if
    the host is not the same as us. It also includes status information about
    the Server Queue in the payload, such as the list of queue clients that at
    least have sent one task to the server queue.
    Delivery is not granted
    """
    current_url = api.get_url(api.get_portal())
    if current_url.lower().startswith(host.lower()):
        # No need to notify myself
        return

    client_part = "@@API/senaite/v1/queue_client"
    parts = [host, client_part, endpoint]
    if not all(parts):
        return

    # Include the zeo client friends that are also adding tasks
    # This is used by clients to keep them in sync for the hypothetical case the
    # queue server is stopped or enters into in idle/offline status. Clients
    # will then be able to operate coordinated in read-only mode
    senders = qapi.get_queue().get_senders()
    senders = filter(lambda f: f != host, senders)
    payload = {
        "taskuid": task_uid,
        "senders": senders
    }
    try:
        auth = QueueAuth(api.get_current_user().id)
        requests.post("/".join(parts), json=payload, auth=auth, timeout=1)
    except:
        # Delivery is not granted
        pass


@add_route("/queue_server/tasks",
           "senaite.queue.server.tasks", methods=["GET", "POST"])
@add_route("/queue_server/tasks/<string:status>",
           "senaite.queue.server.tasks", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def tasks(context, request, status=None):
    """Returns a JSON representation of the tasks from the queue
    """
    # Maybe the status has been sent via POST
    request_data = req.get_json()
    status = status or request_data.get("status")

    # Get the tasks
    tasks = qapi.get_queue().get_tasks(status)

    # Convert to the dict representation
    complete = request_data.get("complete") or False
    return get_summary(list(tasks), "tasks", complete=complete)


@add_route("/queue_server/uids",
           "senaite.queue.server.uids", methods=["GET", "POST"])
@add_route("/queue_server/uids/<string:status>",
           "senaite.queue.server.uids", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def uids(context, request, status=None):
    """Returns a JSON representation of the uids from queued objects
    """
    # Maybe the status has been sent via POST
    request_data = req.get_json()
    status = status or request_data.get("status")

    # Get the uids from queued obejcts
    uids = qapi.get_queue().get_uids(status)

    # Convert to the dict representation
    return get_summary(uids, "uids", converter=None)


@add_route("/queue_server/search",
           "senaite.queue.server.search", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def search(context, request):
    """Performs a search
    """
    # Get the search criteria
    query = req.get_request_data()
    if isinstance(query, (list, tuple)):
        query = query[0]
    elif not isinstance(query, dict):
        query = {}

    uid = query.get("uid")
    name = query.get("name")
    complete = query.get("complete", False)

    # Get the tasks from the utility
    tasks = qapi.get_queue().get_tasks_for(uid, name=name)
    return get_summary(list(tasks), "search", complete=complete)


@add_route("/queue_server/<string(length=32):taskuid>",
           "senaite.queue.server.get", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def get(context, request, taskuid):
    """Returns a JSON representation of the task with the specified task uid
    """
    # Get the task
    task = get_task(taskuid)

    # Digest the task and return
    return get_info(task)


@add_route("/queue_server/add", "senaite.queue.server.add", methods=["POST"])
@check_server
@handle_queue_errors
def add(context, request):
    """Adds a new task to the queue server
    """
    # Extract the task(s) from the request
    raw_tasks = req.get_request_data()

    # Convert raw task(s) to QueueTask object(s)
    tasks = map(to_task, raw_tasks)
    valid = map(is_task, tasks)
    if not all(valid):
        _fail(400, "Bad Request. No valid task(s)")

    # Add the task(s) to the queue
    map(qapi.get_queue().add, tasks)

    # Return the process summary
    return get_summary(tasks, "add")


@add_route("/queue_server/pop", "senaite.queue.server.pop", methods=["POST"])
@check_server
@handle_queue_errors
def pop(context, request):
    """Pops the next task from the queue, if any. Popped task is no longer
    available in the queued tasks pool, but added in the running tasks pool
    """
    # Get the consumer ID
    consumer_id = req.get_json().get("consumerid")
    if not is_consumer_id(consumer_id):
        _fail(400, "Bad Request. No valid consumer id")

    # Pop the task from the queue
    task = qapi.get_queue().pop(consumer_id)

    # Return the task info
    return get_info(task)


@add_route("/queue_server/done", "senaite.queue.server.done", methods=["POST"])
@check_server
@handle_queue_errors
def done(context, request):
    """Acknowledge the task has been successfully processed. Task is removed
    from the running tasks pool and returned
    """
    # Get the task uid
    task_uid = req.get_json().get("taskuid")

    # Get the task
    task = get_task(task_uid)
    if task.status not in ["running", ]:
        _fail(400, "Bad Request. Task is not running")

    # Notify the queue
    qapi.get_queue().done(task)

    # Notify the original sender
    notify(task.sender, "done", task.task_uid)

    # Return the process summary
    return get_summary(task, "done")


@add_route("/queue_server/fail", "senaite.queue.server.fail", methods=["POST"])
@check_server
@handle_queue_errors
def fail(context, request):
    """Acknowledge the task has NOT been successfully processed. Task is
    moved from running tasks to failed or requeued and returned
    """
    # Get the task uid
    request_data = req.get_json()
    task_uid = request_data.get("taskuid")
    error_message = request_data.get("error_message")

    # Get the task
    task = get_task(task_uid)
    if task.status not in ["running", ]:
        _fail(400, "Bad Request. Task is not running")

    # Notify the queue
    qapi.get_queue().fail(task, error_message=error_message)

    # Notify the original sender if the task has been discarded
    if task.status in ["failed"]:
        notify(task.sender, "fail", task.task_uid)

    # Return the process summary
    return get_summary(task, "fail")


@add_route("/queue_server/requeue",
           "senaite.queue.server.requeue", methods=["POST"])
@add_route("/queue_server/requeue/<string(length=32):taskuid>",
           "senaite.queue.server.requeue", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def requeue(context, request, taskuid=None):
    """Requeue the task. Task is moved from either failed or running pool to
    the queued tasks pool and returned
    """
    # Maybe the task uid has been sent via POST
    taskuid = taskuid or req.get_json().get("taskuid")

    # Get the task
    task = get_task(taskuid)

    # Remove, restore max number of retries and re-add the task
    task.retries = qapi.get_max_retries()
    queue = qapi.get_queue()
    queue.delete(taskuid)
    queue.add(task)

    # Return the process summary
    return get_summary(task, "requeue")


@add_route("/queue_server/delete", "senaite.queue.server.delete", methods=["POST"])
@check_server
@handle_queue_errors
def delete(context, request):
    """Removes the task from the queue
    """
    # Get the task uid
    task_uid = req.get_json().get("taskuid")

    # Get the task
    task = get_task(task_uid)
    qapi.get_queue().delete(task.task_uid)

    # Notify the original sender
    notify(task.sender, "delete", task_uid)

    # Return the process summary
    return get_summary(task, "delete")


def get_summary(items, endpoint, complete=True, converter=_marker):
    items = items or []
    if not isinstance(items, (list, tuple)):
        items = [items]
    if converter is _marker:
        items = map(lambda t: get_info(t, complete=complete), items)
    elif converter and callable(converter):
        items = map(converter, items)

    return {
        "count": len(items),
        "items": items,
        "url": japi.url_for("senaite.queue.server.{}".format(endpoint))
    }


def get_task(task_uid):
    """Resolves the task for the given task uid
    """
    if not api.is_uid(task_uid) and task_uid != "0":
        # 400 Bad Request, wrong task uid
        _fail(400, "Bad Request. Task uid empty or no valid format")

    task = qapi.get_queue().get_task(task_uid)
    if not task:
        _fail(404, "Task not found: {}".format(task_uid))

    return task


def get_info(task, complete=True):
    if not task:
        return {}

    if complete:
        out_task = dict(task)
    else:
        out_task = {
            "task_uid": task.task_uid,
            "name": task.name,
            "context_uid": task.context_uid,
            "priority": task.priority,
            "status": task.status,
            "created": task.created,
            "retries": task.retries,
            "username": task.username,
        }

    base_url = api.get_url(api.get_portal())
    task_uid = task.get("task_uid")
    url = "{}/@@API/senaite/v1/queue_server/{}".format(base_url, task_uid)
    out_task.update({
        "task_url": url
    })
    return out_task


def is_consumer_id(consumer_id):
    if not consumer_id:
        return False
    # TODO Implement
    return len(consumer_id) >= 4
