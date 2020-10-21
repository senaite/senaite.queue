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
import time

from Acquisition import aq_base
from collections import OrderedDict
from plone.memoize import ram
from senaite.queue import IQueueUtility
from senaite.queue import is_installed
from senaite.queue.interfaces import IClientQueueUtility
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.queue import QueueTask
from six.moves.urllib import parse
from zope.component import getUtility
from zope.component import queryAdapter

from bika.lims import api as _api
from bika.lims.interfaces import IWorksheet
from bika.lims.utils import render_html_attributes

_action_prefix = "task_action_"
_marker = object()


def _generic_cache_key(fun, *args, **kwargs):
    """Returns an string made of the args and kwargs. Used in cache decorators
    """
    cache_seconds = kwargs.get("cache_seconds", 0)
    if cache_seconds <= 1:
        # Do not cache
        raise ram.DontCache

    params = [fun.func_name] + list(filter(None, args))
    params += sorted(map(lambda i: "{}={}".format(i[0], i[1]), kwargs.items()))
    return "|".join(params), time.time() // cache_seconds


def get_server_url():
    """Returns the url of the queue server, if valid. Decorator ensures that the
    function is only called the first time or when the server url setting from
    control panel changes
    """
    url = _api.get_registry_record("senaite.queue.server")
    if not url:
        return None

    try:
        result = parse.urlparse(url)
        if all([result.scheme, result.netloc, result.path]):
            url = "{}://{}{}".format(result.scheme, result.netloc, result.path)
            # Remove trailing '/'
            url = url.strip("/")
            return url
    except:
        pass
    return None


@ram.cache(lambda *args: get_server_url())
def is_queue_server():
    """Returns whether the current thread belongs to the zeo client configured
    as the queue server. Decorator ensures that the function is only called the
    first time and when the server url setting from control panel changes
    """
    print("CACHE ******************  is queue server ****************")
    server_url = get_server_url()
    if not server_url:
        return False
    current_url = _api.get_url(_api.get_portal())
    return current_url.startswith(server_url)


@ram.cache(lambda *args: time.time() // 10)
def is_queue_reachable():
    """Returns whether the queue server is reachable or not. Decorator ensures
    that the function is only called once every 10 seconds
    """
    if is_queue_server():
        # This current thread is the server
        return True

    server_url = get_server_url()
    if not server_url:
        return False

    # Ping
    url = "{}/@@API/senaite/v1/version".format(server_url)
    try:
        # Check the request was successful. Raise exception otherwise
        print("CACHE ******************  is queue reachable ****************")
        r = requests.get(url, timeout=1)
        r.raise_for_status()
        return True
    except:
        return False


def is_queue_active(name_or_action=None):
    """Returns whether the queue is installed, properly configured and enabled
    :param name_or_action: (optional) if set, returns if the queue is enabled
            for tasks with the name or action passed in
    :param cache_seconds: (optional) cache the result for n seconds. Don't use
            it unless you know exactly what you are doing
    :returns: True or False
    :rtype: bool
    """
    if not is_installed():
        # senaite.queue add-on is not installed
        return False

    server_url = get_server_url()
    if not server_url:
        # Queue's server URL is not valid
        return False

    # Assume the queue is enabled for this name/action if chunk size > 0
    chunk_size = get_chunk_size(name_or_action)
    if chunk_size < 0:
        return False

    # Ping if reachable
    return is_queue_reachable()


def get_chunk_size(name_or_action=None):
    """Returns the number of items to process at once for the given task name
    :param name_or_action: task name or workflow action id
    :returns: the number of items from the task to process async at once
    :rtype: int
    """
    chunk_size = _api.get_registry_record("senaite.queue.default")
    chunk_size = _api.to_int(chunk_size, 0)
    if chunk_size <= 0:
        # All queue disabled
        return 0

    if name_or_action:
        # Get the registry id for this name/action
        token = name_or_action.split("senaite.queue.")[-1]
        if token.startswith("task_"):
            reg_id = "senaite.queue.{}".format(name_or_action)
        else:
            reg_id = "senaite.queue.{}{}".format(_action_prefix, token)

        # Get the registry value
        reg_value = _api.get_registry_record(reg_id)
        chunk_size = _api.to_int(reg_value, default=chunk_size)

    return chunk_size > 0 and chunk_size or 0


def get_min_seconds(default=3):
    """Returns the minimum number of seconds to book per task
    """
    registry_id = "senaite.queue.min_seconds_task"
    min_seconds = _api.get_registry_record(registry_id)
    min_seconds = _api.to_int(min_seconds, default=default)
    return min_seconds >= 1 and min_seconds or default


def get_max_seconds(default=120):
    """Returns the max number of seconds to wait for a task to finish
    """
    registry_id = "senaite.queue.max_seconds_unlock"
    max_seconds = _api.get_registry_record(registry_id)
    max_seconds = _api.to_int(max_seconds, default=default)
    return max_seconds >= 30 and max_seconds or default


def get_max_retries(default=3):
    """Returns the number of retries before considering a task as failed
    """
    registry_id = "senaite.queue.max_retries"
    max_retries = _api.get_registry_record(registry_id)
    max_retries = _api.to_int(max_retries, default=default)
    return max_retries >= 1 and max_retries or default


def new_task(name, context, **kw):
    """Creates a QueueTask
    :param name: the name of the task
    :param context: the context the task is bound or relates to
    :param min_seconds: (optional) int, minimum seconds to book for the task
    :param max_seconds: (optional) int, maximum seconds to wait for the task
    :param retries: (optional) int, maximum number of retries on failure
    :param username: (optional) str, the name of the user assigned to the task
    :param priority: (optional) int, the priority value for this task
    :param unique: (optional) bool, if True, the task will only be added if
            there is no other task with same name and for same context
    :param chunk_size: (optional) the number of items to process asynchronously
            at once from this task (if it contains multiple elements)
    :return: :class:`QueueTask <QueueTask>`
    :rtype: senaite.queue.queue.QueueTask
    """
    task = QueueTask(name, _api.get_request(), context, **kw)
    task.username = kw.get("username", task.username)
    task.update({
        "min_seconds": kw.get("min_seconds", get_min_seconds()),
        "max_seconds": kw.get("max_seconds", get_max_seconds()),
        "retries": kw.get("retries", get_max_retries()),
        "priority": kw.get("priority", 10),
        "unique": kw.get("unique", False),
        "chunk_size": kw.get("chunk_size", get_chunk_size(name))
    })
    return task


def add_task(name, context, **kwargs):
    """Adds a task to the queue for async processing
    :param name: the name of the task
    :param context: the context the task is bound or relates to
    :param \*\*kwargs: optional arguments that ``new_task`` takes.
    :return: :class:`QueueTask <QueueTask>` object
    :rtype: senaite.queue.queue.QueueTask
    """
    # Is senaite.queue enabled/installed for this type of task?
    if not is_queue_active(name):
        raise ValueError(
            "senaite.queue is not installed/enabled for {}".format(name)
        )

    # Check if there is a registered adapter able to handle this task
    adapter = queryAdapter(context, IQueuedTaskAdapter, name=name)
    if not adapter:
        # If this is an action, try to fallback to default action adapter
        if name.startswith(_action_prefix):
            kwargs.update({
                "name": "task_generic_action",
                "action": name[len(_action_prefix):],
                "uids": kwargs.get("uids", [_api.get_uid(context)])
            })
            return add_task(name, context, **kwargs)

        raise ValueError(
            "No IQueuedTaskAdapter for task '{}' and context '{}'".format(
                name, _api.get_path(context)
            )
        )

    # Create the task
    task = new_task(name, context, **kwargs)

    if is_queue_server():
        # This thread belongs to the zeo client configured as server.
        # Directly add the task to the Queue Utility
        queue = getUtility(IQueueUtility)
    else:
        # This thread does not belong to the zeo client configured as server.
        # Initiate a session with the server to queue the task
        queue = getUtility(IClientQueueUtility)

    # Add the task
    queue.add(task)
    return task


def add_action_task(brain_object_uid, action, context=None, **kwargs):
    """Adds an action-type task to the queue for async processing
    :param brain_object_uid: object(s) to perform the action against
    :param action: action to be performed
    :param context: context where the action takes place
    :param \*\*kwargs: optional arguments that ``new_task`` takes.
    :return: the task added to the queue
    :rtype: senaite.queue.queue.QueueTask
    """
    if not isinstance(brain_object_uid, (list, tuple)):
        brain_object_uid = [brain_object_uid]

    # Remove empties and duplicates while keeping the order
    uids = filter(None, map(_api.get_uid, brain_object_uid))
    uids = list(OrderedDict.fromkeys(uids))
    if not uids:
        return False

    context = context or _api.get_portal()

    # Special case for "assign" action
    if action == "assign" and IWorksheet.providedBy(context):
        return add_assign_task(context, analyses=uids)

    name = "{}{}".format(_action_prefix, action)
    kwargs.update({
        "action": action,
        "uids": uids,
    })
    return add_task(name, context, **kwargs)


def add_assign_task(worksheet, analyses, slots=None, **kwargs):
    """Adds an action-type task to the queue for async processing
    :param worksheet: the worksheet object the analyses will be assigned to
    :param analyses: list of analyses objects, brains or uids
    :param slots: list of slots each analysis has to be assigned to
    :param \*\*kwargs: optional arguments that ``new_task`` takes.
    :return: the task added to the queue
    :rtype: senaite.queue.queue.QueueTask
    """
    kwargs.update({
        "uids": map(_api.get_uid, analyses),
        "slots": slots or [],
    })
    return add_task("task_assign_analyses", worksheet, **kwargs)


def add_reindex_obj_security_task(obj, **kwargs):
    """Adds a task for recursive object security reindexing to the queue
    :param obj: the object the recursive security reindexing has to apply to
    :param \*\*kwargs: optional arguments that ``new_task`` takes.
    :return: the task added to the queue
    :rtype: senaite.queue.queue.QueueTask
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
    kwargs.update({
        "uids": uids,
        "priority": kwargs.get("priority", 20)
    })
    return add_task(task_name, obj, **kwargs)


def get_task_uid(task_or_uid, default=_marker):
    """Returns the task unique identifier
    :param task_or_uid: QueueTask/task uid/dict
    :param default: (Optional) fallback value
    :return: the task's unique identifier
    """
    if _api.is_uid(task_or_uid) and task_or_uid != "0":
        return task_or_uid
    if isinstance(task_or_uid, QueueTask):
        return get_task_uid(task_or_uid.task_uid, default=default)
    if isinstance(task_or_uid, dict):
        task_uid = task_or_uid.get("task_uid", None)
        return get_task_uid(task_uid, default=default)
    if default is _marker:
        raise ValueError("Not supported type: {}".format(task_or_uid))
    return default



# TODO REVIEW


def get_queue():
    """Returns the queue utility
    """
    if is_queue_server():
        return getUtility(IQueueUtility)
    else:
        return getUtility(IClientQueueUtility)


def is_queued(brain_object_uid, task_name=None, include_running=True):
    """Returns whether the object passed-in is queued
    :param brain_object_uid: the object to check for
    :param task_name: filter by task_name
    :param include_running: whether to look for in running tasks or not
    :return: True if the object is in the queue
    """
    if not is_queue_active():
        return False

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


def get_max_seconds_task(default=120):
    """Returns the max number of seconds to wait for a task to finish
    """
    registry_id = "senaite.queue.max_seconds_unlock"
    max_seconds = _api.get_registry_record(registry_id)
    max_seconds = _api.to_int(max_seconds, default)
    if max_seconds < 30:
        max_seconds = 30
    return max_seconds


def queue_reindex_object_security(obj):
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
    kwargs = {"uids": uids, "priority": 20}
    return add_task(task_name, obj, **kwargs)
