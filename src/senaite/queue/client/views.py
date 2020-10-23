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

from Products.Five.browser import BrowserView
from senaite.queue.client import consumer


class ConsumerView(BrowserView):
    """View that handle the "consume" HTTP endpoint
    """
    def __call__(self):
        msg = consumer.consume_task()
        return msg


"""
{'__doc__': None,
 '__provides__': <zope.interface.Provides object at 0x7fd99842a990>,
 '_auth': 'Basic endhbWluOnp3YW1pbg==',
 '_client_addr': '0',
 '_debug': <zope.publisher.base.DebugFlags object at 0x7fd998640e90>,
 '_held': (<App.ZApplication.Cleanup instance at 0x7fd997e58cb0>,
           <Products.PluggableAuthService.PluggableAuthService.ResponseCleanup instance at 0x7fd9b08507e8>,
           <Products.CMFCore.Skinnable.SkinDataCleanup instance at 0x7fd9987acdd0>,
           <Products.PluggableAuthService.PluggableAuthService.ResponseCleanup instance at 0x7fd9981b9b48>),
 '_lazies': {'SESSION': <bound method SessionDataManager.getSessionData of <SessionDataManager at /session_data_manager>>},
 '_locale': [],
 '_orig_env': {'GATEWAY_INTERFACE': 'CGI/1.1',
               'HTTP_ACCEPT': 'text/html,text/plain',
               'HTTP_AUTHORIZATION': 'Basic endhbWluOnp3YW1pbg==',
               'HTTP_HOST': 'localhost:9093',
               'HTTP_USER_AGENT': 'Zope Clock Server Client',
               'PATH_INFO': '/senaite/queue_consumer',
               'PATH_TRANSLATED': '/senaite/queue_consumer',
               'REMOTE_ADDR': '0',
               'REQUEST_METHOD': 'GET',
               'SCRIPT_NAME': '',
               'SERVER_NAME': 'Zope Clock Server',
               'SERVER_PORT': 'Clock',
               'SERVER_PROTOCOL': 'HTTP/1.0',
               'SERVER_SOFTWARE': 'Zope',
               'channel.creation_time': 1603471296.737946},
 '_plonebrowserlayer_': True,
 '_plonetheme_': True,
 '_script': [],
 '_steps': ['senaite', 'queue_consumer'],
 '_urls': (),
 'base': 'http://localhost:9093',
 'cookies': {},
 'environ': {'GATEWAY_INTERFACE': 'CGI/1.1',
             'HTTP_ACCEPT': 'text/html,text/plain',
             'HTTP_HOST': 'localhost:9093',
             'HTTP_USER_AGENT': 'Zope Clock Server Client',
             'PATH_INFO': '/senaite/queue_consumer',
             'PATH_TRANSLATED': '/senaite/queue_consumer',
             'QUERY_STRING': '',
             'REMOTE_ADDR': '0',
             'REQUEST_METHOD': 'GET',
             'SCRIPT_NAME': '',
             'SERVER_NAME': 'Zope Clock Server',
             'SERVER_PORT': 'Clock',
             'SERVER_PROTOCOL': 'HTTP/1.0',
             'SERVER_SOFTWARE': 'Zope',
             'channel.creation_time': 1603471296.737946},
 'form': {},
 'other': {'ACTUAL_URL': 'http://localhost:9093/senaite/queue_consumer',
           'AUTHENTICATED_USER': <PloneUser 'zwamin'>,
           'AUTHENTICATION_PATH': 'senaite',
           'LANGUAGE': u'en-us',
           'LANGUAGE_TOOL': <Products.PloneLanguageTool.LanguageTool.LanguageBinding instance at 0x7fd9981b9e60>,
           'PARENTS': [<PloneSite at /senaite>, <Application at >],
           'PUBLISHED': <Products.Five.metaclass.ConsumerView object at 0x7fd998290790>,
           'RESPONSE': ZServerHTTPResponse(''),
           'SERVER_URL': 'http://localhost:9093',
           'TraversalRequestNameStack': [],
           'URL': 'http://localhost:9093/senaite/queue_consumer',
           'method': 'GET'},
 'path': [],
 'response': ZServerHTTPResponse(''),
 'roles': ('LabClerk', 'LabManager', 'Manager', '_senaite_core__Manage_Bika_Permission'),
 'script': 'http://localhost:9093',
 'stdin': <StringIO.StringIO instance at 0x7fd9985aecf8>,
 'steps': ['senaite', 'queue_consumer'],
 'taintedcookies': {},
 'taintedform': {}}

"""

