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

from Acquisition import aq_base  # noqa
from collections import OrderedDict
from plone.memoize import ram
from senaite.queue import is_installed
from senaite.queue.interfaces import IClientQueueUtility
from senaite.queue.interfaces import IQueuedTaskAdapter
from senaite.queue.interfaces import IServerQueueUtility
from senaite.queue.queue import get_chunk_size
from senaite.queue.queue import new_task
from senaite.queue.request import get_zeo_site_url
from six.moves.urllib import parse
from zope.component import getUtility
from zope.component import queryAdapter

from bika.lims import api as _api
from bika.lims.interfaces import IWorksheet


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

    # Compare with the base url of the current zeo client
    return server_url.lower() in get_zeo_site_url().lower()


def is_queue_enabled(name_or_action=None):
    """Returns whether the queue is in a suitable status for reads
    """
    readable = ["ready", "resuming"]
    return get_queue_status(name_or_action) in readable


def is_queue_ready(name_or_action=None):
    """Returns whether the queue is in a suitable status for both read and
    write (task addition) actions
    """
    writable = ["ready"]
    return get_queue_status(name_or_action) in writable


def get_queue_status(name_or_action=None):
    """Returns the current status of the queue:
    * `ready`: queue server is enabled and healthy, It is safe to add tasks
    * `resuming`: queue server is preparing for a `disabled` status. Tasks
        added in the queue while in this status will still be processed, but is
        not recommended.
    * `disabled`: queue has been disabled or is not installed. Tasks added to
        the queue in this status won't be processed.
    """
    # Is senaite queue not installed?
    if not is_installed():
        return "disabled"

    # Is the server url not valid?
    if not get_server_url():
        return "disabled"

    # Is queue enabled?
    if get_chunk_size(name_or_action=name_or_action) > 0:
        return "ready"

    # Queue not enabled, is empty?
    if get_queue().is_empty():
        return "disabled"

    # Queue is not enabled, but not empty. We don't accept new tasks
    return "resuming"


def is_queued(brain_object_uid, status=None):
    """Returns whether the object passed-in is queued
    :param brain_object_uid: the object to check for
    :param status: (Optional) if None, looks to tasks either queued or running
    :return: True if the object is in the queue
    """
    if not is_queue_enabled():
        return False

    uid = _api.get_uid(brain_object_uid)
    return uid in get_queue().get_uids(status=status)


def add_task(name, context, **kwargs):
    """Adds a task to the queue for async processing
    :param name: the name of the task
    :param context: the context the task is bound or relates to
    :param min_seconds: (optional) int, minimum seconds to book for the task
    :param max_seconds: (optional) int, maximum seconds to wait for the task
    :param retries: (optional) int, maximum number of retries on failure
    :param username: (optional) str, the name of the user assigned to the task
    :param priority: (optional) int, the priority value for this task
    :param unique: (optional) bool, if True, the task will only be added if
            there is no other task with same name and for same context. This
            setting is set to False by default
    :param chunk_size: (optional) the number of items to process asynchronously
            at once from this task (if it contains multiple elements)
    :param ghost: (optional) if True, clients won't get notified about the task
            but consumers only. This setting is set to False by default
    :param delay: (optional) delay in seconds before the task becomes available
            for processing to consumers. Default: 0
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
                "action": name[len(action_prefix):],
                "uids": kwargs.get("uids", [_api.get_uid(context)])
            })
            return add_task("task_generic_action", context, **kwargs)

        raise ValueError(
            "No IQueuedTaskAdapter for task '{}' and context '{}'".format(
                name, _api.get_path(context)
            )
        )

    # Create the task
    task = new_task(name, context, **kwargs)

    # Add the task to the queue and return
    return get_queue().add(task)


def add_action_task(brain_object_uid, action, context=None, **kwargs):
    """Adds an action-type task to the queue for async processing.
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
        # Return the server's queue utility
        utility = getUtility(IServerQueueUtility)
    else:
        # Return the client's queue utility
        utility = getUtility(IClientQueueUtility)
        if utility.is_out_of_date():
            # Sync the queue if needed
            utility.sync()

    return utility
