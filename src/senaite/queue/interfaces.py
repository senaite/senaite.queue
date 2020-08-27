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

from bika.lims.interfaces import IBikaLIMS
from senaite.lims.interfaces import ISenaiteLIMS
from zope.interface import Interface


class ISenaiteQueueLayer(IBikaLIMS, ISenaiteLIMS):
    """Zope 3 browser Layer interface specific for senaite.queue
    This interface is referred in profiles/default/browserlayer.xml.
    All views and viewlets register against this layer will appear in the site
    only when the add-on installer has been run.
    """


# TODO: REMOVE. Is not longer used for v1.0.1 onwards. Only kept here for
#       safe-uninstall and safe-upgrade
class IQueueDispatcher(Interface):
    """Process the task from the queue
    """


# TODO: REMOVE. Is not longer used for v1.0.2 onwards. Only kept here for
#       safe-uninstall and safe-upgrade
class IQueued(Interface):
    """Marker interface for objects that are in an async queue
    """


class IQueuedTaskAdapter(Interface):
    """Marker interface for adapters in charge of processing queued tasks
    """

    def __init__(self, context):
        """Initializes the adapter with the context adapted
        """

    def process(self, task):
        """Process the task from the queue
        """


class IQueueUtility(Interface):
    """Marker interface for Queue global utility (singleton)
    """

    def pop(self):
        """Returns the next task to process, if any
        """

    def add(self):
        """Adds a task to the queue
        """

    def is_empty(self):
        """Returns whether the queue is empty
        """

    def is_busy(self):
        """Returns whether the queue is busy
        """

    def fail(self, task, error_message=None):
        """Notifies that the task failed
        """

    def success(self, task):
        """Notifies that the task succeed
        """

    def purge(self):
        """Purges the queue of invalid/stuck tasks
        """

    def get_task(self, task_uid):
        """Returns the task with the given tuid
        """

    def get_tasks_for(self, context_or_uid, name=None):
        """Returns an iterable with the tasks the queue contains for the given
        context and name if provided
        """

    def has_tasks_for(self, context_or_uid, name=None):
        """Returns whether the queue contains a task for the given context and
        name if provided.
        """
