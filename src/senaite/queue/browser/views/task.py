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

import json

from Products.Five.browser import BrowserView
from senaite.queue.storage import QueueStorageTool


class TaskView(BrowserView):
    """View that displays a Queue Task in JSON format
    """

    def __init__(self, context, request):
        super(TaskView, self).__init__(context, request)
        self.context = context
        self.request = request

    def __call__(self):
        task_uid = self.request.get("uid", None)
        queue = QueueStorageTool()
        task = queue.get_task(task_uid) or {}
        return json.dumps(task)
