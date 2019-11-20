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
# Copyright 2018-2019 by it's authors.
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
        return self.template()

    @property
    def queue_tool(self):
        if not self._queue_tool:
            self._queue_tool = QueueStorageTool()
        return self._queue_tool

    def get_tasks(self):
        processed = self.queue_tool.processed
        current = self.queue_tool.current
        tasks = []
        if processed and processed != current:
            processed["task_status"] = _("processed")
            tasks.append(processed)

        if self.queue_tool.current:
            current["task_status"] = _("active")
            tasks.append(current)

        for task in self.queue_tool.tasks:
            task["task_status"] = _("queued")
            tasks.append(task)

        return tasks

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
        queued = map(lambda item: item["queued"], statistics)
        added = map(lambda item: item["added"], statistics)
        removed = map(lambda item: item["removed"], statistics)
        processed = map(lambda item: item["processed"], statistics)
        failed = map(lambda item: item["failed"], statistics)

        # Add the data lines to the chart
        chart.add(_("Queued"), queued)
        chart.add(_("Added"), added)
        chart.add(_("Removed"), removed)
        chart.add(_("Processed"), processed)
        chart.add(_("Failed"), failed)

        # Render the SVG
        return chart.render()
