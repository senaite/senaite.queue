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

from zope.interface import implements

from bika.lims.interfaces import IGuardAdapter
from senaite.queue import api


class SampleGuardAdapter(object):
    implements(IGuardAdapter)

    def __init__(self, context):
        self.context = context

    def guard(self, action):
        """Returns False if the sample is queued or contains queued analyses
        """
        # Don't do anything if senaite.queue is not enabled
        if not api.is_queue_enabled():
            return True

        # Check if the sample is queued
        if api.is_queued(self.context, status=["queued"]):
            return False

        # Check whether the sample contains queued analyses
        for brain in self.context.getAnalyses():
            if api.is_queued(brain, status=["queued"]):
                return False

        return True


class WorksheetGuardAdapter(object):
    implements(IGuardAdapter)

    def __init__(self, context):
        self.context = context

    def guard(self, action):
        """Returns False if the worksheet has queued jobs
        """
        # Don't do anything if senaite.queue is not enabled
        if not api.is_queue_enabled():
            return True

        # Check if the worksheet is queued
        if api.is_queued(self.context, status=["queued"]):
            return False

        # Check whether this worksheet contains queued analyses
        for obj in self.context.getAnalyses():
            if api.is_queued(obj, status=["queued"]):
                return False

        return True
