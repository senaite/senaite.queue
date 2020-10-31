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


import threading
import time
import requests

from senaite.queue import api
from senaite.queue import is_installed
from senaite.queue import logger
from senaite.queue.queue import get_max_seconds
from senaite.queue.pasplugin import QueueAuth
from senaite.queue.request import is_valid_zeo_host

from bika.lims import api as _api
from bika.lims.decorators import synchronized
from requests.exceptions import Timeout


CONSUMER_THREAD_PREFIX = "queue.consumer."


@synchronized(max_connections=1)
def consume_task():
    """Consumes a task from the queue, if any
    """
    if not is_installed():
        return info("Queue is not installed")

    host = _api.get_request().get("SERVER_URL")
    if not is_valid_zeo_host(host):
        return error("zeo host not set or not valid: {} [SKIP]".format(host))

    consumer_thread = get_consumer_thread()
    if consumer_thread:
        # There is a consumer working already
        name = consumer_thread.getName()
        return info("Consumer running: {} [SKIP]".format(name))

    logger.info("Queue client: {}".format(host))

    # Server's queue URL
    server = api.get_server_url()

    # Check the status of the queue
    status = api.get_queue_status()
    if status not in ["resuming", "ready"]:
        return warn("Server is {} ({}) [SKIP]".format(status, server))

    if api.is_queue_server():
        message = [
            "Server = Consumer: {}".format(server),
            "*******************************************************",
            "Client configured as both queue server and consumer.",
            "This is not suitable for productive environments!",
            "Change the Queue Server URL in SENAITE's control panel",
            "or setup another zeo client as queue consumer.",
            "Current URL: {}".format(server),
            "*******************************************************"
        ]
        logger.warn("\n".join(message))

    # Pop next task to process
    consumer_id = host
    try:
        task = api.get_queue().pop(consumer_id)
        if not task:
            return info("Queue is empty or process undergoing [SKIP]")
    except Exception as e:
        return error("Cannot pop. {}: {}".format(type(e).__name__, str(e)))

    auth_key = _api.get_registry_record("senaite.queue.auth_key")
    kwargs = {
        "task_uid": task.task_uid,
        "task_username": task.username,
        "consumer_id": consumer_id,
        "base_url": _api.get_url(_api.get_portal()),
        "server_url": api.get_server_url(),
        "user_id": _api.get_current_user().id,
        "max_seconds": get_max_seconds(),
        "auth_key": auth_key,
    }
    name = "{}{}".format(CONSUMER_THREAD_PREFIX, int(time.time()))
    t = threading.Thread(name=name, target=process_task, kwargs=kwargs)
    t.start()

    return info("Consumer running: {} [SKIP]".format(CONSUMER_THREAD_PREFIX))


def process_task(task_uid, task_username, consumer_id, base_url, server_url,
                 user_id, max_seconds, auth_key):
    """Processes the task passed in gracefully
    """
    def post(username, site_url, endpoint, payload, timeout):
        url = "{}/@@API/senaite/v1/{}".format(site_url, endpoint)

        # POST authenticated with the username
        auth = QueueAuth(username, auth_key)
        payload = payload or {}
        response = requests.post(url, json=payload, auth=auth, timeout=timeout)

        # Check the request was successful. Raise exception otherwise
        response.raise_for_status()

    data = {
        "task_uid": task_uid,
        "consumer_id": consumer_id,
        "__zeo": consumer_id
    }
    try:
        # POST to the 'process' endpoint from the Queue's consumer,
        # authenticated as the user who added the task
        post(task_username, base_url, "queue_consumer/process", data,
             timeout=max_seconds)
    except Exception as e:
        # Handle the failed task gracefully
        message = "{}: {}".format(type(e).__name__, str(e))
        print(message)

        endpoint = isinstance(e, Timeout) and "timeout" or "fail"
        err_url = "queue_server/{}".format(endpoint)

        try:
            # POST to the fail/timeout endpoint from the Queue's server,
            # authenticated as the user who initiated the consumer
            data.update({"error_message": message})
            post(user_id, server_url, err_url, data, timeout=5)
        except Exception as e:
            message = "{}: {}".format(type(e).__name__, str(e))
            print(message)
        finally:
            return message

    # Task succeeded
    try:
        # POST to the done endpoint from the Queue's server, authenticated
        # as the user who initiated the consumer
        post(user_id, server_url, "queue_server/done", data, timeout=10)
    except Exception as e:
        message = "{}: {}".format(type(e).__name__, str(e))
        print(message)
        return message

    return "Task processed: {}".format(consumer_id)


def get_consumer_thread():
    """Returns whether there the consumer thread is running
    """
    def is_consumer_thread(t):
        return t.getName().startswith(CONSUMER_THREAD_PREFIX)

    threads = filter(is_consumer_thread, threading.enumerate())
    if len(threads) > 0:
        return threads[0]
    return None


def msg(message, mode="info"):
    func = getattr(logger, mode)
    func(message)
    return message


def info(message):
    return msg(message)


def warn(message):
    return msg(message, mode="warn")


def error(message):
    return msg(message, mode="error")