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

from Acquisition import aq_base

from collections import OrderedDict

from plone import api as plone_api
from senaite.queue import IQueueUtility
from senaite.queue import is_installed
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.queue import QueueTask
from zope.component import getUtility
from zope.component import queryAdapter

from bika.lims import api as _api
from bika.lims.interfaces import IWorksheet
from bika.lims.utils import render_html_attributes


# Registry key for the default number of objects to process per task
_DEFAULT_CHUNK_SIZE_ID = "senaite.queue.default"

# Registry key for the maximum retries before a task is considered as failed
_DEFAULT_MAX_RETRIES_ID = "senaite.queue.max_retries"

# Registry key for the minimum seconds to book per task
_MIN_SECONDS_TASK_ID = "senaite.queue.min_seconds_task"


def get_queue_image(name, **kwargs):
    """Returns a well-formed image
    :param name: file name of the image
    :param kwargs: additional attributes and values
    :return: a well-formed html img
    """
    if not name:
        return ""
    attr = render_html_attributes(**kwargs)
    return '<img src="{}" {}/>'.format(get_queue_image_url(name), attr)


def get_queue_image_url(name):
    """Returns the url for the given image
    """
    portal_url = _api.get_url(_api.get_portal())
    return "{}/++resource++senaite.queue.static/{}".format(portal_url, name)


def is_queue_enabled(task_name_or_action=_DEFAULT_CHUNK_SIZE_ID):
    """Returns whether the queue is active for current instance or not.
    """
    return get_chunk_size(task_name_or_action) > 0


def disable_queue(task_name_or_action=_DEFAULT_CHUNK_SIZE_ID):
    """Disables the queue for the given action
    """
    set_chunk_size(task_name_or_action, 0)


def enable_queue(task_name_or_action=_DEFAULT_CHUNK_SIZE_ID):
    """Enable the queue for the given action
    """
    default = get_chunk_size(_DEFAULT_CHUNK_SIZE_ID)
    if default <= 0:
        default = 10
    set_chunk_size(task_name_or_action, default)


def set_default_chunk_size(value):
    """Sets the default chunk size
    """
    set_chunk_size(_DEFAULT_CHUNK_SIZE_ID, value)


def set_chunk_size(task_name_or_action, chunk_size):
    """
    Sets the chunk size for the given task name
    """
    registry_id = resolve_queue_registry_record(task_name_or_action)
    if registry_id:
        plone_api.portal.set_registry_record(registry_id, chunk_size)


def get_chunk_size(task_name_or_action=_DEFAULT_CHUNK_SIZE_ID):
    """Returns the default chunk size for a given task. If the queue is not
    enabled for the task or for the whole queue, returns 0
    """
    if not is_installed():
        return 0

    # If the whole queue is deactivated, return 0
    default_size = get_queue_registry_record(_DEFAULT_CHUNK_SIZE_ID)
    default_size = _api.to_int(default_size, 0)
    if default_size < 1:
        return 0

    # Get the chunk size from this task name or action
    chunk_size = get_queue_registry_record(task_name_or_action)
    chunk_size = _api.to_int(chunk_size, default=None)
    if chunk_size is None:
        return default_size

    if chunk_size < 0:
        return 0

    return chunk_size


def get_chunks(task_name, items):
    """Returns the items splitted into a list. The first element contains the
    first chunk and the second element contains the rest of the items
    """
    chunk_size = get_chunk_size(task_name)
    return chunks(items, chunk_size)


def chunks(items, chunk_size):
    """Returns the items splitted into a list of two items. The first element
    contains the first chunk and the second element contains the rest of the
    items
    """
    if chunk_size <= 0 or chunk_size >= len(items):
        return [items, []]
    return [items[:chunk_size], items[chunk_size:]]


def get_queue_registry_record(task_name_or_action):
    """Returns the value for queue settings from the registry
    """
    registry_id = resolve_queue_registry_record(task_name_or_action)
    if registry_id:
        return _api.get_registry_record(registry_id)
    return None


def resolve_queue_registry_record(task_name_or_action):
    """Resolves the id used in the registry for the given task name or action
    """
    registry_name = task_name_or_action
    if "senaite.queue." not in registry_name:
        registry_name = "senaite.queue.{}".format(task_name_or_action)

    # Get the value
    val = _api.get_registry_record(registry_name)
    if val is not None:
        return registry_name

    # Maybe is an action
    action_name = get_action_task_name(task_name_or_action)
    if "senaite.queue." not in action_name:
        action_name = "senaite.queue.{}".format(action_name)

    # Get the value
    val = _api.get_registry_record(action_name)
    if val is not None:
        return action_name
    return None


def get_action_task_name(action):
    """Returns the unique name of an action type task
    """
    return "task_action_{}".format(action)


def get_min_seconds_task(default=3):
    """Returns the minimum number of seconds to book per task
    """
    min_seconds = get_queue_registry_record(_MIN_SECONDS_TASK_ID)
    min_seconds = _api.to_int(min_seconds, default)
    if min_seconds < 1:
        min_seconds = 1
    return min_seconds


def get_max_seconds_task(default=120):
    """Returns the max number of seconds to wait for a task to finish
    """
    registry_id = "senaite.queue.max_seconds_unlock"
    max_seconds = _api.get_registry_record(registry_id)
    max_seconds = _api.to_int(max_seconds, default)
    if max_seconds < 30:
        max_seconds = 30
    return max_seconds


def get_max_retries(default=3):
    """Returns the number of times a task will be re-queued before being
    considered as failed
    """
    max_retries = get_queue_registry_record(_DEFAULT_MAX_RETRIES_ID)
    max_retries = _api.to_int(max_retries, default)
    if max_retries < 1:
        max_retries = 0
    return max_retries


def set_max_retries(value):
    """Sets the number of times a task will be re-queued before being
    considered as failed
    """
    plone_api.portal.set_registry_record(_DEFAULT_MAX_RETRIES_ID, value)


def get_queue():
    """Returns the queue utility
    """
    return getUtility(IQueueUtility)


def is_queued(brain_object_uid, task_name=None, include_running=True):
    """Returns whether the object passed-in is queued
    :param brain_object_uid: the object to check for
    :param task_name: filter by task_name
    :param include_running: whether to look for in running tasks or not
    :return: True if the object is in the queue
    """
    queued = False
    uid = _api.get_uid(brain_object_uid)
    queue = get_queue()
    for task in queue.get_tasks_for(uid):
        if not include_running and task.status == "running":
            continue
        elif task_name and task_name != task.name:
            continue
        else:
            queued = True
            break
    return queued


def queue_task(name, request, context, username=None, unique=False,
               priority=10, **kw):
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
    if not all([name, request, context]):
        raise ValueError("name, request and context are required")

    # Check if there is a registered adapter able to handle this task
    adapter = queryAdapter(context, IQueuedTaskAdapter, name=name)
    if not adapter:
        # If this is an action, try to fallback to default action adapter
        if name.startswith("task_action_"):
            action = name.replace("task_action_", "")
            kw = kw or {}
            uids = kw.get("uids") or [_api.get_uid(context)]
            kw.update({"action": action, "uids": uids})
            return queue_task("task_generic_action", request, context, username,
                              unique=unique, priority=priority, **kw)
        raise ValueError(
            "No IQueuedTaskAdapter found for task '{}' and context '{}'".format(
                name, _api.get_path(context))
            )

    # Create the QueueTask object
    kw = kw or {}
    if priority:
        kw.update({"priority": priority})

    kw.update({
        "min_seconds": kw.get("min_seconds", get_min_seconds_task()),
        "max_seconds": kw.get("max_seconds", get_max_seconds_task()),
        "retries": kw.get("retries", get_max_retries()),
    })

    task = QueueTask(name, request, context, **kw)
    if username:
        task.username = username

    # Add the task to the queue
    return get_queue().add(task, unique=unique)


def queue_action(brain_object_uid, action, context=None, request=None):
    """Adds a given action to the queue for async processing
    :param brain_object_uid: object/s to perform the action against
    :param context: context where the action takes place
    :param request: the HTTPRequest
    :param action: action to be performed
    :return: whether the action was successfully queued or not
    """
    if not isinstance(brain_object_uid, (list, tuple)):
        brain_object_uid = [brain_object_uid]

    # Remove empties and duplicates while keeping the order
    uids = filter(None, map(_api.get_uid, brain_object_uid))
    uids = list(OrderedDict.fromkeys(uids))
    if not uids:
        return False

    context = context or _api.get_portal()
    if action == "assign" and IWorksheet.providedBy(context):
        return queue_assign_analyses(context, analyses=uids, request=request)

    # Queue the task
    task_name = get_action_task_name(action)
    kwargs = {
        "action": action,
        "uids": uids,
    }
    request = request or _api.get_request()
    return queue_task(task_name, request, context, **kwargs)


def queue_assign_analyses(worksheet, analyses, slots=None, request=None):
    """Adds analyses to the queue for analyses assignment
    :param worksheet: the worksheet object the analyses have to be assigned to
    :param analyses: list of analyses objects, brains or uids
    :param slots: list of slots each analysis has to be assigned to
    :param request: the HTTPRequest
    """
    task_name = "task_assign_analyses"
    kwargs = {
        "uids": map(_api.get_uid, analyses),
        "slots": slots or [],
    }
    request = request or _api.get_request()
    return queue_task(task_name, request, worksheet, **kwargs)


def queue_reindex_object_security(obj, request=None, priority=20):
    """Queues a task for the recursive object security reindexing
    """
    def get_children_uids(obj):
        """Returns the uids from the obj hierarchy
        """
        if not hasattr(aq_base(obj), "objectValues"):
            return []

        all_children = []
        for child_obj in obj.objectValues():
            all_children.extend(get_children_uids(child_obj))
            all_children.append(_api.get_uid(child_obj))

        return all_children

    # Get all children reversed, and append current one
    uids = get_children_uids(obj)
    uids.append(_api.get_uid(obj))

    # Get all reversed, so recent objects are processed first
    uids = uids[::-1]

    task_name = "task_reindex_object_security"
    kwargs = {"uids": uids, "priority": priority}
    request = request or _api.get_request()
    return queue_task(task_name, request, obj, **kwargs)
