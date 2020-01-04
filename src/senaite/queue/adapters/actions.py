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

from senaite.queue import api
from senaite.queue.queue import queue_action

from bika.lims.browser.workflow import WorkflowActionGenericAdapter


class WorkflowActionGenericQueueAdapter(WorkflowActionGenericAdapter):
    """Adapter in charge of submission of results from a worksheet,
    adding them into a queue for async submission
    """

    def do_action(self, action, objects):
        # Process the first chunk as usual
        chunks = api.get_chunks(action, objects)
        super(WorkflowActionGenericQueueAdapter, self)\
            .do_action(action, chunks[0])

        # Process the rest in a queue
        queue_action(self.context, self.request, action, chunks[1])

        return objects
