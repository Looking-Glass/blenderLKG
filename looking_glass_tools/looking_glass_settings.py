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

import ctypes
import bpy

def init():
	global hp
	global numDevices

	hp = ctypes.cdll.LoadLibrary(bpy.context.preferences.addons['looking_glass_tools'].preferences.filepath)

	# initialize HoloPlayCore plugin 
	hp.hpc_InitializeApp("BlenderLookingGlassAddon")

	# some lines to test the HoloPlayCore service after initialization:
	hp_serviceVersion = ctypes.create_string_buffer(6)
	hp.hpc_GetHoloPlayServiceVersion(hp_serviceVersion, 6)
	print("HoloPlay service version: " + str(hp_serviceVersion.value))

	hp_coreVersion = ctypes.create_string_buffer(6)
	hp.hpc_GetHoloPlayCoreVersion(hp_coreVersion, 6)
	print("HoloPlay core version: " + str(hp_coreVersion.value))

	numDevices = int(hp.hpc_GetNumDevices())
	print("Number of devices found: " + str(numDevices))

	print("Init Settings")