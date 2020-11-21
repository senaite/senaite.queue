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

from senaite.jsonapi import request as req
from senaite.jsonapi.v1 import add_route
from senaite.queue import api as qapi
from senaite.queue import logger
from senaite.queue.queue import get_max_retries
from senaite.queue.queue import get_task_uid
from senaite.queue.queue import is_task
from senaite.queue.queue import to_task
from senaite.queue.request import fail as _fail
from senaite.queue.request import get_list_summary
from senaite.queue.request import get_message_summary
from senaite.queue.request import get_task_info
from senaite.queue.request import get_tasks_summary
from senaite.queue.request import get_post_zeo
from senaite.queue.request import handle_queue_errors

from bika.lims import api


def check_server(func):
    """Decorator that checks the current client is configured to act as server
    """
    def wrapper(*args, **kwargs):
        if not qapi.is_queue_server():
            _fail(405, "Not a Queue Server")
        return func(*args, **kwargs)
    return wrapper


@add_route("/queue_server/tasks",
           "senaite.queue.server.tasks", methods=["GET", "POST"])
@add_route("/queue_server/tasks/<string:status>",
           "senaite.queue.server.tasks", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def tasks(context, request, status=None):  # noqa
    """Returns a JSON representation of the tasks from the queue
    """
    # Maybe the status has been sent via POST
    request_data = req.get_json()
    status = status or request_data.get("status", [])
    since = request_data.get("since", 0)

    # Get the tasks
    items = qapi.get_queue().get_tasks(status)

    # Skip ghosts unless explicitly asked
    if "ghost" not in status:
        items = filter(lambda t: not t.get("ghost"), items)

    # Skip older
    items = filter(lambda t: t.created > since, items)

    # Convert to the dict representation
    complete = request_data.get("complete") or False
    summary = get_tasks_summary(list(items), "server.tasks", complete=complete)

    # Update the summary with the created time of oldest task
    summary.update({
        "since_time": qapi.get_queue().get_since_time()
    })
    return summary


@add_route("/queue_server/diff",
           "senaite.queue.server.diff", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def diff(context, request):
    request_data = req.get_json()
    status = request_data.get("status", [])
    client_uids = request_data.get("uids", [])
    client_uids = filter(api.is_uid, client_uids)

    # Get the tasks
    items = qapi.get_queue().get_tasks(status)

    # Keep track of the uids the client has to remove
    server_uids = map(lambda t: t.task_uid, items)
    stale_uids = filter(lambda uid: uid not in server_uids, client_uids)

    def keep(task):
        # Skip ghosts unless explicitly asked
        if "ghost" not in status:
            if task.get("ghost"):
                return False

        # Always include tasks that are running (client might have this task
        # already, but in queued status)
        if task.status in "running":
            return True

        # Skip the task if client has it
        return task.task_uid not in client_uids

    # Keep the tasks that matter
    items = filter(keep, items)

    # Convert to the dict representation
    complete = request_data.get("complete") or False
    summary = get_tasks_summary(list(items), "server.diff", complete=complete)

    # Update the summary with the uids the client has to remove
    summary.update({
        "stale": stale_uids,
        # TODO Implement unknowns
        "unknown": []
    })
    return summary


@add_route("/queue_server/uids",
           "senaite.queue.server.uids", methods=["GET", "POST"])
@add_route("/queue_server/uids/<string:status>",
           "senaite.queue.server.uids", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def uids(context, request, status=None):  # noqa
    """Returns a JSON representation of the uids from queued objects
    """
    # Maybe the status has been sent via POST
    request_data = req.get_json()
    status = status or request_data.get("status")

    # Get the uids from queued objects
    items = qapi.get_queue().get_uids(status)

    # Convert to the dict representation
    return get_list_summary(items, "server.uids")


@add_route("/queue_server/search",
           "senaite.queue.server.search", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def search(context, request):  # noqa
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
    items = qapi.get_queue().get_tasks_for(uid, name=name)
    return get_tasks_summary(items, "server.search", complete=complete)


@add_route("/queue_server/<string(length=32):task_uid>",
           "senaite.queue.server.get", methods=["GET", "POST"])
@handle_queue_errors
def get(context, request, task_uid):  # noqa
    """Returns a JSON representation of the task with the specified task uid
    """
    # Get the task
    task = get_task(task_uid)

    # Digest the task and return
    zeo = get_post_zeo()
    task_uid = get_task_uid(task, default="none")
    logger.info("::server.get: {} [{}]".format(task_uid, zeo))
    return get_task_info(task, complete=True)


@add_route("/queue_server/add", "senaite.queue.server.add", methods=["POST"])
@check_server
@handle_queue_errors
def add(context, request):  # noqa
    """Adds a new task to the queue server
    """
    # Extract the task(s) from the request
    raw_tasks = req.get_request_data()

    # Convert raw task(s) to QueueTask object(s)
    items = map(to_task, raw_tasks)
    valid = map(is_task, items)
    if not all(valid):
        _fail(406, "No valid task(s)")

    # Add the task(s) to the queue
    map(qapi.get_queue().add, items)

    # Return the process summary
    return get_tasks_summary(items, "server.add", complete=False)


@add_route("/queue_server/pop", "senaite.queue.server.pop", methods=["POST"])
@check_server
@handle_queue_errors
def pop(context, request):  # noqa
    """Pops the next task from the queue, if any. Popped task is no longer
    available in the queued tasks pool, but added in the running tasks pool
    """
    # Get the consumer ID
    consumer_id = req.get_json().get("consumer_id")
    if not is_consumer_id(consumer_id):
        _fail(428, "No valid consumer id")

    # Pop the task from the queue
    task = qapi.get_queue().pop(consumer_id)

    # Return the task info
    task_uid = get_task_uid(task, default="<empty>")
    logger.info("::server.pop: {} [{}]".format(task_uid, consumer_id))
    return get_task_info(task, complete=True)


@add_route("/queue_server/done", "senaite.queue.server.done", methods=["POST"])
@check_server
@handle_queue_errors
def done(context, request):  # noqa
    """Acknowledge the task has been successfully processed. Task is removed
    from the running tasks pool and returned
    """
    # Get the task uid
    task_uid = req.get_json().get("task_uid")

    # Get the task
    task = get_task(task_uid)
    if task.status not in ["running", ]:
        _fail(412, "Task is not running")

    # Notify the queue
    qapi.get_queue().done(task)

    # Return the process summary
    msg = "Task done: {}".format(task_uid)
    task_info = {"task": get_task_info(task)}
    return get_message_summary(msg, "server.done", **task_info)


@add_route("/queue_server/fail", "senaite.queue.server.fail", methods=["POST"])
@check_server
@handle_queue_errors
def fail(context, request):  # noqa
    """Acknowledge the task has NOT been successfully processed. Task is
    moved from running tasks to failed or re-queued and returned
    """
    # Get the task uid
    request_data = req.get_json()
    task_uid = request_data.get("task_uid")
    error_message = request_data.get("error_message")

    # Get the task
    task = get_task(task_uid)
    if task.status not in ["running", ]:
        _fail(412, "Task is not running")

    # Notify the queue
    qapi.get_queue().fail(task, error_message=error_message)

    # Return the process summary
    msg = "Task failed: {}".format(task_uid)
    task_info = {"task": get_task_info(task)}
    return get_message_summary(msg, "server.fail", **task_info)


@add_route("/queue_server/timeout", "senaite.queue.server.timeout",
           methods=["POST"])
@check_server
@handle_queue_errors
def timeout(context, request):  # noqa
    """The task timed out
    """
    # Get the task uid
    request_data = req.get_json()
    task_uid = request_data.get("task_uid")

    # Get the task
    task = get_task(task_uid)
    if task.status not in ["running", ]:
        _fail(412, "Task is not running")

    # Notify the queue
    qapi.get_queue().timeout(task)

    # Return the process summary
    task_info = {"task": get_task_info(task)}
    return get_message_summary(task_uid, "server.timeout", **task_info)


@add_route("/queue_server/requeue",
           "senaite.queue.server.requeue", methods=["POST"])
@add_route("/queue_server/requeue/<string(length=32):task_uid>",
           "senaite.queue.server.requeue", methods=["GET", "POST"])
@check_server
@handle_queue_errors
def requeue(context, request, task_uid=None):  # noqa
    """Requeue the task. Task is moved from either failed or running pool to
    the queued tasks pool and returned
    """
    # Maybe the task uid has been sent via POST
    task_uid = task_uid or req.get_json().get("task_uid")

    # Get the task
    task = get_task(task_uid)

    # Remove, restore max number of retries and re-add the task
    task.retries = get_max_retries()
    queue = qapi.get_queue()
    queue.delete(task_uid)
    queue.add(task)

    # Return the process summary
    msg = "Task re-queued: {}".format(task_uid)
    task_info = {"task": get_task_info(task)}
    return get_message_summary(msg, "server.requeue", **task_info)


@add_route("/queue_server/delete", "senaite.queue.server.delete",
           methods=["POST"])
@check_server
@handle_queue_errors
def delete(context, request):  # noqa
    """Removes the task from the queue
    """
    # Get the task uid
    task_uid = req.get_json().get("task_uid")

    # Get the task
    task = get_task(task_uid)
    qapi.get_queue().delete(task.task_uid)

    # Return the process summary
    msg = "Task deleted: {}".format(task_uid)
    task_info = {"task": get_task_info(task)}
    return get_message_summary(msg, "server.delete", **task_info)


def get_task(task_uid):
    """Resolves the task for the given task uid
    """
    if not api.is_uid(task_uid) or task_uid == "0":
        # 400 Bad Request, wrong task uid
        _fail(412, "Task uid empty or no valid format")

    task = qapi.get_queue().get_task(task_uid)
    if not task:
        _fail(404, "Task {}".format(task_uid))

    return task


def is_consumer_id(consumer_id):
    if not consumer_id:
        return False
    # TODO Implement
    return len(consumer_id) >= 4
