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

import bpy
import gpu
import json
import subprocess
import logging
from bgl import *
from math import *
from mathutils import *
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty

# ------------ UI Functions -------------
class looking_glass_window_setup(bpy.types.Operator):
	""" Creates a new window of type image editor """
	bl_idname = "lookingglass.window_setup"
	bl_label = "Create Window"
	bl_description = "Creates a new window of type image editor that can be used in the looking glass display."
	bl_options = {'REGISTER', 'UNDO'}

	@staticmethod
	def load_calibration():
		user_preferences = bpy.context.user_preferences
		filepath = user_preferences.addons[__name__].preferences.filepath
		print(filepath)
		try:
			config_json_raw = subprocess.run([filepath], stdout=subprocess.PIPE)
			config_json_text = config_json_raw.stdout.decode('UTF-8')
			config_json = json.loads(config_json_text)
			print("Loading of config success, center: " + str(config_json['center']['value']))
			wm = bpy.context.window_manager
			wm.pitch = float(config_json['pitch']['value'])
			wm.slope = float(config_json['slope']['value'])
			wm.center = float(config_json['center']['value'])
			wm.invView = float(config_json['invView']['value'])
			wm.DPI = float(config_json['DPI']['value'])
			wm.screenW = float(config_json['screenW']['value'])
			wm.screenH = float(config_json['screenH']['value'])
			wm.flipImageX = float(config_json['flipImageX']['value'])
			wm.flipImageY = float(config_json['flipImageY']['value'])
			wm.flipSubp = float(config_json['flipSubp']['value'])

		except:
			print("Loading of config failed. Check file path of config utility in the addon preferences.")



	def execute(self, context):
		# Call user prefs window
		bpy.ops.screen.area_dupli('INVOKE_DEFAULT')

		# Change area type
		area = bpy.context.window_manager.windows[-1].screen.areas[0]
		area.type = 'IMAGE_EDITOR'
		OffScreenDraw.area = area
		self.load_calibration()
		print("Loaded Calibration")
		return {'FINISHED'}

def menu_func(self, context):
	''' Helper function to add the operator to menus '''
	self.layout.operator(OffScreenDraw.bl_idname)

class LookingGlassPreferences(AddonPreferences):
	# this must match the addon name
	bl_idname = __name__

	filepath = bpy.props.StringProperty(
			name="Location of the Config Extration Utility",
			subtype='FILE_PATH',
			)

	def draw(self, context):
		layout = self.layout
		layout.prop(self, "filepath")

# ------------- The Panel ----------------
class looking_glass_panel(bpy.types.Panel):
		
	""" Looking Glass Tools and Properties """ 
	bl_idname = "lookingglass.panel" # unique identifier for buttons and menu items to reference.
	bl_label = "Looking Glass" # display name in the interface.
	bl_space_type = "VIEW_3D"
	bl_region_type = "TOOLS"
	bl_category = "Looking Glass"

	# exposed parameters stored in WindowManager as global props so they 
	# can be changed even when loading the addon (due to config file parsing)
	bpy.types.WindowManager.pitch = bpy.props.FloatProperty(
			name = "Pitch",
			default = 49.0,
			min = 5.0,
			max = 250.0,
			description = "Pitch",
			)
	bpy.types.WindowManager.slope = bpy.props.FloatProperty(
			name = "Slope",
			default = 5.0,
			min = 3.0,
			max = 7.0,
			description = "Slope",
			)

	bpy.types.WindowManager.center = FloatProperty(
			name = "Center",
			default = 0.47,
			min = 0.0,
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
	bpy.types.WindowManager.invView = bpy.props.FloatProperty(
			name = "Invert View",
			default = 1.0,
			min = 0.0,
			max = 1.0,
			description = "Should the view be inverted?",
			)
	bpy.types.WindowManager.verticalAngle = bpy.props.FloatProperty(
			name = "Vertical Angle",
			default = 0.0,
			min = 0.0,
			max = 45.0,
			description = "Vertical Angle",
			)
	bpy.types.WindowManager.DPI = bpy.props.FloatProperty(
			name = "DPI",
			default = 338.0,
			min = 100.0,
			max = 1000.0,
			description = "Dots per inch of the looking glass display.",
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
	bpy.types.WindowManager.flipImageX = bpy.props.FloatProperty(
			name = "Flip Image X",
			default = 0.0,
			min = 0.0,
			max = 1.0,
			description = "Flip image along X-axis?",
			)
	bpy.types.WindowManager.flipImageY = bpy.props.FloatProperty(
			name = "Flip Image Y",
			default = 0.0,
			min = 0.0,
			max = 1.0,
			description = "Flip image along Y-axis?",
			)
	bpy.types.WindowManager.flipSubp = bpy.props.FloatProperty(
			name = "Flip Subpixels",
			default = 0.0,
			min = 0.0,
			max = 1.0,
			description = "Change the order of the Subpixels?",
			)
	bpy.types.WindowManager.tilesHorizontal = bpy.props.IntProperty(
			name = "Horizontal Tiles",
			default = 4,
			min = 0,
			max = 100,
			description = "How many views to store horizontally",
			)
	bpy.types.WindowManager.tilesVertical = bpy.props.IntProperty(
			name = "Vertical Tiles",
			default = 8,
			min = 0,
			max = 100,
			description = "How many views to store horizontally",
			)

	def draw(self, context):
		layout = self.layout
		layout.operator("lookingglass.window_setup", text="Create Live Window", icon='PLUGIN')
		layout.operator("lookingglass.render_setup", text="Create Render Setup", icon='PLUGIN')
		layout.prop(context.window_manager, "pitch")
		layout.prop(context.window_manager, "slope")
		layout.prop(context.window_manager, "center")
		layout.prop(context.window_manager, "viewCone")
		layout.prop(context.window_manager, "invView")
		layout.prop(context.window_manager, "verticalAngle")
		layout.prop(context.window_manager, "DPI")
		layout.prop(context.window_manager, "screenW")
		layout.prop(context.window_manager, "screenH")
		layout.prop(context.window_manager, "flipImageX")
		layout.prop(context.window_manager, "flipImageY")
		layout.prop(context.window_manager, "flipSubp")
		layout.prop(context.window_manager, "tilesHorizontal")
		layout.prop(context.window_manager, "tilesVertical")

def register():
	bpy.utils.register_class(looking_glass_panel)
	bpy.utils.register_class(looking_glass_window_setup)
	bpy.types.IMAGE_MT_view.append(menu_func)
	bpy.utils.register_class(LookingGlassPreferences)
	looking_glass_window_setup.load_calibration()


def unregister():
	bpy.utils.unregister_class(looking_glass_window_setup)
	bpy.utils.unregister_class(looking_glass_panel)
	bpy.types.IMAGE_MT_view.remove(menu_func)
	bpy.utils.unregister_class(LookingGlassPreferences)

if __name__ == "__main__":
	register()