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


from plone import api as plone_api
from senaite.queue import logger
from senaite.queue import PRODUCT_NAME
from senaite.queue import PROFILE_ID
from senaite.queue.interfaces import IQueued
from senaite.queue.pasplugin import reset_auth_key
from senaite.queue.setuphandlers import setup_pas_plugin
from zope.annotation.interfaces import IAnnotations
from zope.interface import noLongerProvides

from bika.lims import api as _api
from bika.lims.interfaces import IWorksheet
from bika.lims.upgrade import upgradestep
from bika.lims.upgrade.utils import UpgradeUtils

version = "1.0.2"


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

    # Re-import the registry profile to add new settings in control panel
    setup.runImportStepFromProfile(PROFILE_ID, "plone.app.registry")

    # Reset control panel settings to defaults
    reset_settings(portal)

    # Port old storage mechanism
    remove_legacy_storage(portal)

    # Install the PAS Plugin to allow authenticating tasks as their creators
    setup_pas_plugin(portal)

    # Create and store the key to use for auth
    reset_auth_key(portal)

    logger.info("{0} upgraded to version {1}".format(PRODUCT_NAME, version))
    return True


def reset_settings(portal):
    """Reset the settings from registry to match with defaults
    """
    logger.info("Reset Queue settings ...")
    default_settings = {
        "default": 10,
        "max_retries": 3,
        "min_seconds_task": 3,
        "max_seconds_unlock": 120,
    }

    for key, val in default_settings.items():
        registry_key = "senaite.queue.{}".format(key)
        plone_api.portal.set_registry_record(registry_key, val)

    logger.info("Reset Queue settings [DONE]")


def remove_legacy_storage(portal):
    """Removes the legacy storage and removes marker IQueued from objects
    """
    logger.info("Removing legacy storage ...")

    # Main legacy tool for queue management of tasks
    legacy_storage_tool_id = "senaite.queue.main.storage"
    legacy_storage_tasks_id = "senaite.queue.main.storage.tasks"
    setup = _api.get_setup()
    annotations = IAnnotations(setup)

    # Walk through the tasks and remove IQueued marker interface
    tasks_storage = annotations.get(legacy_storage_tasks_id) or {}

    # Queued tasks
    map(remove_queued_task, tasks_storage.get("tasks", []))

    # Failed tasks
    map(remove_queued_task, tasks_storage.get("failed", []))

    # Current task
    remove_queued_task(tasks_storage.get("current"))

    # Last processed task
    remove_queued_task(tasks_storage.get("processed"))

    # Flush main storage annotation
    if annotations.get(legacy_storage_tool_id) is not None:
        del annotations[legacy_storage_tool_id]

    if annotations.get(legacy_storage_tasks_id) is not None:
        del annotations[legacy_storage_tasks_id]

    logger.info("Removing legacy storage [DONE]")


def remove_queued_task(task):
    """Removes the legacy IQueued interface from the queued task
    """
    if not task:
        return
    uid = task.get("context_uid")

    # Remove the legacy IQueued marker interface
    remove_queued(uid)


def remove_queued(uid_brain_object):
    """Removes the legacy IQueued interface from the object passed-in
    """
    obj = _api.get_object(uid_brain_object, default=None)
    if not obj:
        return

    if IQueued.providedBy(obj):
        noLongerProvides(obj, IQueued)

    if IWorksheet.providedBy(obj):
        map(remove_queued, obj.getAnalyses())
