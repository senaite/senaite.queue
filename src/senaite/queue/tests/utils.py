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

import json

import collections
import transaction
from DateTime import DateTime
from requests.exceptions import HTTPError
from senaite.queue import api
from senaite.queue.interfaces import IClientQueueUtility
from senaite.queue.interfaces import IServerQueueUtility
from six.moves.urllib import parse
from zope import globalrequest
from zope.component import getUtility

from bika.lims import api as _api
from bika.lims.browser.workflow import WorkflowActionHandler
from bika.lims.utils.analysisrequest import create_analysisrequest
from bika.lims.workflow import doActionFor as do_action_for


def handle_action(context, items_or_uids, action):
    """Simulates the handling of an action when multiple items from a list are
    selected and the action button is pressed
    """
    if not isinstance(items_or_uids, (list, tuple)):
        items_or_uids = [items_or_uids]
    items_or_uids = map(_api.get_uid, items_or_uids)
    request = _api.get_request()
    request.set("workflow_action", action)
    request.set("uids", items_or_uids)
    WorkflowActionHandler(context, request)()


def create_sample(services, client, contact, sample_type, receive=True):
    """Creates a new sample with the specified services
    """
    request = _api.get_request()
    values = {
        'Client': client.UID(),
        'Contact': contact.UID(),
        'DateSampled': DateTime().strftime("%Y-%m-%d"),
        'SampleType': sample_type.UID()
    }
    service_uids = map(_api.get_uid, services)
    sample = create_analysisrequest(client, request, values, service_uids)
    if receive:
        do_action_for(sample, "receive")
    transaction.commit()
    return sample


def get_client_queue(browser, request):
    """Returns the client queue
    """
    queue = getUtility(IClientQueueUtility)
    queue._req = RequestTestHandler(browser, request)
    return queue


def get_server_queue():
    queue = getUtility(IServerQueueUtility)
    return queue


def flush_queue(browser, request):
    """Flushes the queue
    """
    # Flush the client queue
    queue = get_client_queue(browser, request)
    map(queue.delete, queue.get_tasks())

    # And the server queue
    queue = get_server_queue()
    map(queue.delete, queue.get_tasks())


def filter_by_state(brains_or_objects, state):
    """Filters the objects passed in by state
    """
    objs = map(_api.get_object, brains_or_objects)
    return filter(lambda obj: _api.get_review_status(obj) == state, objs)


def process(browser, task_uid):
    """Simulates the processing of the task
    """
    request = _api.get_request()
    site_url = _api.get_url(_api.get_portal())
    url = "{}/@@API/senaite/v1/queue_consumer/process".format(site_url)
    payload = {"task_uid": task_uid}
    browser.post(url, parse.urlencode(payload, doseq=True))

    # We loose the globalrequest each time we do a post with browser
    globalrequest.setRequest(request)

    # Mark the task as done
    api.get_queue().done(task_uid)

    transaction.commit()
    return browser.contents


class ResponseTest(object):
    """A Response object for tests that slightly mimics requests.Response
    """

    def __init__(self, response):
        self.response = response

    def raise_for_status(self):
        if "404 Not Found" in str(self.response.headers):
            Response = collections.namedtuple('Response', 'status_code')
            resp = Response(status_code=404)
            raise HTTPError(response=resp)

    def json(self):
        return json.loads(self.response.contents)


class RequestTestHandler(object):
    """A handler for testing requests that mimics the behavior of requests.post
    """
    def __init__(self, browser, request):
        self.browser = browser
        self.request = request

    def post(self, url, **kwargs):
        """Returns an HTTPResponse
        """
        payload = kwargs.get("json") or {}

        # We simulate error handling in raise_for_status (ala requests)
        self.browser.handleErrors = True
        self.browser.raiseHttpErrors = False
        self.browser.post(url, parse.urlencode(payload, doseq=True))

        # We loose the globalrequest each time we do a post with browser
        globalrequest.setRequest(self.request)

        return ResponseTest(self.browser)
