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

from senaite.queue import PRODUCT_NAME
from senaite.queue import PROFILE_ID
from senaite.queue import logger
from senaite.queue.interfaces import IQueueDispatcher

from bika.lims.upgrade import upgradestep
from bika.lims.upgrade.utils import UpgradeUtils

version = "1.0.1"


@upgradestep(PRODUCT_NAME, version)
def upgrade(tool):
    portal = tool.aq_inner.aq_parent
    setup = portal.portal_setup
    ut = UpgradeUtils(portal)
    ver_from = ut.getInstalledVersion(PRODUCT_NAME)

    if ut.isOlderVersion(PRODUCT_NAME, version):
        logger.info("Skipping upgrade of {0}: {1} > {2}".format(
            PRODUCT_NAME, ver_from, version))
        return True

    logger.info("Upgrading {0}: {1} -> {2}".format(PRODUCT_NAME, ver_from, version))

    # -------- ADD YOUR STUFF BELOW --------

    # https://github.com/senaite/senaite.queue/pull/3
    setup.runImportStepFromProfile(PROFILE_ID, "plone.app.registry")
    setup.runImportStepFromProfile(PROFILE_ID, "actions")

    # Remove queue dispatcher utility, that is no longer used
    setup.runImportStepFromProfile(PROFILE_ID, "componentregistry")
    remove_queue_dispatcher_utility(portal)

    logger.info("{0} upgraded to version {1}".format(PRODUCT_NAME, version))
    return True


def remove_queue_dispatcher_utility(portal):
    logger.info("Removing IQueueDispatcher utility ...")
    sm = portal.getSiteManager()
    sm.unregisterUtility(provided=IQueueDispatcher)
    util = sm.queryUtility(IQueueDispatcher)
    if util:
        del util
        sm.utilities.unsubscribe((), IQueueDispatcher)
        del sm.utilities.__dict__['_provided'][IQueueDispatcher]

    logger.info("Removed IQueueDispatcher utility ...")
