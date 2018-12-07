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
	def setParentTrans(childOb, parentOb):
		''' Create a child-parent hierarchy similar to the operator '''
		childOb.parent = parentOb
		childOb.matrix_parent_inverse = parentOb.matrix_world.inverted()
		return True

	def makeMultiview(self, context):
		''' Create a parent object for the multiview cameras that also indicates the view space of the LKG '''
		self.log.info("Making Multiview")

		scn = context.scene
		global currentMultiview

		currentMultiview = bpy.data.objects.new("Multiview", None)
		scn.collection.objects.link(currentMultiview)
		currentMultiview.empty_display_type = 'CUBE'

		# the aspect ratio should match the one of the LKG device
		wm = bpy.context.window_manager
		aspectRatio = wm.screenH / wm.screenW
		currentMultiview.scale.y = currentMultiview.scale.x * aspectRatio

		# adding another empty as cone to indicate direction
		multiviewDirection = bpy.data.objects.new("MultiviewDirection", None)
		
		scn.collection.objects.link(multiviewDirection)
		multiviewDirection.location = (0,0,1.0)
		multiviewDirection.rotation_euler = (radians(90.0), 0, 0)
		multiviewDirection.empty_display_type = 'CONE'

		self.setParentTrans(multiviewDirection, currentMultiview)



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
		currentMultiview.select_set(True)
		bpy.context.view_layer.objects.active = currentMultiview
		bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

		# cam distance
		camLocZ = currentMultiview.scale[0] / tan(0.5 * cam.data.angle)
		cam.location[2] = camLocZ

		# cam x pos
		angleStr = radians(-viewCone * 0.5 + viewCone * (i / (numViews - 1)))
		camLocX = cam.location[2] * tan(angleStr) / currentMultiview.scale[0]
		self.log.info("Camera X location: %f" % camLocX)
		self.log.info("Camera Z location: %f" % cam.location[2])
		cam.location[0] = camLocX

		#* driver for shift x
		cam.data.shift_x = (-0.5) * cam.location.x

		#* set up view
		bpy.ops.scene.render_view_add()
		newView = bpy.context.scene.render.views.active
		newView.name = 'view.' + str(i).zfill(2)
		newView.camera_suffix = '.' + str(i).zfill(2)

		#cam should be invisible in the viewport because otherwise a line will appear in the LKG
		cam.hide_viewport = True

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
		self.makeMultiview(context)
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