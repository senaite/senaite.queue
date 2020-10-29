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

from bika.lims.browser.workflow import WorkflowActionGenericAdapter


class WorkflowActionGenericQueueAdapter(WorkflowActionGenericAdapter):
    """Adapter in charge of adding a transition/action to be performed for a
    single object or multiple objects to the queue
    """

    def do_action(self, action, objects):

        if api.is_queue_ready(action):
            # Add to the queue
            kwargs = {"unique": True}
            api.add_action_task(objects, action, self.context, **kwargs)
            return objects

        # Delegate to base do_action
        return super(WorkflowActionGenericQueueAdapter, self).do_action(
            action, objects)
