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

import requests
import threading
import time
from senaite.queue import api
from senaite.queue import is_installed
from senaite.queue import logger
from senaite.queue.client.utility import QueueAuth

from bika.lims import api as _api
from bika.lims.decorators import synchronized

# Prefix for the name of the thread in charge of notifying consumer
CONSUMER_THREAD_PREFIX = "queue.consumer."


@synchronized(max_connections=1)
def consume_task():
    """Consumes a task from the queue, if any
    """
    logger.info("Consuming task ...")
    if not is_installed():
        msg = "Queue is not installed [SKIP]"
        logger.warn(msg)
        return msg

    status = api.get_queue_status()
    if status not in ["resuming", "ready"]:
        server = api.get_server_url()
        msg = "Server is {} ({}) [SKIP]".format(status, server)
        logger.warn(msg)
        return msg

    if api.is_queue_server():
        server_url = api.get_server_url()
        msg = [
            "Server = Consumer: {}".format(server_url),
            "*******************************************************",
            "Client configured as both queue server and consumer.",
            "This is not suitable for productive environments!",
            "Change the Queue Server URL in SENAITE's control panel",
            "or setup another zeo client as queue consumer.",
            "Current URL: {}".format(server_url),
            "*******************************************************"
        ]
        logger.warn("\n".join(msg))

    # Pop next task to process
    consumer_id = "{}{}".format(CONSUMER_THREAD_PREFIX, int(time.time()))
    try:
        task = api.get_queue().pop(consumer_id)
    except Exception as e:
        msg = "Cannot pop [SKIP]. {}: {}".format(type(e).__name__, str(e))
        logger.error(msg)
        return msg

    if not task:
        # No task to process
        msg = "Queue is empty or process undergoing [SKIP]"
        logger.info(msg)
        return msg

    # Start a new thread
    kwargs = {
        "site_url": _api.get_url(_api.get_portal()),
        "server_url": api.get_server_url(),
        "task_uid": task.task_uid,
        "userid": _api.get_current_user().id,
        "task_userid": task.username,
        "timeout": task.get("max_seconds", api.get_max_seconds()),
    }
    new_consumer(**kwargs)
    #t = threading.Thread(name=consumer_id, target=new_consumer, kwargs=kwargs)
    #t.start()

    msg = "Consumer started: {}".format(consumer_id)
    logger.info(msg)
    return msg


def new_consumer(site_url, server_url, task_uid, userid, task_userid, timeout):

    def log(message, status="info"):
        print("*** wOrkIn~ {} {}".format(status.upper(), message))

    def post(username, base_url, endpoint, payload):
        url = "{}/@@API/senaite/v1/{}".format(base_url, endpoint)

        # POST authenticated with the username
        auth = QueueAuth(username)
        payload = payload or {}
        log(url, "info")
        response = requests.post(url, json=payload, auth=auth)

        # Check the request was successful. Raise exception otherwise
        response.raise_for_status()

    payload = {"taskuid": task_uid}
    try:
        # POST to the 'process' endpoint from the Queue's consumer,
        # authenticated as the user who added the task
        # TODO Implement timeout here!
        post(task_userid, site_url, "queue_consumer/process", payload)
    except Exception as e:
        # Handle the failed task gracefully
        # *** NOTE: We don't have context here
        msg = "{}: {}".format(type(e).__name__, str(e))
        log(msg, "error")
        try:
            # POST to the fail endpoint from the Queue's server, authenticated
            # as the user who initiated the consumer
            payload.update({"error_message": msg})
            post(userid, server_url, "queue_server/fail", payload)
        except Exception as e:
            msg = "{}: {}".format(type(e).__name__, str(e))
            log(msg, "error")
        finally:
            return

    # Task succeeded
    try:
        # POST to the done endpoint from the Queue's server, authenticated
        # as the user who initiated the consumer
        post(userid, server_url, "queue_server/done", payload)
    except Exception as e:
        msg = "{}: {}".format(type(e).__name__, str(e))
        log(msg, "error")


def get_consumer():
    """Returns the consumer thread that is currently running, if any
    :return: threading.Thread
    """
    def is_consumer_thread(t):
        return t.getName().startswith(CONSUMER_THREAD_PREFIX)

    threads = filter(is_consumer_thread, threading.enumerate())
    if len(threads) > 0:
        return threads[0]
    return None
