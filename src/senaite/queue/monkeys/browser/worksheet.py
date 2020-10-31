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

from bika.lims import api as capi
from senaite.queue import api


def handle_submit(self):
    """Handle form submission for the assignment of a WorksheetTemplate
    """
    wst_uid = self.request.form.get("getWorksheetTemplate")
    if not wst_uid:
        return False

    # Do not allow the assignment of a worksheet template when queued
    if api.is_queued(self.context):
        return False

    # Current context is the worksheet
    worksheet = self.context
    layout = worksheet.getLayout()

    # XXX For what is this used?
    self.request["context_uid"] = capi.get_uid(worksheet)

    # Apply the worksheet template to this worksheet
    wst = capi.get_object_by_uid(wst_uid)
    worksheet.applyWorksheetTemplate(wst)

    # Are there tasks queued for this Worksheet?
    if api.is_queue_enabled():
        queue = api.get_queue()
        tasks = queue.get_tasks_for(worksheet)
        if tasks:
            return True

    # Maybe the queue has not been used (disabled?)
    new_layout = worksheet.getLayout()
    if len(new_layout) != len(layout):
        # Layout has changed. Assume the analyses were added
        return True

    return False
