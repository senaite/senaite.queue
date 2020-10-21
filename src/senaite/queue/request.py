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

from requests.exceptions import ConnectionError
from requests.exceptions import HTTPError
from requests.exceptions import Timeout
from requests.exceptions import TooManyRedirects
from senaite.jsonapi import api as japi
from senaite.jsonapi.exceptions import APIError
from senaite.queue import logger


def handle_queue_errors(func):
    """Decorator that handles errors/exceptions from queue requests gracefully
    """
    def wrapper(*args, **kwargs):
        try:
            if japi.is_anonymous():
                # 401 Unauthorized, user needs to authenticate
                fail(401, "Unauthorized")
            return func(*args, **kwargs)
        except ConnectionError:
            # Queue server refused the connection (probably stopped)
            fail(504, "Queue Server Timeout. Refused connection")
        except Timeout:
            # Queue server timeout
            fail(504, "Queue Server Timeout. Busy")
        except TooManyRedirects:
            fail(500, "Internal Server Error. Too many redirects")
        except HTTPError as e:
            status = e.response.status_code or 500
            message = e.response.json() or {}
            message = message.get("message", str(e))
            fail(status, message)
        except APIError as e:
            fail(e.status, e.message)
        except Exception as e:
            msg = "{}: {}".format(type(e).__name__, str(e))
            fail(500, "Internal Server Error. {}".format(msg))

    return wrapper


def fail(status_code, message):
    """Raises an API error
    """
    japi.fail(status_code, message)


def get_summary(message, endpoint):
    """Returns a dict that represents a summary of the request outcome
    """
    logger.info(message)
    return {
        "message": message,
        "url": japi.url_for("senaite.queue.consumer.{}".format(endpoint))
    }
