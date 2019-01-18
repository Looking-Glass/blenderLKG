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
		scn.objects.link(currentMultiview)

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
		wm = bpy.context.window_manager
		render = bpy.context.scene.render
		projection_matrix = cam.calc_matrix_camera(render.resolution_x, render.resolution_y, render.pixel_aspect_x, render.pixel_aspect_y)
		fov_vertical = 2.0*atan( 1.0/projection_matrix[1][1] )
		return fov_vertical

	@staticmethod
	def calculate_camera_distance_z(fov):
		#global fov
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
			view_align=False,
			enter_editmode=False,
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
		currentMultiview.select = True
		bpy.context.scene.objects.active = currentMultiview
		bpy.ops.object.parent_set(type='OBJECT', keep_transform=True)

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

		#* set up view
		bpy.ops.scene.render_view_add()
		newView = bpy.context.scene.render.views.active
		newView.name = 'view.' + str(i).zfill(2)
		newView.camera_suffix = '.' + str(i).zfill(2)

		#cam should be invisible in the viewport because otherwise a line will appear in the LKG
		cam.hide = True

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
		allCameras = self.makeAllCameras()
		#* need to set the scene camera otherwise it won't render by code?
		# for a meaningful view set the middle camera active
		numCams = len(allCameras)
		context.scene.camera = allCameras[int(floor(numCams/2))]
		self.setRenderSettings(context)
		return {'FINISHED'}

def register():
	bpy.utils.register_class(lkgRenderSetup)


def unregister():
	bpy.utils.unregister_class(lkgRenderSetup)

if __name__ == "__main__":
	register()