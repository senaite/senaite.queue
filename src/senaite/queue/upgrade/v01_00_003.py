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
# Copyright 2019-2021 by it's authors.
# Some rights reserved, see README and LICENSE.

from senaite.queue import logger
from senaite.queue import PRODUCT_NAME
from senaite.queue import PROFILE_ID

from bika.lims.upgrade import upgradestep
from bika.lims.upgrade.utils import UpgradeUtils

version = "1.0.3"


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

    logger.info("{0} upgraded to version {1}".format(PRODUCT_NAME, version))
    return True


def setup_top_priority_tasks(tool):
    """Re-imports the registry for the new field "top_priority_tasks" from
    Queue control panel to take effect
    """
    logger.info("Setup tasks with top priority ...")
    portal = tool.aq_inner.aq_parent
    setup = portal.portal_setup
    setup.runImportStepFromProfile(PROFILE_ID, "controlpanel")
    setup.runImportStepFromProfile(PROFILE_ID, "plone.app.registry")
    logger.info("Setup tasks with top priority [DONE]")
