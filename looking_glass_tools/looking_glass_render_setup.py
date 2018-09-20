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

class lkgRenderSetup(bpy.types.Operator):
	bl_idname = "lookingglass.render_setup"
	bl_label = "Looking Glass Render Setup"
	bl_description = "Creates render setup for offline rendering utilizing multiview."
	bl_options = {'REGISTER', 'UNDO'}

	currentMultiview = None

	log = logging.getLogger('bpy.ops.%s' % bl_idname)
	log.setLevel('DEBUG')

	@staticmethod
	def makeMultiview():
		bpy.ops.object.empty_add(
			type='CUBE',
			view_align=False,
			location=(0, 0, 0)
		)

		global currentMultiview
		currentMultiview = bpy.context.active_object
		currentMultiview.name = 'Multiview'

		#* driver for height
		driver = currentMultiview.driver_add('scale', 1).driver
		scalex = driver.variables.new()
		scalex.name = "scalex"
		scalex.targets[0].id = currentMultiview
		scalex.targets[0].data_path = 'scale.x'
		driver.expression = 'scalex * 10 / 16'

	def makeCamera(self, i):
		''' Create Camera '''
		self.log.info("Creating Camera")
		wm = bpy.context.window_manager
		numViews = wm.tilesHorizontal * wm.tilesVertical
		viewCone = wm.viewCone
		#why a field of view of 13.5 degrees?
		#fov = 13.5
		fov = 35.5

		bpy.ops.object.camera_add(
			view_align=False,
			enter_editmode=False,
			location=(0, 0, 0),
			rotation=(0,0,0)
		)
		cam = bpy.context.active_object
		cam.name = 'cam.' + str(i).zfill(2)
		cam.data.lens_unit = 'FOV'
		cam.data.angle = radians(fov)

		#* parent it to current multi view
		global currentMultiview
		currentMultiview.select = True
		bpy.context.scene.objects.active = currentMultiview
		bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

		# cam distance
		camLocZ = currentMultiview.scale[0] / tan(0.5 * cam.data.angle)
		cam.location[2] = camLocZ

		# cam x pos
		angleStr = radians(-viewCone * 0.5 + viewCone * (i / (numViews - 1)))
		#driver.expression = 'camDist * tan(' + angleStr + ') / viewSize.x'
		camLocX = cam.location[2] * tan(angleStr) / currentMultiview.scale[0]
		self.log.info("Camera X location: %f" % camLocX)
		self.log.info("Camera Z location: %f" % cam.location[2])
		cam.location[0] = camLocX

		#* driver for shift x
		driver = cam.data.driver_add('shift_x').driver
		xpos = driver.variables.new()
		xpos.name = 'xpos'
		xpos.targets[0].id = cam
		xpos.targets[0].data_path = 'location.x'
		viewSize = driver.variables.new()
		viewSize.name = 'viewSize'
		viewSize.targets[0].id = currentMultiview
		viewSize.targets[0].data_path = 'scale'
		driver.expression = '-0.5 * xpos'

		#* set up view
		bpy.ops.scene.render_view_add()
		newView = bpy.context.scene.render.views.active
		newView.name = 'view.' + str(i).zfill(2)
		newView.camera_suffix = '.' + str(i).zfill(2)

		return cam

	def makeAllCameras(self):
		self.log.info("Make all cameras")
		wm = bpy.context.window_manager
		numViews = wm.tilesHorizontal * wm.tilesVertical
		self.log.info("Creating %d Cameras" % numViews)
		allCameras = []
		for i in range(0, numViews):
			cam = self.makeCamera(i)
			allCameras.append(cam)
		return allCameras

	#@staticmethod
	def setupMultiView(self):
		self.log.info("Setting up Multiview")
		render = bpy.context.scene.render
		render.use_multiview = True
		if "left" in render.views:
			render.views["left"].use = False
		if "right" in render.views:
			render.views["right"].use = False
		render.views_format = 'MULTIVIEW'

	def execute(self, context):
		# TODO: find a better way, this here is tricky
		bpy.ops.ed.undo_push()
		self.setupMultiView()
		self.makeMultiview()
		allCameras = self.makeAllCameras()
		#* need to set the scene camera otherwise it won't render by code?
		# for a meaningful view set the middle camera active
		numCams = len(allCameras)
		context.scene.camera = allCameras[int(floor(numCams/2))]

		return {'FINISHED'}

def register():
	bpy.utils.register_class(lkgRenderSetup)


def unregister():
	bpy.utils.unregister_class(lkgRenderSetup)

if __name__ == "__main__":
	register()