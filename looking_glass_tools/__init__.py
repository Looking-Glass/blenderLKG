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

bl_info = {
	"name": "Looking Glass Toolset",
	"author": "Gottfried Hofmann, Kyle Appelgate, Evan Kahn",
	"version": (3, 1),
	"blender": (2, 92, 0),
	"location": "3D View > Looking Glass Tab",
	"description": "Creates a window showing the viewport from camera view ready for the looking glass display. Builds a render-setup for offline rendering looking glass-compatible images. Allows to view images rendered for looking glass by selecting the first image of the multiview sequence.",
	"wiki_url": "",
	"category": "View",
	}

# required for proper reloading of the addon by using F8
if "bpy" in locals():
	import importlib
	importlib.reload(looking_glass_live_view)
	importlib.reload(looking_glass_render_setup)
	importlib.reload(looking_glass_settings)
	importlib.reload(holoplay_service_api_commands)
else:
	from . import *
	from . looking_glass_render_setup import *
	from . looking_glass_live_view import *
	from . looking_glass_settings import *
	from . holoplay_service_api_commands import *

if "looking_glass_live_view" not in globals():
	message = ("\n\n"
		"The Looking Glass Toolset addon cannot be registered correctly.\n"
		"Please try to remove and install it again.\n"
		"If it still does not work, report it.\n")
	raise Exception(message)

import bpy
import gpu
import json
import subprocess
import logging
import os
import platform
import pathlib
import ctypes
from bgl import *
from math import *
from mathutils import *
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty
from bpy_extras.io_utils import ExportHelper
from . import cbor

# global var to store the holoplay core instance
hp = None

# ------------- The Tools Panel ----------------
class looking_glass_render_viewer(bpy.types.Panel):
		
	""" Looking Glass Render Viewer """ 
	bl_idname = "LKG_PT_panel_tools" # unique identifier for buttons and menu items to reference.
	bl_label = "Looking Glass Tools" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "LKG"

	bpy.types.Scene.LKG_image = bpy.props.PointerProperty(
		name="LKG Image",
		type=bpy.types.Image,
		description = "Multiview Image for LKG"
		)

	def draw(self, context):
		layout = self.layout
		layout.operator("lookingglass.render_setup", text="Create Render Setup", icon='PLUGIN')
		layout.operator("lookingglass.send_quilt_to_holoplay_service", text="Send Quilt to Looking Glass", icon='CAMERA_STEREO')
		layout.operator("lookingglass.save_quilt_as_image", text="Save Quilt to Image Datablock", icon='IMAGE')
		# layout.operator("view3d.offscreen_draw", text="Start/Stop Live View", icon='CAMERA_STEREO')

		row = layout.row(align = True)
		row.label(text = "LKG image to view:")
		row = layout.row(align = True)
		row.template_ID(context.scene, "LKG_image", open="image.open")
		

# ------------- The Config Panel ----------------
class looking_glass_panel(bpy.types.Panel):
		
	""" Looking Glass Properties """ 
	bl_idname = "LKG_PT_panel_config" # unique identifier for buttons and menu items to reference.
	bl_label = "Looking Glass Properties" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "LKG"

	# exposed parameters stored in WindowManager as global props so they 
	# can be changed even when loading the addon (due to config file parsing)
	bpy.types.WindowManager.center = FloatProperty(
			name = "Center",
			default = 0.47,
			min = -1.0,
			max = 1.0,
			description = "Center",
			)

	bpy.types.WindowManager.viewCone = bpy.props.FloatProperty(
			name = "View Cone",
			default = 40.0,
			min = 20.0,
			max = 80.0,
			description = "View Cone",
			)
	bpy.types.WindowManager.screenW = bpy.props.FloatProperty(
			name = "Screen Width",
			default = 2560.0,
			min = 1000.0,
			max = 10000.0,
			description = "Screen width of looking glass display in pixels.",
			)
	bpy.types.WindowManager.screenH = bpy.props.FloatProperty(
			name = "Screen Height",
			default = 1600.0,
			min = 1000.0,
			max = 10000.0,
			description = "Screen height of looking glass display in pixels.",
			)
	bpy.types.WindowManager.aspect = bpy.props.FloatProperty(
			name = "Aspect Ratio",
			default = 0.75,
			min = 0.0,
			max = 100.0,
			description = "Aspect ratio of looking glass display.",
			)
	bpy.types.WindowManager.tileX = bpy.props.IntProperty(
			name = "Horizontal Tiles",
			default = 5,
			min = 0,
			max = 100,
			description = "How many views to store horizontally",
			)
	bpy.types.WindowManager.tileY = bpy.props.IntProperty(
			name = "Vertical Tiles",
			default = 9,
			min = 0,
			max = 100,
			description = "How many views to store vertically",
			)
	bpy.types.WindowManager.quiltX = bpy.props.IntProperty(
			name = "Horizontal Quilt Resolution",
			default = 4096,
			min = 0,
			max = 100000,
			description = "Resolution of the Quilt in X",
			)
	bpy.types.WindowManager.quiltY = bpy.props.IntProperty(
			name = "Vertical Quilt Resolution",
			default = 4096,
			min = 0,
			max = 100000,
			description = "Resolution of the Quilt in Y",
			)
	bpy.types.WindowManager.viewX = bpy.props.IntProperty(
			name = "Horizontal View Resolution",
			default = 819,
			min = 0,
			max = 10000,
			description = "Resolution of an individual view in X",
			)
	bpy.types.WindowManager.viewY = bpy.props.IntProperty(
			name = "Vertical View Resolution",
			default = 455,
			min = 0,
			max = 10000,
			description = "Resolution of an individual view in Y",
			)
	bpy.types.WindowManager.numDevicesConnected = bpy.props.IntProperty(
			name = "Connected Devices",
			default = 0,
			min = 0,
			max = 100,
			description = "How many looking glass devices have been discovered by HoloPlay Service.",
			)
	bpy.types.WindowManager.wm = None

	def draw(self, context):
		wm = context.window_manager
		layout = self.layout
		if wm.numDevicesConnected < 1:
			text="No connected LKG devices found."
			layout.label(text=text, icon='ERROR')
		else:
			text = "Found " + str(wm.numDevicesConnected) + " connected LKG devices."
			layout.label(text=text, icon='CAMERA_STEREO')
			text = "Device type: " + looking_glass_settings.hardwareVersion
			layout.label(text=text)
		layout.operator("lookingglass.reconnect_to_holoplay_service", text="Reconnect to Service", icon='PLUGIN')	

classes = (
	OffScreenDraw,
	lkgRenderSetup,
	looking_glass_panel,
	looking_glass_render_viewer,
	looking_glass_send_quilt_to_holoplay_service,
	looking_glass_save_quilt_as_image,
	looking_glass_reconnect_to_holoplay_service
)

def register():
	global hp
	from bpy.utils import register_class
	for cls in classes:
		register_class(cls)
	
	looking_glass_settings.init()
		
	wm = bpy.context.window_manager
	print("Registered the live view")

def unregister():
	from bpy.utils import unregister_class
	for cls in reversed(classes):
		unregister_class(cls)
	bpy.types.IMAGE_MT_view.remove(looking_glass_live_view.menu_func)
	bpy.types.VIEW3D_MT_view.remove(looking_glass_live_view.menu_func)

if __name__ == "__main__":
	register()
