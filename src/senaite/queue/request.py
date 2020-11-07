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

import time
import traceback

from requests.exceptions import ConnectionError
from requests.exceptions import HTTPError
from requests.exceptions import Timeout
from requests.exceptions import TooManyRedirects
from senaite.jsonapi import request as req
from senaite.jsonapi import api as japi
from senaite.jsonapi.exceptions import APIError
from senaite.queue import logger
from six.moves.urllib import parse

from bika.lims import api as capi


status_reasons = {
    # Informational
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',

    # Successful
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi-Status',
    226: 'IM Used',

    # Redirection
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',
    308: 'Permanent Redirect',

    # Client Error
    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    418: "I'm a teapot",
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    426: 'Upgrade Required',
    428: 'Precondition Required',
    429: 'Too Many Requests',
    431: 'Request Header Fields Too Large',
    451: 'Unavailable for Legal Reasons',

    # Server Error
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    507: 'Insufficient Storage',
    510: 'Not Extended',
    511: 'Network Authentication Required',
}


def handle_queue_errors(func):
    """Decorator that handles queue-specific errors and exceptions gracefully
    """
    def wrapper(*args, **kwargs):
        try:
            if japi.is_anonymous():
                # 401 Unauthorized, user needs to authenticate
                fail(401)
            return func(*args, **kwargs)
        except ConnectionError:
            # Queue server refused the connection (probably stopped)
            fail(504, "Refused connection")
        except Timeout:
            # Queue server timeout
            fail(504, "Busy")
        except TooManyRedirects:
            fail(500, "Too many redirects")
        except HTTPError as e:
            status = e.response.status_code or 500
            message = e.response.json() or {}
            message = message.get("message", str(e))
            fail(status, message)
        except APIError as e:
            raise e
        except Exception as e:
            traceback.print_exc()
            msg = "{}: {}".format(type(e).__name__, str(e))
            fail(500, msg)

    return wrapper


def fail(status_code, message=None):
    """Raises an API error
    :param status_code: HTTP Response status code
    :param message: error message
    """
    reason = [status_reasons.get(status_code), message]
    reason = filter(None, reason)
    reason = reason and " - ".join(reason) or "Unknown reason"
    japi.fail(status_code, reason)


def get_message_summary(message, endpoint, **kwargs):
    """Returns a dict that represents a summary of a message response
    :param message: message to be included in the response
    :param endpoint: endpoint from the request
    :param kwargs: additional (hashable) params to be included in the message
    :return: dict with the summary of the response
    """
    zeo = get_post_zeo()
    logger.info("::{}: {} [{}]".format(endpoint, message, zeo))
    info = kwargs or {}
    info.update({
        "message": message,
        "url": japi.url_for("senaite.queue.{}".format(endpoint)),
        "zeo": zeo,
    })
    return info


def get_tasks_summary(tasks, endpoint, complete=False, **kwargs):
    """Returns a dict that represents a summary of a tasks response
    :param tasks: items to be included in the response
    :param endpoint: endpoint from the request
    :param complete: whether to include the full representation of the tasks
    :param kwargs: additional (hashable) params to be included in the message
    :return: dict with the summary and the list of task representations
    """
    tasks = tasks or []
    if not isinstance(tasks, (list, tuple)):
        tasks = [tasks]

    # Get the information dict of each task
    tasks = filter(None, tasks)
    tasks = map(lambda t: get_task_info(t, complete=complete), tasks)

    zeo = get_post_zeo()
    complete_info = complete and " (complete)" or ""
    logger.info("::{}: {} tasks{} [{}]".format(endpoint, len(tasks),
                                               complete_info, zeo))
    info = kwargs or {}
    info.update({
        "count": len(tasks),
        "items": tasks,
        "url": japi.url_for("senaite.queue.{}".format(endpoint)),
        "zeo": zeo,
    })
    return info


def get_list_summary(items, endpoint, **kwargs):
    """Returns a dict that represents a summary of a list response
    :param items: items to be included in the response
    :param endpoint: endpoint from the request
    :param kwargs: additional (hashable) params to be included in the message
    :return: dict with the summary and the list of items
    """
    items = items or []
    if not isinstance(items, (list, tuple)):
        items = [items]

    # Remove empties
    items = filter(None, items)

    zeo = get_post_zeo()
    logger.info("::{}: {} items [{}]".format(endpoint, len(items), zeo))
    info = kwargs or {}
    info.update({
        "count": len(items),
        "items": items,
        "url": japi.url_for("senaite.queue.{}".format(endpoint)),
        "zeo": zeo,
    })
    return info


def get_task_info(task, complete=True):
    """Return a dict that represents a task, suitable in response summaries
    :param task: QueueTask to be formatted
    :param complete: whether the returning dict has to contain the whole
        information from the task or only the basic information
    """
    if not task:
        return {}

    if complete:
        out_task = dict(task)
    else:
        out_task = {
            "task_uid": task.task_uid,
            "name": task.name,
            "priority": task.priority,
            "status": task.status,
            "created": time.ctime(task.created),
            "retries": task.retries,
            "username": task.username,
        }

    # Include the url of the task
    out_task.update({
        "task_url": get_task_url(task),
    })
    return out_task


def get_task_url(task):
    """Returns the canonical url of the task
    """
    return "/".join([
        capi.get_url(capi.get_portal()),
        "@@API/senaite/v1/queue_server",
        task.task_uid
    ])


def is_valid_zeo_host(host):
    """Returns whether the host passed-in is a valid host
    """
    try:
        result = parse.urlparse(host)
        return all([result.scheme, result.netloc])
    except:  # noqa
        pass
    return False


def get_post_zeo():
    """Returns the value of param "__zeo" from the request's POST. If not
    present or url is not valid, returns empty str
    """
    try:
        req_data = req.get_json()
        result = parse.urlparse(req_data.get("__zeo"))
        if all([result.scheme, result.netloc]):
            return "{}://{}".format(result.scheme, result.netloc).strip()
    except:  # noqa
        pass
    return ""


def get_zeo_site_url():
    """"Returns the base url form the current zeo client
    """
    site_id = capi.get_id(capi.get_portal()).strip("/")
    current_url = capi.get_request().get("SERVER_URL").strip("/")
    return "{}/{}".format(current_url, site_id)
