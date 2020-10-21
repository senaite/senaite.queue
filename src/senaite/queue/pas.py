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
from AccessControl.class_init import InitializeClass
from cryptography.fernet import Fernet
from Products.PluggableAuthService.interfaces.plugins import \
    IAuthenticationPlugin
from Products.PluggableAuthService.interfaces.plugins import IExtractionPlugin
from Products.PluggableAuthService.plugins.BasePlugin import BasePlugin
from Products.PluggableAuthService.utils import classImplements
from senaite.queue.interfaces import ISenaiteQueueLayer

from bika.lims import api


class QueueAuthPlugin(BasePlugin):

    # Meta type name of the Plugin used when registering the plugin in PAS
    meta_type = 'SENAITE Queue Auth Plugin'

    def extractCredentials(self, request):
        """IExtractionPlugin implementation. Extracts login name from the
        request's "X-Queue-Auth-Token" header. This header contains an
        encrypted token with it's expiration date, together with the user name.

        Returns a dict with {'login': <username>} if:
        - current layer is ISenaiteQueueLayer,
        - the token can be decrypted,
        - the decrypted token contains both expiration and username and
        - the the token has not expired (expiration date)

        Returns an empty dict otherwise
        :param request: the HTTPRequest object to extract credentials from
        :return: a dict {"login": <username>} or empty dict
        """
        # Check if request provides ISenaiteQueueLayer
        if not ISenaiteQueueLayer.providedBy(request):
            return {}

        # Read the magical header that contains the encrypted info
        auth_token = request.getHeader("X-Queue-Auth-Token")
        if not auth_token:
            return {}

        # Decrypt the auth_token
        key = api.get_registry_record("senaite.queue.auth_key")
        token = Fernet(str(key)).decrypt(auth_token)

        # Check if token is valid
        tokens = token.split(":")
        if len(tokens) < 2 or not api.is_floatable(tokens[0]):
            return {}

        # Check if token has expired
        expiration = api.to_float(tokens[0])
        if expiration < time.time():
            return {}

        user_id = "".join(tokens[1:])
        return {"login": user_id}

    def authenticateCredentials(self, credentials):
        """IAuthenticationPlugin implementation, maps credentials to a User ID.
        If credentials cannot be authenticated, return None
        :param credentials: dict with {"login": <user_id>}
        :return: a tuple with the user id and login name or None
        """
        # Verify credentials source
        if credentials.get("extractor") != self.getId():
            return None

        # Verify credentials data
        if "login" not in credentials:
            return None

        # Verify user
        pas = self._getPAS()
        info = pas._verifyUser(pas.plugins, user_id=credentials['login'])

        if info is None:
            return None

        # User can authenticate
        return info['id'], info['login']


classImplements(QueueAuthPlugin, IExtractionPlugin, IAuthenticationPlugin)
InitializeClass(QueueAuthPlugin)


def add_queue_auth_plugin():
    # Form for manually adding the plugin, but we do this in
    # setuphandlers.py always.
    pass
