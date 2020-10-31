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

from operator import itemgetter

import collections
from datetime import datetime
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from senaite.core.listing import ListingView
from senaite.queue import api as qapi
from senaite.queue import messageFactory as _
from senaite.queue.queue import get_max_retries
from zope.component.interfaces import implements

from bika.lims import api
from bika.lims.browser.workflow import RequestContextAware
from bika.lims.interfaces import IWorkflowActionUIDsAdapter
from bika.lims.utils import get_link


class TasksListingView(ListingView):
    """BrowserView with the listing of Queued Tasks
    """

    template = ViewPageTemplateFile("templates/tasks.pt")

    def __init__(self, context, request):
        super(TasksListingView, self).__init__(context, request)

        # Query is ignored in `folderitems` method and only there to override
        # the default settings
        self.catalog = "uid_catalog"
        self.contentFilter = {"UID": api.get_uid(context)}

        # Set the view name with `@@` prefix to get the right API URL
        self.__name__ = "@@queue_tasks"

        self.pagesize = 20
        self.show_select_column = True
        self.show_search = False
        self.show_table_footer = True
        self.show_workflow_action_buttons = True

        self.show_categories = False
        self.expand_all_categories = True
        self.categories = []

        self.title = _("Queue monitor")
        self.sort_on = "priority"
        self.sort_order = "ascending"

        self.columns = collections.OrderedDict((
            ("task_short_uid", {
                "title": _("Task UID"),
                "sortable": False,
            }),
            ("priority", {
                "title": _("Priority"),
                "sortable": True,
            }),
            ("created", {
                "title": _("Created"),
                "sortable": True,
            }),
            ("name", {
                "title": _("Name"),
                "sortable": True,
            }),
            ("context_path", {
                "title": _("Context"),
                "sortable": True,
            }),
            ("username", {
                "title": _("Username"),
                "sortable": True,
            }),
            ("status", {
                "title": _("Status"),
                "sortable": True,
            })
        ))

        url = api.get_url(self.context)
        url = "{}/workflow_action?action=".format(url)
        self.review_states = [{
            "id": "default",
            "title": _("Active tasks"),
            "contentFilter": {},
            "columns": self.columns.keys(),
            "transitions": [],
            "custom_transitions": [
                {"id": "queue_requeue",
                 "title": _("Requeue"),
                 "url": "{}{}".format(url, "queue_requeue")},
                {"id": "queue_remove",
                 "title": _("Remove"),
                 "url": "{}{}".format(url, "queue_remove")}
            ],
            "confirm_transitions": [
                "queue_remove",
            ]
        }, {
            "id": "failed",
            "title": _("Failed tasks"),
            "contentFilter": {},
            "columns": self.columns.keys(),
            "transitions": [],
            "custom_transitions": [
                {"id": "queue_requeue",
                 "title": _("Requeue"),
                 "url": "{}{}".format(url, "queue_requeue")},
                {"id": "queue_remove",
                 "title": _("Remove"),
                 "url": "{}{}".format(url, "queue_remove")}
            ],
            "confirm_transitions": [
                "queue_requeue",
            ]
        }, {
            "id": "all",
            "title": _("All tasks +ghosts"),
            "contentFilter": {},
            "columns": self.columns.keys(),
            "transitions": [],
            "custom_transitions": [
                {"id": "queue_requeue",
                 "title": _("Requeue"),
                 "url": "{}{}".format(url, "queue_requeue")},
                {"id": "queue_remove",
                 "title": _("Remove"),
                 "url": "{}{}".format(url, "queue_remove")}
            ],
            "confirm_transitions": [
                "queue_remove",
            ]
        }
        ]

    def update(self):
        """Update hook
        """
        self.request.set("disable_border", 1)
        self.request.set("disable_plone.rightcolumn", 1)
        super(TasksListingView, self).update()

    def folderitems(self):
        states_map = {
            "running": "state-published",
            "failed": "state-retracted",
            "queued": "state-active",
            "ghost": "state-unassigned",
        }
        # flag for manual sorting
        self.manual_sort_on = self.get_sort_on()

        # Get the items
        status = ["running", "queued"]
        if self.review_state.get("id") == "failed":
            status = ["failed"]
        elif self.review_state.get("id") == "all":
            status = ["running", "queued", "failed", "ghost"]

        items = map(self.make_item, qapi.get_queue().get_tasks(status=status))

        # Infere the priorities
        site_url = api.get_url(api.get_portal())
        api_url = "{}/@@API/v1/@@API/senaite/v1/queue_server".format(site_url)
        idx = 1
        for item in items:
            if item["status"] not in ["queued", "running"]:
                priority = 0
            else:
                priority = idx
                idx += 1

            created = datetime.fromtimestamp(int(item["created"])).isoformat()
            context_link = get_link(item["context_path"], item["context_path"])

            task_link = "{}/{}".format(api_url, item["uid"])
            params = {"class": "text-monospace"}
            task_link = get_link(task_link, item["task_short_uid"], **params)

            status_msg = _(item["status"])
            css_class = states_map.get(item["status"])
            if item.get("ghost"):
                css_class = "{} {}".format(css_class, states_map["ghost"])
                status_msg = "{} ({})".format(status_msg, _("ghost"))

            item.update(
                {"priority": str(priority).zfill(4),
                 "state_class": css_class,
                 "replace": {
                     "status": status_msg,
                     "context_path": context_link,
                     "task_short_uid": task_link,
                     "created": created,
                 }}
            )

        # Sort the items
        sort_on = self.manual_sort_on in self.columns.keys() or "priority"
        reverse = self.get_sort_order() == "ascending"
        items = sorted(items, key=itemgetter(sort_on), reverse=reverse)

        # Pagination
        self.total = len(items)
        limit_from = self.get_limit_from()
        if limit_from and len(items) > limit_from:
            return items[limit_from:self.pagesize + limit_from]
        return items[:self.pagesize]

    def make_empty_item(self, **kw):
        """Creates an empty listing item
        :return: a dict that with the basic structure of a listing item
        """
        item = {
            "uid": None,
            "before": {},
            "after": {},
            "replace": {},
            "allow_edit": [],
            "disabled": False,
            "state_class": "state-active",
        }
        item.update(**kw)
        return item

    def make_item(self, task):
        """Makes an item from a QueueTask object
        :param task: QueueTask object to make an item from
        :return: a listing item that represents the QueueTask object
        """
        item = self.make_empty_item()
        item.update({
            "uid": task.task_uid,
            "task_short_uid": task.task_short_uid,
            "priority": task.priority,
            "created": task.created,
            "name": task.name,
            "context_path": task.context_path,
            "username": task.username,
            "status": task.status,
            "ghost": task.get("ghost") or False,
            "disabled": task.status in ["running", ]
        })
        return item

    def get_allowed_transitions_for(self, uids):
        """Overrides get_allowed_transations_for from paranet class. Our UIDs
        are not from objects, but from tasks, so none of them have
        workflow-based transitions
        """
        if not uids:
            return []

        return self.review_state.get("custom_transitions", [])

    def get_transitions_for(self, obj):
        """Overrides get_transitions_for from parent class. Our UIDs are not
        from objects, but from tasks, so none of them have workflow-based
        transitions
        """
        return []


class WorkflowActionRequeueAdapter(RequestContextAware):
    """Adapter in charge of queue tasks' requeue action
    """
    implements(IWorkflowActionUIDsAdapter)

    def __call__(self, action, uids):
        """Re-queues the selected tasks and redirects to the previous URL
        """
        queue = qapi.get_queue()
        for uid in uids:
            task = queue.get_task(uid)
            task.retries = get_max_retries()
            queue.delete(uid)
            queue.add(task)

        url = api.get_url(api.get_portal())
        url = "{}/queue_tasks".format(url)
        return self.redirect(url)


class WorkflowActionRemoveAdapter(RequestContextAware):
    """Adapter in charge of queue tasks' remove action
    """
    implements(IWorkflowActionUIDsAdapter)

    def __call__(self, action, uids):
        """Removes the selected tasks and redirects to the previous URL
        """
        queue = qapi.get_queue()
        map(queue.delete, uids)

        url = api.get_url(api.get_portal())
        url = "{}/queue_tasks".format(url)
        return self.redirect(url)
