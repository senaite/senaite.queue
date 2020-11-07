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

from Products.Archetypes.config import REFERENCE_CATALOG
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import _createObjectByType
from senaite.queue import api
from senaite.queue import messageFactory as _

from bika.lims import api as _api
from bika.lims.browser.worksheet.views.add_worksheet import AddWorksheetView
from bika.lims.utils import tmpID


class AddWorksheetQueueView(AddWorksheetView):
    """Handler for the "Add Worksheet" button in Worksheet Folder.
    If a template is selected, the worksheet template is applied and user
    redirected back to the "manage_results" view

    N.B. Mostly grabbed from core's worksheet/browser/views/add_worksheet,
         except those parts related with the queue
    """

    def __call__(self):
        # N.B.

        form = self.request.form
        analyst = self.request.get('analyst', '')
        template = self.request.get('template', '')
        instrument = self.request.get('instrument', '')

        if not analyst:
            message = _("Analyst must be specified.")
            self.context.plone_utils.addPortalMessage(message, 'info')
            self.request.RESPONSE.redirect(self.context.absolute_url())
            return

        rc = getToolByName(self.context, REFERENCE_CATALOG)
        wf = getToolByName(self.context, "portal_workflow")
        pm = getToolByName(self.context, "portal_membership")

        ws = _createObjectByType("Worksheet", self.context, tmpID())
        ws.processForm()

        # Set analyst and instrument
        ws.setAnalyst(analyst)
        if instrument:
            ws.setInstrument(instrument)

        # Set the default layout for results display
        ws.setResultsLayout(self.context.bika_setup.getWorksheetLayout())

        # overwrite saved context UID for event subscribers
        self.request['context_uid'] = ws.UID()

        # if no template was specified, redirect to blank worksheet
        if not template:
            ws.processForm()
            self.request.RESPONSE.redirect(ws.absolute_url() + "/add_analyses")
            return

        wst = rc.lookupObject(template)
        ws.applyWorksheetTemplate(wst)

        if ws.getLayout():
            self.request.RESPONSE.redirect(ws.absolute_url() + "/manage_results")

        elif api.is_queued(ws):
            msg = _("Analyses for {} have been queued".format(_api.get_id(ws)))
            self.context.plone_utils.addPortalMessage(msg)
            self.request.RESPONSE.redirect(_api.get_url(ws.aq_parent))

        else:
            msg = _("No analyses were added")
            self.context.plone_utils.addPortalMessage(msg)
            self.request.RESPONSE.redirect(ws.absolute_url() + "/add_analyses")
