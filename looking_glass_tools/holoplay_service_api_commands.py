# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

def hide():
    obj = {
        'cmd': {
            'hide': {},
        },
        'bin': bytes(),
    }
    return obj

def wipe():
    obj = {
        'cmd': {
            'wipe': {},
        },
        'bin': bytes(),
    }
    return obj

def load_quilt(name, settings = 0):
    obj = {
        'cmd': {
            'show': {
                'source': 'cache',
                'quilt': {
                    'name': name
                },
            },
        },
        'bin': bytes(),
    }
    if (settings != 0):
        obj['cmd']['show']['quilt']['settings'] = settings
    return obj

def show_quilt(bindata, settings):
    obj = {
        'cmd': {
            'show': {
                'source': 'bindata',
                'quilt': {
                    'type': 'image',
                    'settings': settings
                }
            },
        },
        'bin': bindata,
    }
    return obj

def cache_quilt(bindata, name, settings):
    obj = {
        'cmd': {
            'cache': {
                'quilt': {
                    'name': name,
                    'type': 'image',
                    'settings': settings
                }
            }
        },
        'bin': bindata,
    }
    return obj
