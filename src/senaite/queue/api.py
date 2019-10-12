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
# Copyright 2018-2019 by it's authors.
# Some rights reserved, see README and LICENSE.

from senaite.queue.interfaces import IQueueDispatcher
from zope.component._api import queryUtility

from bika.lims.api import *
from bika.lims.utils import render_html_attributes

_DEFAULT_TASK_ID = "senaite.queue.default"


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
    portal_url = get_url(get_portal())
    return "{}/++resource++senaite.queue.static/{}".format(portal_url, name)


def get_queue_utility():
    """
    Returns the queue utility
    """
    return queryUtility(IQueueDispatcher)


def is_queue_enabled(task=_DEFAULT_TASK_ID):
    """Returns whether the queue is active for current instance or not.
    """
    return get_chunk_size(task) > 0


def get_chunk_size(task_name_or_action):
    """Returns the default chunk size for a given task. If the queue is not
    enabled for the task or for the whole queue, returns 0
    """
    utility = get_queue_utility()
    if utility is None:
        # Queue dispatch utility not registered. The add-on is not installed
        return 0

    # If the whole queue is deactivated, return 0
    default_size = get_queue_registry_record(_DEFAULT_TASK_ID)
    default_size = to_int(default_size, 0)
    if default_size < 1:
        return 0

    # Get the chunk size from this task name or action
    chunk_size = get_queue_registry_record(task_name_or_action)
    chunk_size = to_int(chunk_size, default=None)
    if chunk_size is None:
        return default_size

    if chunk_size < 0:
        return 0

    return chunk_size


def get_chunks(task_name, items):
    """Returns the items splited into a list. Rhe first element contains the
    first chunk and the second element contains the rest of the items
    """
    chunk_size = get_chunk_size(task_name)
    if chunk_size <= 0 or chunk_size >= len(items):
        return [items, []]

    return [items[:chunk_size], items[chunk_size:]]


def get_queue_registry_record(task_name_or_action, fallback_action=True):
    # Be sure we don't miss the prefix
    registry_name = task_name_or_action
    if "senaite.queue." not in registry_name:
        registry_name = "senaite.queue.{}".format(task_name_or_action)

    # Get the value
    val = get_registry_record(registry_name)

    if val is None and fallback_action:
        # Maybe is an action
        action_name = get_action_task_name(task_name_or_action)
        return get_queue_registry_record(action_name, fallback_action=False)

    return val


def get_action_task_name(action):
    return "task_action_{}".format(action)

