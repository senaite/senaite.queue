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
from Acquisition import aq_base  # noqa
from collections import OrderedDict
from plone.memoize import ram
from senaite.queue import IQueueUtility
from senaite.queue import is_installed
from senaite.queue import logger
from senaite.queue.interfaces import IClientQueueUtility
from senaite.queue.interfaces import IOfflineClientQueueUtility
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.queue import get_chunk_size
from senaite.queue.queue import new_task
from six.moves.urllib import parse
from zope.component import getUtility
from zope.component import queryAdapter

from bika.lims import api as _api
from bika.lims.interfaces import IWorksheet
from bika.lims.utils import render_html_attributes


def get_server_url():
    """Returns the url of the queue server if valid. None otherwise.
    """
    url = _api.get_registry_record("senaite.queue.server")
    try:
        result = parse.urlparse(url)
    except:  # noqa a convenient way to check if the url is valid
        return None

    # Validate the url is ok
    if not all([result.scheme, result.netloc, result.path]):
        return None

    url = "{}://{}{}".format(result.scheme, result.netloc, result.path)
    return url.strip("/")


@ram.cache(lambda *args: get_server_url())
def is_queue_server():
    """Returns whether the current thread belongs to the zeo client configured
    as the queue server. Decorator ensures that the function is only called the
    first time and when the server url setting from control panel changes
    """
    server_url = get_server_url()
    if not server_url:
        return False
    # TODO FIx this!
    current_url = _api.get_url(_api.get_portal())
    return current_url.lower().startswith(server_url.lower())


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
        r = requests.get(url, timeout=1)
        r.raise_for_status()
        return True
    except:  # noqa don't care about the response, want a ping only
        return False


def is_queue_readable(name_or_action=None):
    """Returns whether the queue is in a suitable status for reads
    """
    readable = ["ready", "resuming", "offline"]
    return get_queue_status(name_or_action) in readable


def is_queue_writable(name_or_action=None):
    """Returns whether the queue is in a suitable status for both read and
    write (task addition) actions
    """
    writable = ["ready"]
    return get_queue_status(name_or_action) in writable


def is_queue_readonly(name_or_action=None):
    """Returns whether the queue is in read-only mode (no new tasks allowed)
    """
    readonly = ["resuming", "offline"]
    return get_queue_status(name_or_action) in readonly


def get_queue_status(name_or_action=None):
    """Returns the current status of the queue:

    * `ready`: queue server is enabled and healthy

    * `resuming`: queue server is preparing for a `disabled` status. Queue
            server does not accept `add` requests. In this status, clients
            should be communicating with the queue to get updates about the
            status of remaining tasks and objects.

    * `disabled`: queue server does not accept requests at all, either because
            has been disabled or because senaite.queue is not installed

    * `offline`: queue server is not reachable or is unable to answer requests.
    """
    # Is senaite queue not installed?
    if not is_installed():
        return "disabled"

    # Is the server url not valid?
    if not get_server_url():
        return "offline"

    # Is queue enabled?
    queue = get_queue()
    enabled = get_chunk_size(name_or_action=name_or_action) > 0

    if IOfflineClientQueueUtility.providedBy(queue):
        # This is the utility to operate offline
        return "offline"

    if IQueueUtility.providedBy(queue):
        # This is the Queue server
        return enabled and "ready" or "disabled"

    if not enabled:
        try:
            if not queue.is_empty():
                # Queue is disabled but there are remaining tasks
                return "resuming"
        except:  # noqa if server raises an error, assume is not healthy
            # Client queue has problems to communicate with server, so we
            # cannot be sure about the "real" status of the server
            return "offline"

    return enabled and "ready" or "disabled"


def add_task(name, context, **kwargs):
    """Adds a task to the queue for async processing

    Delivery is not granted. The recommended usage is::

        >>> if not add_task(name, context):
        >>>     # Do the process sync

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
    :return: the QueueTask object added to the queue, if any
    :rtype: senaite.queue.queue.QueueTask
    """
    # Check if there is a registered adapter able to handle this task
    adapter = queryAdapter(context, IQueuedTaskAdapter, name=name)
    if not adapter:
        # If this is an action, try to fallback to default action adapter
        action_prefix = "task_action_"
        if name.startswith(action_prefix):
            kwargs.update({
                "name": "task_generic_action",
                "action": name[len(action_prefix):],
                "uids": kwargs.get("uids", [_api.get_uid(context)])
            })
            return add_task(name, context, **kwargs)

        raise ValueError(
            "No IQueuedTaskAdapter for task '{}' and context '{}'".format(
                name, _api.get_path(context)
            )
        )

    # Don't add the task unless the queue is writable
    if not is_queue_writable(name):
        return None

    # Create the task
    task = new_task(name, context, **kwargs)

    # Add the task to the queue and return
    try:
        return get_queue().add(task)
    except:  # noqa Delivery is not granted
        return None


def add_action_task(brain_object_uid, action, context=None, **kwargs):
    """Adds an action-type task to the queue for async processing.

    Delivery is not granted. The recommended usage is::

        >>> if not add_action_task(brain_object_uid, action):
        >>>     # Do the process sync

    :param brain_object_uid: object(s) to perform the action against
    :param action: action to be performed
    :param context: context where the action takes place
    :param kwargs: optional arguments that ``add_task`` takes.
    :return: the task added to the queue
    :rtype: senaite.queue.queue.QueueTask
    """
    if not isinstance(brain_object_uid, (list, tuple)):
        brain_object_uid = [brain_object_uid]

    # Remove empties and duplicates while keeping the order
    uids = filter(None, map(_api.get_uid, brain_object_uid))
    uids = list(OrderedDict.fromkeys(uids))
    if not uids:
        return None

    context = context or _api.get_portal()

    # Special case for "assign" action
    if action == "assign" and IWorksheet.providedBy(context):
        return add_assign_task(context, analyses=uids)

    name = "task_action_{}".format(action)
    kwargs.update({
        "action": action,
        "uids": uids,
    })
    return add_task(name, context, **kwargs)


def add_assign_task(worksheet, analyses, slots=None, **kwargs):
    """Adds an action-type task to the queue for async processing

    Delivery is not granted. The recommended usage is::

        >>> if not add_action_task(worksheet, analyses):
        >>>     # Do the process sync

    :param worksheet: the worksheet object the analyses will be assigned to
    :param analyses: list of analyses objects, brains or uids
    :param slots: list of slots each analysis has to be assigned to
    :param kwargs: optional arguments that ``add_task`` takes.
    :return: the task added to the queue
    :rtype: senaite.queue.queue.QueueTask
    """
    kwargs.update({
        "uids": map(_api.get_uid, analyses),
        "slots": slots or [],
    })
    return add_task("task_assign_analyses", worksheet, **kwargs)


def add_reindex_obj_security_task(brain_object_uid, **kwargs):
    """Adds a task for recursive object security reindexing to the queue

    Delivery is not granted. The recommended usage is::

        >>> if not add_reindex_obj_security_task(obj):
        >>>     # Do the process sync

    :param brain_object_uid: uid/brain/object
    :param kwargs: optional arguments that ``add_task`` takes.
    :return: the task added to the queue
    :rtype: senaite.queue.queue.QueueTask
    """
    def get_children_uids(base_obj):
        """Returns the uids from the obj hierarchy
        """
        if not hasattr(aq_base(base_obj), "objectValues"):
            return []

        all_children = []
        for child_obj in base_obj.objectValues():
            all_children.extend(get_children_uids(child_obj))
            all_children.append(_api.get_uid(child_obj))

        return all_children

    # Get the object
    obj = _api.get_object(brain_object_uid)

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


def get_queue():
    """Returns the queue utility
    """
    if is_queue_server():
        # This is the server, return the base queue utility
        return getUtility(IQueueUtility)

    elif is_queue_reachable():
        # Return the queue utility that communicates with server via JSON
        utility = getUtility(IClientQueueUtility)

        # Synchronize the serverless utility if necessary
        headless = getUtility(IOfflineClientQueueUtility)
        if headless.is_out_of_sync():
            headless.sync(utility)

        return utility

    # Queue server not reachable, return the queue utility for off-line mode
    logger.warn("Running in off-line mode")
    return getUtility(IOfflineClientQueueUtility)


# TODO REVIEW


def is_queued(brain_object_uid, task_name=None, include_running=True):
    """Returns whether the object passed-in is queued
    :param brain_object_uid: the object to check for
    :param task_name: filter by task_name
    :param include_running: whether to look for in running tasks or not
    :return: True if the object is in the queue
    """
    if not is_queue_readable():
        return False

    uid = _api.get_uid(brain_object_uid)
    for task in get_queue().get_tasks_for(uid):
        if not include_running and task.status == "running":
            continue
        elif task_name and task_name != task.name:
            continue
        else:
            return True
    return False


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
