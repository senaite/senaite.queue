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

from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from senaite.queue import messageFactory as _
from zope import schema
from zope.interface import Interface


class IQueueControlPanel(Interface):
    """Control panel Settings
    """

    default = schema.Int(
        title=_(u"Default number of objects to process per task"),
        description=_(
            "Default number of objects that will be handled in a single task. "
            "A value of 0 disables queuing of tasks functionality at all, "
            "specific tasks below included."),
        default=5,
        required=True,
    )

    max_retries = schema.Int(
        title=_(u"Maximum retries"),
        description=_(
            "Number of times a task will be re-queued before being considered "
            "as failed and removed from the queue. A value of 0 disables the"
            "re-queue of failing tasks."
        ),
        default=5,
        required=True,
    )

    max_stats_hours = schema.Int(
        title=_(u"Hours to keep in statistics"),
        description=_(
            "Maximum number of hours backwards to keep statistics"
        ),
        default=8,
        required=True,
    )

    task_assign_analyses = schema.Int(
        title=_(u"Number of analyses to assign per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "assigned to a worksheet. Overrides default's for action 'assign'. "
            "A value of 0 disables the queue for this specific action."),
        default=5,
        required=True,
    )

    task_action_unassign = schema.Int(
        title=_(u"Number of analyses to unassign per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "unassigned from a worksheet. Overrides default's for 'unassign' "
            "action. A value of 0 disables the queue for this specific action."),
        default=10,
        required=True,
    )

    task_action_submit = schema.Int(
        title=_(u"Number of analyses to submit per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "result is submitted. Overrides default's for 'submit' action. "
            "A value of 0 disables the queue for this specific action."),
        default=5,
        required=True,
    )

    task_action_verify = schema.Int(
        title=_(u"Number of analyses to verify per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "the analysis is verified. Overrides default's for 'reject' "
            "action. A value of 0 disables the queue for this specific action"),
        default=10,
        required=True,
    )

    task_action_retract = schema.Int(
        title=_(u"Number of analyses to retract per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "the analysis is retracted. Overrides default's for 'retract' "
            "action. A value of 0 disables the queue for this specific action"),
        default=5,
        required=True,
    )

    task_action_reject = schema.Int(
        title=_(u"Number of analyses to reject per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "the analysis is rejected. Overrides default's for 'reject' "
            "action. A value of 0 disables the queue for this specific action"),
        default=10,
        required=True,
    )

    max_seconds_unlock = schema.Int(
        title=_(u"Seconds to wait before unlock"),
        description=_(
            "Number of seconds to wait for a process in queue to be finished "
            "before being considered as failed. Failed processes will be "
            "enqueued again"),
        default=600,
        required=True,
    )


class QueueControlPanelForm(RegistryEditForm):
    schema = IQueueControlPanel
    schema_prefix = "senaite.queue"
    label = _("SENAITE QUEUE Settings")


QueueControlPanelView = layout.wrap_form(QueueControlPanelForm,
                                         ControlPanelFormWrapper)
