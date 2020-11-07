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

from Products.PlonePAS.setuphandlers import activatePluginInterfaces
from senaite.queue import logger
from senaite.queue import PAS_PLUGIN_ID
from senaite.queue import PRODUCT_NAME
from senaite.queue import PROFILE_ID
from senaite.queue import UNINSTALL_PROFILE_ID
from senaite.queue.pasplugin import QueueAuthPlugin


def setup_handler(context):
    """Generic setup handler
    """
    if context.readDataFile('senaite.queue.install.txt') is None:
        return

    logger.info("setup handler [BEGIN]".format(PRODUCT_NAME.upper()))
    portal = context.getSite()  # noqa

    # Install the PAS Plugin to allow authenticating tasks as their creators,
    # both in senaite's site and in zope's root to grant access to zope's users
    setup_pas_plugin(portal.getPhysicalRoot())
    setup_pas_plugin(portal)

    logger.info("{} setup handler [DONE]".format(PRODUCT_NAME.upper()))


def setup_pas_plugin(place):
    logger.info("Setting up Queue's PAS plugin ...")

    pas = place.acl_users
    if PAS_PLUGIN_ID not in pas.objectIds():
        plugin = QueueAuthPlugin(title="SENAITE Queue PAS plugin")
        plugin.id = PAS_PLUGIN_ID
        pas._setObject(PAS_PLUGIN_ID, plugin)  # noqa
        logger.info("Created {} in acl_users".format(PAS_PLUGIN_ID))

    plugin = getattr(pas, PAS_PLUGIN_ID)
    if not isinstance(plugin, QueueAuthPlugin):
        raise ValueError(
            "PAS plugin {} is not a QueueAuthPlugin".format(PAS_PLUGIN_ID))

    # Activate all supported interfaces for this plugin
    activatePluginInterfaces(place, PAS_PLUGIN_ID)

    # Make our plugin the first one for some interfaces
    top_interfaces = ["IExtractionPlugin", "IAuthenticationPlugin"]
    plugins = pas.plugins
    for info in pas.plugins.listPluginTypeInfo():
        interface_name = info["id"]
        if interface_name in top_interfaces:
            iface = plugins._getInterfaceFromName(interface_name)  # noqa
            for obj in plugins.listPlugins(iface):
                plugins.movePluginsUp(iface, [PAS_PLUGIN_ID])
                logger.info("Moved {} to top of {}".format(PAS_PLUGIN_ID,
                                                           interface_name))

    logger.info("Setting up Queue's PAS plugin [DONE]")


def pre_install(portal_setup):
    """Runs before the first import step of the *default* profile
    This handler is registered as a *pre_handler* in the generic setup profile
    :param portal_setup: SetupTool
    """
    logger.info("{} pre-install handler [BEGIN]".format(PRODUCT_NAME.upper()))
    context = portal_setup._getImportContext(PROFILE_ID)
    portal = context.getSite()  # noqa

    # Only install senaite.lims once!
    qi = portal.portal_quickinstaller
    if not qi.isProductInstalled("senaite.lims"):
        profile_name = "profile-senaite.lims:default"
        portal_setup.runAllImportStepsFromProfile(profile_name)

    logger.info("{} pre-install handler [DONE]".format(PRODUCT_NAME.upper()))


def post_install(portal_setup):
    """Runs after the last import step of the *default* profile
    This handler is registered as a *post_handler* in the generic setup profile
    :param portal_setup: SetupTool
    """
    logger.info("{} install handler [BEGIN]".format(PRODUCT_NAME.upper()))
    context = portal_setup._getImportContext(PROFILE_ID)  # noqa
    portal = context.getSite()  # noqa

    logger.info("{} install handler [DONE]".format(PRODUCT_NAME.upper()))


def post_uninstall(portal_setup):
    """Runs after the last import step of the *uninstall* profile
    This handler is registered as a *post_handler* in the generic setup profile
    :param portal_setup: SetupTool
    """
    logger.info("{} uninstall handler [BEGIN]".format(PRODUCT_NAME.upper()))

    # https://docs.plone.org/develop/addons/components/genericsetup.html#custom-installer-code-setuphandlers-py
    context = portal_setup._getImportContext(UNINSTALL_PROFILE_ID)  # noqa
    portal = context.getSite()  # noqa

    # Uninstall Queue's PAS plugin, from both Zope's acl_users and site's
    uninstall_pas_plugin(portal.getPhysicalRoot())
    uninstall_pas_plugin(portal)

    logger.info("{} uninstall handler [DONE]".format(PRODUCT_NAME.upper()))


def uninstall_pas_plugin(place):
    """Uninstalls the Queue's PAS Plugin
    """
    pas = place.acl_users
    if PAS_PLUGIN_ID not in pas.objectIds():
        return

    plugin = getattr(pas, PAS_PLUGIN_ID)
    if not isinstance(plugin, QueueAuthPlugin):
        logger.warning(
            "PAS plugin {} is not a QueueAuthPlugin".format(PAS_PLUGIN_ID))
        return

    pas._delObject(PAS_PLUGIN_ID)  # noqa access to protected
    logger.info(
        "Removed QueueAuthPlugin {} from acl_users".format(PAS_PLUGIN_ID))
