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
from zope.interface import Interface  # noqa


class ISenaiteQueueLayer(IBikaLIMS, ISenaiteLIMS):
    """Zope 3 browser Layer interface specific for senaite.queue
    This interface is referred in profiles/default/browserlayer.xml.
    All views and viewlets register against this layer will appear in the site
    only when the add-on installer has been run.
    """


# TODO: REMOVE. Is not longer used for v1.0.1 onwards. Only kept here for
#       safe-uninstall and safe-upgrade. See upgrade v1.0.1
class IQueueDispatcher(Interface):
    """Process the task from the queue
    """


# TODO: REMOVE. Is not longer used for v1.0.2 onwards. See upgrade v1.0.2
class IQueued(Interface):
    """Marker interface for objects that are in an async queue
    """


class IQueuedTaskAdapter(Interface):
    """Marker interface for adapters in charge of processing queued tasks
    """

    def __init__(self, context):  # noqa
        """Initializes the adapter with the context adapted
        """

    def process(self, task):
        """Process the task from the queue
        """


class IQueueUtility(Interface):
    """Interface that provide basic signatures for Queue utilities
    """

    def add(self, task):
        """Adds a task to the queue
        :param task: the QueueTask to add
        """

    def pop(self, consumer_id):
        """Returns the next task to process, if any
        :param consumer_id: id of the consumer thread that will process the task
        :return: the task to be processed or None
        :rtype: queue.QueueTask
        """

    def done(self, task):
        """Notifies the queue that the task has been processed successfully
        :param task: task's unique id (task_uid) or QueueTask object
        """

    def fail(self, task, error_message=None):
        """Notifies the queue that the processing of the task failed
        :param task: task's unique id (task_uid) or QueueTask object
        :param error_message: (Optional) the error/traceback
        """

    def timeout(self, task):
        """Notifies the queue that the processing of the task timed out
        :param task: task's unique id (task_uid) or QueueTask object
        """

    def delete(self, task):
        """Removes a task from the queue
        :param task: task's unique id (task_uid) or QueueTask object
        """

    def get_task(self, task_uid):
        """Returns the task with the given task uid
        :param task_uid: task's unique id
        :return: the task from the queue
        :rtype: queue.QueueTask
        """

    def get_tasks(self, status=None):
        """Returns an iterable with the tasks from the queue
        :param status: (Optional) a string or list with status. If None, only
            "running" and "queued" are considered
        :return iterable of QueueTask objects
        :rtype: iterator
        """

    def get_uids(self, status=None):
        """Returns a list with the uids from the queue
        :param status: (Optional) a string or list with status. If None, only
            "running" and "queued" are considered
        :return list of uids
        :rtype: list
        """

    def get_tasks_for(self, context_or_uid, name=None):
        """Returns a list with the queued or running tasks the queue contains
        for the given context and name, if provided. Failed tasks are not
        considered
        :param context_or_uid: object/brain/uid to look for in the queue
        :param name: (Optional) name of the type of the task to look for
        :return: a list of QueueTask objects
        :rtype: list
        """

    def has_task(self, task):
        """Returns whether the queue contains a given task
        :param task: task's unique id (task_uid) or QueueTask object
        :return: True if the queue contains the task
        :rtype: bool
        """

    def has_tasks_for(self, context_or_uid, name=None):
        """Returns whether the queue contains a task for the given context and
        name if provided.
        :param context_or_uid: object/brain/uid to look for in the queue
        :param name: (Optional) name of the type of the task to look for
        :return: True if the queue contains the task
        :rtype: bool
        """

    def is_empty(self):
        """Returns whether the queue is empty. Failed tasks are not considered
        :return: True if the queue does not have running nor queued tasks
        :rtype: bool
        """


class IServerQueueUtility(IQueueUtility):
    """Marker interface for Queue global utility (singleton) used by the zeo
    client that acts as the server
    """

    def get_since_time(self):
        """Returns the time since epoch when the oldest task the queue contains
        was created, failed tasks excluded. Returns -1 if queue has no queued
        or running tasks
        """

    def is_busy(self):
        """Returns whether the queue is busy
        """

    def purge(self):
        """Purges the queue of invalid/stuck tasks
        """


class IClientQueueUtility(IQueueUtility):
    """Marker interface for the Queue global utility (singleton) used by the
    zeo clients that act as queue clients
    """

    def is_out_of_date(self):
        """Returns whether this client queue utility is out-of-date and requires
        a synchronization of tasks with the queue server
        """

    def sync(self):
        """Synchronizes the client queue utility with the queue server
        """
