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
	"author": "Gottfried Hofmann, Kyle Appelgate",
	"version": (2, 0),
	"blender": (2, 83, 6),
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
else:
	from . import *
	from . looking_glass_render_setup import *
	from . looking_glass_live_view import *
	from . looking_glass_settings import *

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

# global var to store the holoplay core instance
hp = None

def filepath_listener(self, context):
	''' Function to run when the file path of the Holoplay Core library is changed by the user in the addon preferences '''
	global hp
	print("Running filepath update")
	try:			
		# run and initialize holoplay core
		looking_glass_settings.init()
		
		wm = bpy.context.window_manager
		hp = looking_glass_settings.hp

		wm.numDevicesConnected = looking_glass_settings.numDevices
	except:
		print("Loading of Holoplay Core library failed. Is the path set correctly?")

class LookingGlassPreferences(AddonPreferences):
	# this must match the addon name
	bl_idname = __name__
	
	filepath: bpy.props.StringProperty(
			name="Location of libHoloPlayCore",
			subtype='FILE_PATH',
			update=filepath_listener
			)

	def draw(self, context):
		global hp
		layout = self.layout
		if hp != None:
			text = "Please set the location of the Holoplay Core Library here. Usually this should already point to the correct path."
			icon = 'INFO'
		else:
			text = "Loading of Holoplay Core library failed. Please set it's location below, save or close the preferences and restart Blender."
			icon = 'ERROR'
		layout.label(text=text, icon=icon)
		layout.prop(self, "filepath")

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
		layout.operator("lookingglass.window_setup", text="Open LKG Window", icon='WINDOW')
		layout.operator("view3d.offscreen_draw", text="Start/Stop Live View", icon='CAMERA_STEREO')

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
	bpy.types.WindowManager.tilesHorizontal = bpy.props.IntProperty(
			name = "Horizontal Tiles",
			default = 5,
			min = 0,
			max = 100,
			description = "How many views to store horizontally",
			)
	bpy.types.WindowManager.tilesVertical = bpy.props.IntProperty(
			name = "Vertical Tiles",
			default = 9,
			min = 0,
			max = 100,
			description = "How many views to store horizontally",
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
	# 	layout.prop(context.window_manager, "tilesHorizontal")
	# 	layout.prop(context.window_manager, "tilesVertical")

classes = (
	OffScreenDraw,
	looking_glass_window_setup,
	lkgRenderSetup,
	looking_glass_panel,
	looking_glass_render_viewer,
	LookingGlassPreferences,
)

def register():
	global hp
	from bpy.utils import register_class
	for cls in classes:
		register_class(cls)
	bpy.types.IMAGE_MT_view.append(looking_glass_live_view.menu_func)
	bpy.types.VIEW3D_MT_view.append(looking_glass_live_view.menu_func)
	# set the default path to libHoloPlayCore on first registration, can be changed by the user
	fp = bpy.context.preferences.addons['looking_glass_tools'].preferences.filepath
	if fp == '':
		home = pathlib.Path.home()
		sys = platform.system()
		lkgFolderName = "Looking Glass Factory"
		lkgSubFolderName= "Corelibrary"
		if sys.startswith('Darwin'):
			print("Running on Mac OS")
			# convert from PosixPath to string before storing in preferences
			filepath = str(home / "Library/Application Support" / lkgFolderName / lkgSubFolderName / "libHoloPlayCore.dylib")
			# the holoplay library might also reside in the local library
			if not os.path.exists(filepath):
				filepath = str("/Library/Application Support" / lkgFolderName / lkgSubFolderName / "libHoloPlayCore.dylib")
			bpy.context.preferences.addons['looking_glass_tools'].preferences.filepath = filepath
		elif sys.startswith('Windows'):
			print("Running on Windows")
			filepath = str(home / "AppData/Roaming" / lkgFolderName / lkgSubFolderName / "HoloPlayCore.dll")
			bpy.context.preferences.addons['looking_glass_tools'].preferences.filepath = filepath
		elif sys.startswith('Linux'):
			print("Running on Linux")
			filepath = str(home / ".local/share" / lkgFolderName / lkgSubFolderName / "libHoloPlayCore.so")			
			bpy.context.preferences.addons['looking_glass_tools'].preferences.filepath = filepath
	elif not os.path.exists(fp):
		print("Path to libHoloPlayCore is set but file cannot be found.")
		# get the location of the HoloPlayCore SDK lib from user preferences
	
	try:			
		# run and initialize holoplay core
		looking_glass_settings.init()
		
		wm = bpy.context.window_manager
		hp = looking_glass_settings.hp

		wm.numDevicesConnected = looking_glass_settings.numDevices
	except:
		print("Loading of Holoplay Core library failed. Is the path set correctly?")

	print("Registered the live view")

def unregister():
	try:
		looking_glass_settings.hp.hpc_CloseApp()
	except:
		print("Closing of the Holoplay Core App failed.")
	from bpy.utils import unregister_class
	for cls in reversed(classes):
		unregister_class(cls)
	bpy.types.IMAGE_MT_view.remove(looking_glass_live_view.menu_func)
	bpy.types.VIEW3D_MT_view.remove(looking_glass_live_view.menu_func)

if __name__ == "__main__":
	register()
