#  Copyright 2020-2021 Dragorn421
#
#  This objex2 addon is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This objex2 addon is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this objex2 addon.  If not, see <https://www.gnu.org/licenses/>.

import bpy

import json

from . import blender_version_compatibility

def quote(s):
    return json.dumps(s)

class ObjexExportAbort(Exception):
    def __init__(self, reason):
        self.reason = reason

def detect_zztag(log, name):
    if (name[0:2] == 'ZZ'
        or any(suspicious_string in name for suspicious_string in ('_ZZ', '#ZZ', '|ZZ'))
    ):
        log.warning('Found what may be an ancient ZZ-tag in name {}\n'
            'Those are not used at all anymore and will be ignored', name)

def get_addon_version():
    return addon_version

def get_addon_preferences():
    addons_preferences = blender_version_compatibility.get_preferences(bpy.context).addons
    if __package__ in addons_preferences:
        return addons_preferences[__package__].preferences
    else:
        return None
