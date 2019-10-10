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
# Copyright 2018-2019 by it's authors.
# Some rights reserved, see README and LICENSE.

CHUNK_SIZES = {
    "default": 5,
    "task_action_reject": 5,
    "task_action_retract": 5,
    "task_action_submit": 5,
    "task_action_unassign": 10,
    "task_assign_analyses": 5,
}

# Maximum number of seconds to wait for a process in queue to be finished
# before being considered as failed
MAX_SECONDS_UNLOCK = 600
