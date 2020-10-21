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

import base64
import os

from bika.lims import api
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.z3cform import layout
from Products.CMFPlone.utils import safe_unicode
from senaite.queue import messageFactory as _
from six.moves.urllib import parse
from zope import schema
from zope.interface import Interface


def auth_key_constraint(value):
    """Return true if the value is a 32 url-safe base64-encoded bytes
    """
    try:
        key = base64.urlsafe_b64decode(str(value))
        return len(key) == 32
    except:
        return False


def valid_url_constraint(value):
    """Return true if the value is a well-formed url
    """
    try:
        result = parse.urlparse(value)
        return all([result.scheme, result.netloc, result.path])
    except:
        return False


# Default number of objects per task
DEFAULT_OBJ_TASK = 5


class IQueueControlPanel(Interface):
    """Control panel Settings
    """

    default = schema.Int(
        title=_(u"Default number of objects to process per task"),
        description=_(
            "Default number of objects that will be handled in a single task. "
            "A value of 0 disables queuing of tasks functionality at all, "
            "specific tasks below included. "
            "Default value: {}".format(DEFAULT_OBJ_TASK)
        ),
        min=0,
        max=10,
        default=DEFAULT_OBJ_TASK,
        required=True,
    )

    max_retries = schema.Int(
        title=_(u"Maximum retries"),
        description=_(
            "Number of times a task will be re-queued before being considered "
            "as failed. A value of 0 disables the re-queue of failing tasks. "
            "Default value: 3"
        ),
        min=0,
        max=5,
        default=3,
        required=True,
    )

    min_seconds_task = schema.Int(
        title=_(u"Minimum seconds per task"),
        description=_(
            "Minimum number of seconds to book per task. If the task is "
            "performed very rapidly, it will have priority over a transaction "
            "done from userland. In case of conflict, the transaction from "
            "userland will fail and will be retried up to 3 times. This "
            "setting makes the thread that handles the task to take some time "
            "to complete, thus preventing threads from userland to be delayed "
            "or fail. Default value: 3"
        ),
        min=3,
        max=30,
        default=3,
        required=True,
    )

    task_assign_analyses = schema.Int(
        title=_(u"Number of analyses to assign per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "assigned to a worksheet. Overrides default's for action 'assign'. "
            "A value of 0 disables the queue for this specific action. "
            "Default value: {}".format(DEFAULT_OBJ_TASK)
        ),
        min=0,
        max=10,
        default=DEFAULT_OBJ_TASK,
        required=True,
    )

    task_action_unassign = schema.Int(
        title=_(u"Number of analyses to unassign per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "unassigned from a worksheet. Overrides default's for 'unassign' "
            "action. A value of 0 disables the queue for this specific action. "
            "Default value: {}".format(DEFAULT_OBJ_TASK)
        ),
        min=0,
        max=10,
        default=DEFAULT_OBJ_TASK,
        required=True,
    )

    task_action_submit = schema.Int(
        title=_(u"Number of analyses to submit per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "results are submitted. Overrides default's for 'submit' action. "
            "A value of 0 disables the queue for this specific action. "
            "Default value: {}".format(DEFAULT_OBJ_TASK)
        ),
        min=0,
        max=10,
        default=DEFAULT_OBJ_TASK,
        required=True,
    )

    task_action_verify = schema.Int(
        title=_(u"Number of analyses to verify per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "the analysis is verified. Overrides default's for 'reject' "
            "action. A value of 0 disables the queue for this specific action. "
            "Default value: {}".format(DEFAULT_OBJ_TASK)
        ),
        min=0,
        max=10,
        default=DEFAULT_OBJ_TASK,
        required=True,
    )

    task_action_retract = schema.Int(
        title=_(u"Number of analyses to retract per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "the analysis is retracted. Overrides default's for 'retract' "
            "action. A value of 0 disables the queue for this specific action. "
            "Default value: {}".format(DEFAULT_OBJ_TASK)
        ),
        min=0,
        max=10,
        default=DEFAULT_OBJ_TASK,
        required=True,
    )

    task_action_reject = schema.Int(
        title=_(u"Number of analyses to reject per task"),
        description=_(
            "Number of analyses that will be handled in a single task when "
            "the analysis is rejected. Overrides default's for 'reject' "
            "action. A value of 0 disables the queue for this specific action. "
            "Default value: {}".format(DEFAULT_OBJ_TASK)
        ),
        min=0,
        max=10,
        default=DEFAULT_OBJ_TASK,
        required=True,
    )

    max_seconds_unlock = schema.Int(
        title=_(u"Seconds to wait before unlock"),
        description=_(
            "Number of seconds to wait for a process in queue to be finished "
            "before being considered as failed. Failed processes will be "
            "enqueued again. "
            "Minimum value: 30, Default value: 120"
        ),
        min=30,
        max=1800,
        default=120,
        required=True,
    )

    server = schema.TextLine(
        title=_(u"Queue server"),
        description=_(
            "URL of the zeo client that will act as the queue server. This is, "
            "the zeo client others will rely on regarding tasks addition, "
            "retrieval and removal. An empty value or a non-reachable queue "
            "server disables the asynchronous processing of tasks. In such "
            "case, system will behave as if senaite.queue was not installed"
        ),
        default=u"http://localhost:8080/senaite",
        constraint=valid_url_constraint,
        required=False,
    )

    consumer = schema.TextLine(
        title=_(u"Queue consumer"),
        description=_(
            "URL of the zeo client that will act as a queue consumer. This "
            "zeo client will keep asking the queue server for tasks and "
            "sequentially process them thereafter. An empty value does not "
            "disable the queuing, but tasks won't be processed."
        ),
        default=u"http://localhost:8080/senaite",
        constraint=valid_url_constraint,
        required=False,
    )

    auth_key = schema.TextLine(
        title=_(u"Auth secret key"),
        description=_(
            "This secret key is used by senaite.queue to generate an encrypted "
            "token for the authentication of requests sent by queue clients "
            "and workers to the Queue's server API. Must be 32 url-safe "
            "base64-encoded bytes"
        ),
        default=safe_unicode(base64.urlsafe_b64encode(os.urandom(32))),
        constraint=auth_key_constraint,
        required=True,
    )


class QueueControlPanelForm(RegistryEditForm):
    schema = IQueueControlPanel
    schema_prefix = "senaite.queue"
    label = _("SENAITE QUEUE Settings")


QueueControlPanelView = layout.wrap_form(QueueControlPanelForm,
                                         ControlPanelFormWrapper)
