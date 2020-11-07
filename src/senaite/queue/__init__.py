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

import logging

from AccessControl.Permissions import manage_users
from Products.Archetypes.atapi import listTypes
from Products.Archetypes.atapi import process_types
from Products.CMFCore.permissions import AddPortalContent
from Products.CMFCore.utils import ContentInit
from Products.PluggableAuthService import PluggableAuthService
from senaite.queue.interfaces import ISenaiteQueueLayer
from senaite.queue.pasplugin import add_queue_auth_plugin
from zope.i18nmessageid import MessageFactory  # noqa

PRODUCT_NAME = "senaite.queue"
PROFILE_ID = "profile-{}:default".format(PRODUCT_NAME)
UNINSTALL_PROFILE_ID = "profile-{}:uninstall".format(PRODUCT_NAME)
PAS_PLUGIN_ID = "senaite_queue_auth"

# Defining a Message Factory for when this product is internationalized.
messageFactory = MessageFactory(PRODUCT_NAME)

logger = logging.getLogger(PRODUCT_NAME)


def initialize(context):
    """Initializer called when used as a Zope 2 product."""
    logger.info("*** Initializing SENAITE QUEUE Customization package ***")

    types = listTypes(PRODUCT_NAME)
    content_types, constructors, ftis = process_types(types, PRODUCT_NAME)

    # Register each type with it's own Add permission
    # use ADD_CONTENT_PERMISSION as default
    all_types = zip(content_types, constructors)
    for a_type, constructor in all_types:
        kind = "%s: Add %s" % (PRODUCT_NAME, a_type.portal_type)
        ContentInit(kind,
                    content_types=(a_type,),
                    permission=AddPortalContent,
                    extra_constructors=(constructor, ),
                    fti=ftis,
                    ).initialize(context)

    # Register Queue's PAS plugin
    from pasplugin import QueueAuthPlugin
    PluggableAuthService.registerMultiPlugin(QueueAuthPlugin.meta_type)
    context.registerClass(
        QueueAuthPlugin,
        permission=manage_users,
        constructors=(add_queue_auth_plugin,),
    )


def is_installed():
    """Returns whether the product is installed or not
    """
    from bika.lims import api
    request = api.get_request()
    return ISenaiteQueueLayer.providedBy(request)
