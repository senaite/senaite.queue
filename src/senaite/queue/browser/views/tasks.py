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
from datetime import datetime

from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.queue import api
from senaite.queue import messageFactory as _

from bika.lims.browser import BrowserView


class TasksView(BrowserView):
    """View that displays the on-going and queued tasks
    """
    template = ViewPageTemplateFile("templates/tasks.pt")

    def __init__(self, context, request):
        super(TasksView, self).__init__(context, request)
        self.context = context
        self.request = request
        self._queue_tool = None

    def __call__(self):
        self.request.set("disable_border", 1)
        self.request.set("disable_plone.rightcolumn", 1)

        remove_uid = self.request.get("remove")
        if remove_uid:
            # Remove the task
            self.remove_task(remove_uid)
            return self.redirect()

        requeue_uid = self.request.get("requeue")
        if requeue_uid:
            # Requeue the task
            self.requeue_task(requeue_uid)
            return self.redirect()

        return self.template()

    def redirect(self, url=None):
        if not url:
            url = "{}/queue_tasks".format(self.portal_url)
        self.request.response.redirect(url)

    @property
    def queue_tool(self):
        return api.get_queue()

    def remove_task(self, tuid):
        self.queue_tool.remove(tuid)

    def requeue_task(self, tuid):
        qtool = self.queue_tool
        task = qtool.get_task(tuid)
        if task:
            qtool.remove(tuid)
            task.retries = api.get_max_retries()
            qtool.add(task)

    def get_tasks(self):
        # Failed tasks
        failed = self.queue_tool._storage.failed_tasks
        tasks = map(lambda task: self.get_task_data(dict(task), "failed"), failed)

        # Undergoing task
        current = self.queue_tool._storage.running_tasks
        current = current and self.get_task_data(dict(current[0]), "active") or None
        if current:
            tasks.append(current)

        # Awaiting tasks
        queued = self.queue_tool._storage.tasks
        queued = map(lambda task: self.get_task_data(dict(task), "queued"), queued)
        tasks.extend(reversed(queued))

        # Remove empties
        return filter(None, tasks)

    def get_task_data(self, task, status_id):
        """Adds additional metadata to the task for the template
        """
        if not task:
            return None
        created = task.get("created") or time.time()
        task["task_status_id"] = status_id
        task["task_status"] = _(status_id)
        task["created_date"] = datetime.fromtimestamp(int(created)).isoformat()
        return task

    def get_task_json(self, task):
        """Returns the url that displays the task in JSON format
        """
        return "{}/queue_task?uid={}".format(self.portal_url, task["task_uid"])
