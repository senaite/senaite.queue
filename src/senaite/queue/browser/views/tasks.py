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

import pygal
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from pygal.style import LightenStyle
from senaite.queue import messageFactory as _
from senaite.queue.storage import QueueStorageTool

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
        if not self._queue_tool:
            self._queue_tool = QueueStorageTool()
        return self._queue_tool

    def remove_task(self, tuid):
        qtool = self.queue_tool
        task = qtool.get_task(tuid)
        if task:
            qtool.remove(task)

    def requeue_task(self, tuid):
        qtool = self.queue_tool
        task = qtool.get_task(tuid)
        if task:
            task.retries = 0
            qtool.requeue(task)

    def get_tasks(self):
        # Failed tasks
        failed = self.queue_tool.failed
        tasks = map(lambda task: self.get_task_data(task, "failed"), failed)

        processed = self.queue_tool.processed
        current = self.queue_tool.current

        # Last processed task
        if processed and processed != current:
            processed = self.get_task_data(processed, "processed")
            tasks.append(processed)

        # Undergoing task
        current = self.get_task_data(current, "active")
        if current:
            tasks.append(current)

        # Awaiting tasks
        queued = self.queue_tool.tasks
        queued = map(lambda task: self.get_task_data(task, "queued"), queued)
        tasks.extend(queued)

        # Remove empties
        return filter(None, tasks)

    def get_task_data(self, task, status_id):
        """Adds additional metadata to the task for the template
        """
        if not task:
            return None
        task["task_status_id"] = status_id
        task["task_status"] = _(status_id)
        return task

    def get_task_json(self, task):
        """Returns the url that displays the task in JSON format
        """
        return "{}/queue_task?uid={}".format(self.portal_url, task.task_uid)

    def get_statistics_chart(self):
        """Generates a SVG with queue statistics
        """
        # Chart style
        style = LightenStyle('#254a55',
                             step=5,
                             background='transparent',
                             legend_font_size=12)

        # Stacked bar chart
        chart = pygal.StackedBar(fill=True,
                                 style=style,
                                 height=200,
                                 spacing=5,
                                 margin_left=0,
                                 margin_right=0,
                                 max_scale=5,
                                 legend_at_bottom=True,
                                 legend_box_size=8,
                                 pretty_print=True,
                                 explicit_size=True)

        # Get the data lines from queue's statistics
        statistics = self.queue_tool.statistics
        keys = statistics[0].keys()
        transposed = {k: map(lambda item: item[k], statistics) for k in keys}

        # Add the data lines to the chart
        chart.add(_("Queued"), transposed["queued"])
        chart.add(_("Added"), transposed["added"])
        chart.add(_("Removed"), transposed["removed"])
        chart.add(_("Processed"), transposed["processed"])
        chart.add(_("Failed"), transposed["failed"])

        # Render the SVG
        return chart.render()
