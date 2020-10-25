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

from senaite.queue import api


def _recursive_reindex_object_security(self, obj):
    """Reindex object security recursively, but using the queue
    """
    if api.is_queue_ready("task_reindex_object_security"):
        api.add_reindex_obj_security_task(obj)
        return

    # Do classic reindex
    _recursive_reindex_object_security_wo_queue(self, obj)


def _recursive_reindex_object_security_wo_queue(self, obj):
    """Classic reindex object security, without queue
    """
    if hasattr(aq_base(obj), "objectValues"):
        for child_obj in obj.objectValues():
            _recursive_reindex_object_security_wo_queue(self, child_obj)
    obj.reindexObjectSecurity()
