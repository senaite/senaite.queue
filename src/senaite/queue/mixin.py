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
from plone.memoize import ram
from senaite.queue import api

from bika.lims import api as _api


def _generic_5s_key(func, *args, **kwargs):
    """Returns an string made of the args and kwargs. Used in cache decorators
    :param func: the decorated function
    :param *args: the named arguments of the decorated function
    :param **kwargs: additional arguments of the decorated function
    :return tuple (string_key, multiple_of_5_seconds), where the string_key is
        made of the concatenation of the func name and the arguments
    :rtype: tuple
    """
    params = [func.func_name] + list(filter(None, args))
    params += sorted(map(lambda i: "{}={}".format(i[0], i[1]), kwargs.items()))
    return "|".join(params), time.time() // 5


@ram.cache(_generic_5s_key)
def _get_uids(status=None):
    """Returns a list with the uids from the queue
    For a given status function is called once every 5 seconds
    :param status: (Optional) a string or list with status. If None, only
        "running" and "queued" are considered
    :return list of uids
    :rtype: list
    """
    return api.get_queue().get_uids(status=status)


class IsQueuedMixin(object):
    """Mixin object providing most used functions for views, viewlets and
    adapters. Functions might rely on memoize decorators, so the values they
    return cached for some seconds. In a single request, same function is
    called many times, that is a waste of resources and cause a lot of requests
    to the Queue server. We do not use here memoize's instance mode because we
    do not want cache to be persistent. Rather, we store the cache in RAM so no
    chance of transaction commit conflicts
    """

    def is_queue_readable(self, name_or_action=None):
        return api.is_queue_readable(name_or_action=name_or_action)

    def is_queued(self, brain_object_uid, status=None):
        """Returns whether the object passed-in is queued
        :param brain_object_uid: the object to check for
        :param status: (optional) task status to filter by
        :return: True if the object is in the queue
        """
        return _api.get_uid(brain_object_uid) in _get_uids(status=status)
