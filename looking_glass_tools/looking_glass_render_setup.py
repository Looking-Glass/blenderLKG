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
import bmesh
import subprocess
import logging
from bgl import *
from math import *
from mathutils import *
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty
from bpy.app.handlers import persistent

# @persistent
# def fix_clipping_planes_pre(self):
# 	''' Fixed weird behaviour of Blender when rendering by adjusting the clipping distances of the LKG cameras by the local scale of the Multiview object '''
# 	global fov
# 	currentMultiview = bpy.data.objects.get("Multiview")
# 	scale_factor = currentMultiview.matrix_local.to_scale().z
# 	clip_delta = 0.01
# 	camLocZ = currentMultiview.scale[0] / tan(0.5 * radians(fov))
	
# 	#	cam.data.clip_start = camLocZ - 1.0 + clip_delta
# 	#	cam.data.clip_end = camLocZ + 1.0 - clip_delta
# 	for ob in currentMultiview.children:		
# 		ob.data.clip_start = camLocZ - 1.0*scale_factor + clip_delta
# 		ob.data.clip_end = camLocZ + 1.0*scale_factor - clip_delta

# @persistent
# def fix_clipping_planes_post(self):
# 	''' Reverse the effects of fix_clipping_planes_post '''
# 	currentMultiview = bpy.data.objects.get("Multiview")
# 	for ob in currentMultiview.children:
# 		scale_factor = currentMultiview.matrix_local.to_scale().z
# 		ob.data.clip_start *= scale_factor
# 		ob.data.clip_end /= scale_factor

class lkgRenderSetup(bpy.types.Operator):
	bl_idname = "lookingglass.render_setup"
	bl_label = "Looking Glass Render Setup"
	bl_description = "Creates render setup for offline rendering utilizing multiview."
	bl_options = {'REGISTER', 'UNDO'}

	currentMultiview = None
	fov = None

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

		# cube of dimensions 1-1-1, front and back stored separately
		verts_front = [(-1.0,1.0,1.0),(1.0,1.0,1.0),(1.0,-1.0,1.0),(-1.0,-1.0,1.0)]
		verts_back = [(-1.0,1.0,-1.0),(1.0,1.0,-1.0),(1.0,-1.0,-1.0),(-1.0,-1.0,-1.0)]

		scn = context.scene
		global currentMultiview
		global fov

		# Create mesh 
		me = bpy.data.meshes.new('Multiview') 

		# Create object
		currentMultiview = bpy.data.objects.new("Multiview", me)
		currentMultiview.show_name = True
		scn.collection.objects.link(currentMultiview)

		# Get a BMesh representation
		bm = bmesh.new()   # create an empty BMesh
		
		bm_verts_front = []
		bm_verts_back = []
		bm_verts = []				

		for v in verts_front:
			bm_vert = bm.verts.new(v)
			bm_verts_front.append(bm_vert)
			bm_verts.append(bm_vert)
		for v in verts_back:
			bm_vert = bm.verts.new(v)
			bm_verts_back.append(bm_vert)
			bm_verts.append(bm_vert)

		for i, v in enumerate(bm_verts_front):
			j = (i+1)%len(bm_verts_front)
			bm.edges.new( (bm_verts_front[i], bm_verts_front[j]) )
			
		for i, v in enumerate(bm_verts_back):
			j = (i+1)%len(bm_verts_back)
			bm.edges.new( (bm_verts_back[i], bm_verts_back[j]) )
			# hacky, saves one extra loop
			bm.edges.new( (bm_verts_front[i], bm_verts_back[i]) )
		
		dist=self.calculate_camera_distance_z(fov)
		# hardcoded - refactor!
		# the result includes a margin around the Multiview container object
		dist_front = dist - 1.5
		dist_back = dist + 0.0
		
		scale_factor_front = tan(fov) * dist_front
		scale_factor_back = tan(fov) * dist_back
		
		bmesh.ops.scale(bm, vec=(scale_factor_front, scale_factor_front, 1.0), space=currentMultiview.matrix_local, verts=bm_verts_front)
		bmesh.ops.scale(bm, vec=(scale_factor_back, scale_factor_back, 1.0), space=currentMultiview.matrix_local, verts=bm_verts_back)

		# the aspect ratio should match the one of the LKG device
		wm = bpy.context.window_manager
		aspectRatio = wm.screenH / wm.screenW

		bmesh.ops.scale(bm, vec=(1.0, aspectRatio, 1.0), space=currentMultiview.matrix_local, verts=bm_verts_front)
		bmesh.ops.scale(bm, vec=(1.0, aspectRatio, 1.0), space=currentMultiview.matrix_local, verts=bm_verts_back)

		# Finish up, write the bmesh back to the mesh
		bm.to_mesh(me)
		
	def get_vertical_fov_from_camera(self, cam):
		''' returns the vertical field of view of the camera '''
		render = bpy.context.scene.render
		projection_matrix = cam.calc_matrix_camera(render.resolution_x, render.resolution_y, render.pixel_aspect_x, render.pixel_aspect_y)
		fov_vertical = 2.0*atan( 1.0/projection_matrix[1][1] )
		return fov_vertical

	@staticmethod
	def calculate_camera_distance_z(fov):
		global currentMultiview
		camLocZ = currentMultiview.scale[0] / tan(0.5 * radians(fov))
		return camLocZ

	def makeCamera(self, i):
		''' Create Camera '''
		self.log.info("Creating Camera")
		global fov
		wm = bpy.context.window_manager
		numViews = wm.tilesHorizontal * wm.tilesVertical
		viewCone = wm.viewCone
		
		bpy.ops.object.camera_add(
			enter_editmode=False,
			align='WORLD',
			location=(0, 0, 0),
			rotation=(0,0,0)
		)
		cam = bpy.context.active_object
		cam.name = 'cam.' + str(i).zfill(2)
		cam.data.lens_unit = 'FOV'
		fov_rad = radians(fov)
		cam.data.angle = fov_rad

		#* parent it to current multi view
		global currentMultiview
		currentMultiview.select_set(True)
		bpy.context.view_layer.objects.active = currentMultiview
		self.setParentTrans(cam, currentMultiview)
		# const = cam.constraints.new('CHILD_OF')
		# const.target=currentMultiview
		# const.inverse_matrix = currentMultiview.matrix_world.inverted()



		# cam distance
		#camLocZ = currentMultiview.scale[0] / tan(0.5 * fov_rad)
		camLocZ = self.calculate_camera_distance_z(fov)
		cam.location[2] = camLocZ

		# cam x pos
		angleStr = radians(-viewCone * 0.5 + viewCone * (i / (numViews - 1)))
		camLocX = cam.location[2] * tan(angleStr) / currentMultiview.scale[0]
		self.log.info("Camera X location: %f" % camLocX)
		self.log.info("Camera Z location: %f" % cam.location[2])
		cam.location[0] = camLocX

		# shift x
		cam.data.shift_x = (-0.5) * cam.location.x

		# clipping relative to the MultiView object bounds
		# clip delta is to get rid of most of the Multiview object in the LKG
		clip_delta = 0.01
		cam.data.clip_start = camLocZ - 1.0 + clip_delta
		cam.data.clip_end = camLocZ + 1.0 - clip_delta

		# drivers to keep camera clipping distances in bounds of Multiview object when it gets scaled TODO: De-duplicate
		driver = cam.data.driver_add('clip_start').driver
		var = driver.variables.new()
		var.name = 'z_scale'
		var.targets[0].id = currentMultiview
		var.targets[0].data_path = 'scale.z'
		driver.expression = 'z_scale / tan(0.5 * radians(' + str(fov) + ')) - z_scale + ' + str(clip_delta) + '*z_scale'

		driver = cam.data.driver_add('clip_end').driver
		var = driver.variables.new()
		var.name = 'z_scale'
		var.targets[0].id = currentMultiview
		var.targets[0].data_path = 'scale.z'
		driver.expression = 'z_scale / tan(0.5 * radians(' + str(fov) + ')) + z_scale - ' + str(clip_delta) + '*z_scale'

		#* set up view
		bpy.ops.scene.render_view_add()
		newView = bpy.context.scene.render.views.active
		newView.name = 'view.' + str(i).zfill(2)
		newView.camera_suffix = '.' + str(i).zfill(2)

		# the cameras will be invisible in the viewport but for debugging it is nice to see the limits directly when turning one on
		cam.data.show_limits = True

		# cam should be invisible in the viewport because otherwise a line will appear in the LKG
		# for 2.8 we need to use hide_set(True) because hide_viewport will globally disable it in viewports, temporarily breaking the child-parent-relationship
		cam.hide_set(True)

		return cam

	def makeAllCameras(self, camCollection):
		self.log.info("Make all cameras")
		wm = bpy.context.window_manager
		numViews = wm.tilesHorizontal * wm.tilesVertical
		self.log.info("Creating %d Cameras" % numViews)
		allCameras = []
		for i in range(0, numViews):
			cam = self.makeCamera(i)
			allCameras.append(cam)
			camCollection.objects.link(cam)
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

	def setRenderSettings(self, context):
		''' Set render size depending on LKG configuration. This overwrites previous settings! '''
		wm = context.window_manager
		render = context.scene.render
		if wm.tilesHorizontal == 5 and wm.tilesVertical == 9:
			render.resolution_x = 819
			render.resolution_y = 455
			render.pixel_aspect_x = 1.0
			render.pixel_aspect_y = 1.125
		elif wm.tilesHorizontal == 4 and wm.tilesVertical == 8:
			render.resolution_x = 512
			render.resolution_y = 256
			render.pixel_aspect_x = 1.0
			render.pixel_aspect_y = 1.25
		#only make changes when one of the supported configs is set


	def execute(self, context):
		# the fov of the Blender camera is relative to the broader side
		# at an aspect ratio of 16:10 a fov of 14° translates to ~22.23 degrees
		global fov
		fov = 22.23
		# TODO: find a better way, this here is tricky
		bpy.ops.ed.undo_push()
		self.setupMultiView()
		self.makeMultiview(context)
		# create an own collection for the camera objects
		camCollection = bpy.data.collections.new("LKGCameraCollection")
		context.scene.collection.children.link(camCollection)
		allCameras = self.makeAllCameras(camCollection)
		#* need to set the scene camera otherwise it won't render by code?
		# for a meaningful view set the middle camera active
		numCams = len(allCameras)
		context.scene.camera = allCameras[int(floor(numCams/2))]
		self.setRenderSettings(context)
		#bpy.app.handlers.render_pre.append(fix_clipping_planes_pre)
		#bpy.app.handlers.render_post.append(fix_clipping_planes_post)
		return {'FINISHED'}

def register():
	bpy.utils.register_class(lkgRenderSetup)


def unregister():
	bpy.utils.unregister_class(lkgRenderSetup)

if __name__ == "__main__":
	register()