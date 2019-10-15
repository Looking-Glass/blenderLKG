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
	"version": (1, 9),
	"blender": (2, 80, 0),
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
else:
	from . import *
	from . looking_glass_render_setup import *
	from . looking_glass_live_view import *


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
from bgl import *
from math import *
from mathutils import *
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty


# TODO: Make this a class method
def set_defaults():
	''' Returns the file path of the configuration utility shipping with the addon '''
	script_file = os.path.realpath(__file__)
	directory = os.path.dirname(script_file)
	filepath = ''

	if platform.system() == "Linux":
		filepath = directory + "/c_calibration_loader_linux_x86"
	elif platform.system() == "Windows":
		filepath = directory + "\c_calibration_loader_win.exe"
	elif platform.system() == "Darwin":
		filepath = directory + "/c_calibration_loader_mac"
	else:
		print("Operating system not recognized, path to calibration utility nees to be set manually.")
		return ''
	
	if os.path.isfile(filepath):
		return filepath
	else:
		print("Could not find pre-installed calibration loader")
		return ''

class LookingGlassPreferences(AddonPreferences):
	# this must match the addon name
	bl_idname = __name__

	filepath: bpy.props.StringProperty(
			name="Location of the Config Extration Utility",
			subtype='FILE_PATH',
			default = set_defaults()
			)

	def draw(self, context):
		layout = self.layout
		layout.prop(self, "filepath")

# ------------- The Tools Panel ----------------
class looking_glass_render_viewer(bpy.types.Panel):
		
	""" Looking Glass Render Viewer """ 
	bl_idname = "lookingglass.panel_tools" # unique identifier for buttons and menu items to reference.
	bl_label = "Looking Glass Tools" # display name in the interface.
	bl_space_type = "PROPERTIES"
	bl_region_type = "WINDOW"
	#bl_context = '.objectmode'
	#bl_category = "Looking Glass"

	# the pointer property only works in Blender 2.79 or higher
	# older versions will crash
	bpy.types.Scene.LKG_image = bpy.props.PointerProperty(
		name="LKG Image",
		type=bpy.types.Image,
		description = "Multiview Image for LKG"
		)

	def draw(self, context):
		layout = self.layout
		layout.operator("lookingglass.render_setup", text="Create Render Setup", icon='PLUGIN')
		layout.operator("lookingglass.window_setup", text="Create LKG Window", icon='PLUGIN')

		row = layout.row(align = True)
		row.label(text = "LKG image to view:")
		row = layout.row(align = True)
		row.template_ID(context.scene, "LKG_image", open="image.open")
		

# ------------- The Config Panel ----------------
class looking_glass_panel(bpy.types.Panel):
		
	""" Looking Glass Properties """ 
	bl_idname = "lookingglass.panel_config" # unique identifier for buttons and menu items to reference.
	bl_label = "Looking Glass Configuration" # display name in the interface.
	bl_space_type = "PROPERTIES"
	bl_region_type = "WINDOW"
	#bl_context = '.objectmode'
	#bl_category = "Looking Glass"

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
			# changed to 5 for hires -k
			default = 5,
			min = 0,
			max = 100,
			description = "How many views to store horizontally",
			)
	bpy.types.WindowManager.tilesVertical = bpy.props.IntProperty(
			name = "Vertical Tiles",
			# changed to 9 for hires -k
			default = 9,
			min = 0,
			max = 100,
			description = "How many views to store horizontally",
			)

	def draw(self, context):
		layout = self.layout
		layout.prop(context.window_manager, "tilesHorizontal")
		layout.prop(context.window_manager, "tilesVertical")

classes = (
	OffScreenDraw,
	looking_glass_window_setup,
	lkgRenderSetup,
	looking_glass_panel,
	looking_glass_render_viewer,
	LookingGlassPreferences,
)

def register():
	from bpy.utils import register_class
	for cls in classes:
		register_class(cls)
	bpy.types.IMAGE_MT_view.append(looking_glass_live_view.menu_func)
	print("registered the live view")

def unregister():
	from bpy.utils import unregister_class
	for cls in reversed(classes):
		unregister_class(cls)
	bpy.types.IMAGE_MT_view.remove(looking_glass_live_view.menu_func)

if __name__ == "__main__":
	register()
