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
    except:  # noqa a convenient way to check if the key is ok
        return False


def valid_url_constraint(value):
    """Return true if the value is a well-formed url
    """
    try:
        result = parse.urlparse(value)
        return all([result.scheme, result.netloc, result.path])
    except:  # noqa a convenient way to check if the url is ok
        return False


# Default number of objects per task
DEFAULT_OBJ_TASK = 10


class IQueueControlPanel(Interface):
    """Control panel Settings
    """

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

    default = schema.Int(
        title=_(u"Number of objects to process per task"),
        description=_(
            "Default number of objects to process in a single request when the "
            "task contains multiple items. The items from a task are processed "
            "in chunks, and remaining are re-queued for later. For instance, "
            "when a user selects multiple analyses for their assignment to a "
            "worksheet, only one task is generated. If the value defined is 5, "
            "the analyses will be assigned in chunks of this size, and the "
            "system will keep generating tasks for the remaining analyses "
            "all them are finally assigned. Higher values increment the chance "
            "of transaction commit conflicts, while lower values tend to slow "
            "down the completion of the whole task. "
            "A value of 0 disables queueing if tasks functionality at all. "
            "Default value: {}".format(DEFAULT_OBJ_TASK)
        ),
        min=0,
        max=20,
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
        max=10,
        default=3,
        required=True,
    )

    min_seconds_task = schema.Int(
        title=_(u"Minimum seconds"),
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

    max_seconds_unlock = schema.Int(
        title=_(u"Maximum seconds"),
        description=_(
            "Number of seconds to wait for a task to finish before being "
            "re-queued or considered as failed. System will keep retrying the "
            "task until the value set in 'Maximum retries' is reached, at"
            "which point the task will be definitely considered as failed and "
            "no further actions will take place. "
            "Minimum value: 30, Default value: 120"
        ),
        min=30,
        max=1800,
        default=120,
        required=True,
    )

    auth_key = schema.TextLine(
        title=_(u"Auth secret key"),
        description=_(
            "This secret key is used by senaite.queue to generate an encrypted "
            "token (symmetric encryption) for the authentication of requests "
            "sent by queue clients and workers to the Queue's server API. "
            "Must be 32 url-safe base64-encoded bytes"
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
