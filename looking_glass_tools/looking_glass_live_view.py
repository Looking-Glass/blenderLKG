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
import logging
import time
import timeit # only for benchmarking
import os
import ctypes
import sys
from bgl import *
from math import *
from mathutils import *
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty
from gpu_extras.presets import draw_texture_2d
from gpu_extras.batch import batch_for_shader
from . import looking_glass_settings
from . looking_glass_settings import *
from . holoplay_service_api_commands import *

# HoloPlayCore will be loaded into this
#hp = None

# some global vars we need to get rid of
qs_width = 4096
qs_height = 4096
qs_viewWidth = 819
qs_viewHeight = 455
qs_columns = 5
qs_rows = 9
qs_numViews = 45

hp_myQuilt = None
hp_liveQuilt = None
hp_imgQuilt = None
hp_imgDataBlockQuilt = None
hp_FBO = None
hp_FBO_tmp = None
hp_FBO_img = None
hpc_LightfieldVertShaderGLSL = None
hpc_LightfieldFragShaderGLSL = None
sock = None

class OffScreenDraw(bpy.types.Operator):
	''' Manages drawing of the looking glass live view '''
	bl_idname = "view3d.offscreen_draw"
	bl_label = "Looking Glass Live View"
	bl_description = "Starts and stops the LKG live view drawing."

	_handle_draw = None
	_handle_draw_3dview = None
	is_enabled = False
	# array of texture to view multiview renders in the LGK
	_LKGtexArray = []

	# store the area from where the operator is invoked
	area = None

	@staticmethod
	def compute_view_angles(view_cone, total_views):
		view_angles = list()

		for i in range(total_views):
			# the last (-1) is to invert the order
			tmp_view = (((-1)*view_cone) / 2 + view_cone * (i / (total_views-1))) * (-1)
			view_angles.append(tmp_view)

		return view_angles

	@staticmethod
	def compute_x_offsets(convergence_distance, view_angles):
		x_offsets = list()

		for ang in view_angles:
			tmp_offset = convergence_distance * tan(ang * 0.5)
			x_offsets.append(tmp_offset)

		return x_offsets

	@staticmethod
	def compute_projection_offsets(x_offsets, aspect_ratio, size):
		projection_offsets = list()

		for off in x_offsets:
			tmp_proj = off / (aspect_ratio * size)
			projection_offsets.append(tmp_proj)

		return projection_offsets

	@staticmethod
	def setup_modelview_matrices(modelview_matrix, x_offsets):
		''' shift the camera position on the local x-axis by x_offset '''
		modelview_matrices = list()

		for off in x_offsets:
			# matrices in Blender need to be copied, otherwise it is only a link
			mv_temp = modelview_matrix.copy()
			mv_temp[0][3] += off
			modelview_matrices.append(mv_temp)

		return modelview_matrices

	@staticmethod
	def setup_projection_matrices(projection_matrix, projection_offsets):
		''' the projection matrices need to be offset (similar to lens shift in Cycles) '''
		projection_matrices = list()

		for off in projection_offsets:
			# matrices in Blender need to be copied, otherwise it is only a link
			proj_temp = projection_matrix.copy()
			proj_temp[0][2] += off
			projection_matrices.append(proj_temp)

		return projection_matrices

	@staticmethod
	def update_offscreens(self, context, offscreens, modelview_matrices, projection_matrices, quilt):
		''' helper method to update a whole list of offscreens '''

		scene = context.scene

		global qs_width
		global qs_height
		global qs_viewWidth
		global qs_viewHeight
		global qs_columns
		global qs_rows
		global qs_numViews

		global hp_myQuilt
		global hp_FBO

		if hp_myQuilt == None:
		 	hp_myQuilt = self.setupMyQuilt(hp_myQuilt)
		if hp_FBO == None:
			hp_FBO = self.setupBuffers(hp_FBO, hp_myQuilt)

		for view, offscreen in enumerate(offscreens):
			with offscreen.bind():
				# start_time = timeit.default_timer()
				offscreen.draw_view3d(
					scene,
					context.view_layer,
					context.space_data,
					context.region,
					modelview_matrices[view],
					projection_matrices[view],
					)
				# print("Offscreen rendering: %.6f" % (timeit.default_timer() - start_time))
		
		# this is a workaround for https://developer.blender.org/T84402
		for view, offscreen in enumerate(offscreens):
			with offscreen.bind():
				# start_time = timeit.default_timer()
				glReadBuffer(GL_BACK)
				glBindTexture(GL_TEXTURE_2D, hp_myQuilt[0])
				x = int((view % qs_columns) * qs_viewWidth)
				y = int(floor(view / qs_columns) * qs_viewHeight)

				''' glCopyTexSubImage2D works like a direct call to glReadPixels, saves one step '''
				# glCopyTexSubImage2D(GL_TEXTURE_2D, 0, x, y, 0, 0,
				# 					qs_viewWidth, qs_viewHeight)

				''' alternate implementation using glBlitFramebuffer() '''
				old_draw_framebuffer = Buffer(GL_INT, 1)
				glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, old_draw_framebuffer)
				
				glBindFramebuffer(GL_DRAW_FRAMEBUFFER, hp_FBO[0])

				glBlitFramebuffer(0, 0, qs_viewWidth, qs_viewHeight, 
							x, y, x+qs_viewWidth, y+qs_viewHeight, 
							GL_COLOR_BUFFER_BIT, GL_LINEAR)
							
				glBindFramebuffer(GL_DRAW_FRAMEBUFFER, old_draw_framebuffer[0])
				# print("Copying to quilt: %.6f" % (timeit.default_timer() - start_time))

	def _setup_matrices_from_existing_cameras(self, context, cam_parent):
		modelview_matrices = []
		projection_matrices = []
		for cam in bpy.data.collections['LKGCameraCollection'].objects:
			modelview_matrix, projection_matrix = self._setup_matrices_from_camera(
				context, cam)
			modelview_matrices.append(modelview_matrix)
			projection_matrices.append(projection_matrix)
		return modelview_matrices, projection_matrices

	@staticmethod
	def draw_3dview_into_texture(self, context, offscreens):
		scene = context.scene
		render = scene.render
		wm = context.window_manager
		global hp_myQuilt
		if hp_myQuilt == None:
			hp_myQuilt = self.setupMyQuilt(hp_myQuilt)
		global hp_imgDataBlockQuilt

		# should be the same aspect ratio as the looking glass display
		aspect_ratio = render.resolution_x / render.resolution_y

		total_views = wm.tilesHorizontal * wm.tilesVertical

		# check whether multiview render setup has been created
		cam_parent = bpy.data.objects.get("Multiview")
		if cam_parent is not None:
			modelview_matrices, projection_matrices = self._setup_matrices_from_existing_cameras(self,
				context, cam_parent)
		else:
			camera_active = scene.camera
			modelview_matrix, projection_matrix = self._setup_matrices_from_camera(
				context, camera_active)

			# compute the field of view from projection matrix directly
			# because focal length fov in Cycles is relative to the longer side of the view rectangle
			view_cone = 2.0*atan(1.0/projection_matrix[1][1])
			view_angles = self.compute_view_angles(view_cone, total_views)

			try:
				convergence_vector = camera_active.location - camera_active.data.dof_object.location
			except:
				print("Active camera does not have a DoF object, using distance to World Origin instead")
				convergence_vector = camera_active.location
			
			convergence_distance = convergence_vector.magnitude

			size = convergence_distance * tan(view_cone * 0.5)

			x_offsets = self.compute_x_offsets(convergence_distance, view_angles)
			projection_offsets = self.compute_projection_offsets(
				x_offsets, aspect_ratio, size)

			# create lists of matrices for modelview and projection
			modelview_matrices = self.setup_modelview_matrices(
				modelview_matrix, x_offsets)
			projection_matrices = self.setup_projection_matrices(
				projection_matrix, projection_offsets)
		# print("Computing matrices: %.6f" % (timeit.default_timer() - start_time))

		# start_time = timeit.default_timer()
		# render the scene total_views times from different angles and store the results in a quilt
		self.update_offscreens(self, context, offscreens,
							modelview_matrices, projection_matrices, hp_myQuilt[0])
		print("Rendered into texture id " + str(hp_myQuilt[0]))		

	@staticmethod
	def draw_callback_px(self, context, offscreens, quilt, batch, shader):
		''' Manages the draw handler for the live view '''
		scene = context.scene
		render = scene.render
		wm = context.window_manager
		global hp_myQuilt

		# TODO: super ugly hack because area spaces do not allow custom properties
		if context.area.spaces[0].stereo_3d_volume_alpha > 0.075:
			# in case we have an image loaded, offscreen is False and we can draw the content of the quilt directly.
			if offscreens == False:
				self.draw_new(context, quilt, batch, shader)
			else:
				# start_time = timeit.default_timer()
				# should be the same aspect ratio as the looking glass display
				aspect_ratio = render.resolution_x / render.resolution_y

				total_views = wm.tilesHorizontal * wm.tilesVertical

				# check whether multiview render setup has been created
				cam_parent = bpy.data.objects.get("Multiview")
				if cam_parent is not None:
					modelview_matrices, projection_matrices = self._setup_matrices_from_existing_cameras(
						context, cam_parent)
				else:
					camera_active = scene.camera
					modelview_matrix, projection_matrix = self._setup_matrices_from_camera(
						context, camera_active)

					# compute the field of view from projection matrix directly
					# because focal length fov in Cycles is relative to the longer side of the view rectangle
					view_cone = 2.0*atan(1.0/projection_matrix[1][1])
					view_angles = self.compute_view_angles(view_cone, total_views)

					try:
						convergence_vector = camera_active.location - camera_active.data.dof_object.location
					except:
						print("Active camera does not have a DoF object, using distance to World Origin instead")
						convergence_vector = camera_active.location
					
					convergence_distance = convergence_vector.magnitude

					size = convergence_distance * tan(view_cone * 0.5)

					x_offsets = self.compute_x_offsets(convergence_distance, view_angles)
					projection_offsets = self.compute_projection_offsets(
						x_offsets, aspect_ratio, size)

					# create lists of matrices for modelview and projection
					modelview_matrices = self.setup_modelview_matrices(
						modelview_matrix, x_offsets)
					projection_matrices = self.setup_projection_matrices(
						projection_matrix, projection_offsets)
				# print("Computing matrices: %.6f" % (timeit.default_timer() - start_time))

				# start_time = timeit.default_timer()
				# render the scene total_views times from different angles and store the results in a quilt
				self.update_offscreens(self, context, offscreens,
									modelview_matrices, projection_matrices, quilt)
				print("Rendered into texture id " + str(hp_myQuilt[0]))
				# print("Offscreen rendering and quilt building total: %.6f" % (timeit.default_timer() - start_time))

				# start_time = timeit.default_timer()
				self.draw_new(context, quilt, batch, shader)
				# print("Draw_new total: %.6f" % (timeit.default_timer() - start_time))

	@staticmethod
	def draw_callback_3dview(self, context):
		''' Redraw the area stored in self.area whenever the 3D view updates '''
		self.area.tag_redraw()

	@staticmethod
	def handle_add(self, context, offscreens, quilt, batch, shader):
		if self.area:
			''' Creates a draw handler in the 3D view and a None handler for the image editor. When no LKG window is found it removes all LKG draw handlers. '''
			OffScreenDraw._handle_draw_3dview = bpy.types.SpaceView3D.draw_handler_add(
					self.draw_callback_px, (self, context, offscreens, quilt, batch, shader),
					'WINDOW', 'POST_PIXEL',
					)
			# Redraw the area stored in self.area to force update
			self.area.tag_redraw()
			if OffScreenDraw._handle_draw_image_editor is not None:
				print("Removing Draw Handler from Image Editor")
				bpy.types.SpaceImageEditor.draw_handler_remove(OffScreenDraw._handle_draw_image_editor, 'WINDOW')
				OffScreenDraw._handle_draw_image_editor = None
		else:
			self.report({'ERROR'}, "No Looking Glass window found. Use Open LKG Window to create one.")
			OffScreenDraw._handle_draw_image_editor = None
			OffScreenDraw._handle_draw_3dview = None

	@staticmethod
	def handle_add_image_editor(self, context, quilt, batch, shader):
		''' The handler to view multiview image sequences '''
		OffScreenDraw._handle_draw_image_editor = bpy.types.SpaceImageEditor.draw_handler_add(
				self.draw_callback_viewer, (self, context, quilt, batch, shader),
				'WINDOW', 'POST_PIXEL',
				)
		# Redraw the area stored in self.area to force update
		self.area.tag_redraw()
		if OffScreenDraw._handle_draw_3dview is not None:
				print("Removing Draw Handler from Image Editor")
				bpy.types.SpaceView3D.draw_handler_remove(OffScreenDraw._handle_draw_3dview, 'WINDOW')
				OffScreenDraw._handle_draw_3dview = None		

	@staticmethod
	def handle_remove():
		if OffScreenDraw._handle_draw_image_editor is not None:
			print("Removing Draw Handler from Image Editor")
			bpy.types.SpaceImageEditor.draw_handler_remove(
				OffScreenDraw._handle_draw_image_editor, 'WINDOW')
			OffScreenDraw._handle_draw_image_editor = None

		if OffScreenDraw._handle_draw_3dview is not None:
			print("Removing Draw Handler from 3D View")
			# bpy.types.SpaceView3D.draw_handler_remove(OffScreenDraw._handle_draw_3dview, 'WINDOW')
			bpy.types.SpaceView3D.draw_handler_remove(
				OffScreenDraw._handle_draw_3dview, 'WINDOW')
			OffScreenDraw._handle_draw_3dview = None

	@staticmethod
	def _setup_offscreens(context, num_offscreens=1):
		''' Returns a list of num_offscreens off-screen buffers or one off-screen buffer directly '''
		offscreens = list()
		for i in range(num_offscreens):
			try:
				# edited this to be higher resolution, but it should be dynamic -k
				offscreen = gpu.types.GPUOffScreen(qs_viewWidth, qs_viewHeight)
			except Exception as e:
				print(e)
				offscreen = None
			offscreens.append(offscreen)

		# do not return a list when only one offscreen is set up
		if num_offscreens == 1:
			return offscreens[0]
		else:
			return offscreens

	@staticmethod
	def _setup_matrices_from_camera(context, camera):
		scene = context.scene
		render = scene.render

		modelview_matrix = camera.matrix_world.normalized().inverted()
		projection_matrix = camera.calc_matrix_camera(
				context.evaluated_depsgraph_get(),
				x=render.resolution_x,
				y=render.resolution_y,
				scale_x=render.pixel_aspect_x,
				scale_y=render.pixel_aspect_y,
				)

		return modelview_matrix, projection_matrix

	@staticmethod
	def setupMyQuilt(quilt):
		''' Create Quilt Texture '''
		#global hp_myQuilt
		global qs_width
		global qs_height
		quilt = Buffer(GL_INT, 1)
		glGenTextures(1, quilt)
		glBindTexture(GL_TEXTURE_2D, quilt[0])

		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, qs_width,
					 qs_height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)

		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

		return quilt

	@staticmethod
	def setupBuffers(fbo, quilt):
		''' Create Framebuffers for image_to_quilt '''
		fbo = Buffer(GL_INT, 1)
		glGenFramebuffers(1, fbo)
		glBindFramebuffer(GL_FRAMEBUFFER, fbo[0])
		glFramebufferTexture(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, quilt[0], 0)
		
		# unbind the buffers
		glBindFramebuffer(GL_FRAMEBUFFER, 0)
		print("End of setup buffers")
		return fbo       

	@staticmethod
	def image_to_quilt(self, context, img, view):
		''' place an image in a quilt a the right position '''
		global qs_width
		global qs_height
		global qs_viewWidth
		global qs_viewHeight
		global qs_columns
		global qs_rows
		global qs_numViews

		global hp_myQuilt
		global hp_imgQuilt
		global hp_FBO
		global hp_FBO_tmp
		global hp_FBO_img

		if hp_myQuilt == None:
			hp_myQuilt = self.setupMyQuilt(hp_myQuilt)
		if hp_imgQuilt == None:
			hp_imgQuilt = self.setupMyQuilt(hp_imgQuilt)

		if hp_FBO_img == None:
			hp_FBO_img = self.setupBuffers(hp_FBO_img, hp_imgQuilt)

		if hp_FBO_tmp == None:
			hp_FBO_tmp = Buffer(GL_INT, 1)
			glGenFramebuffers(1, hp_FBO_tmp)
			glBindFramebuffer(GL_FRAMEBUFFER, hp_FBO_tmp[0])
			glFramebufferTexture(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, img, 0)
			# unbind the buffers
			glBindFramebuffer(GL_FRAMEBUFFER, 0)
			print("Setup of temporary framebuffer completed")       

		old_read_framebuffer = Buffer(GL_INT, 1)
		glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, old_read_framebuffer)
		old_draw_framebuffer = Buffer(GL_INT, 1)
		glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, old_draw_framebuffer)

		glBindFramebuffer(GL_READ_FRAMEBUFFER, hp_FBO_tmp[0])
		glFramebufferTexture(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, img, 0)
		glBindFramebuffer(GL_DRAW_FRAMEBUFFER, hp_FBO_img[0])

		x = int((view % qs_columns) * qs_viewWidth)
		y = int(floor(view / qs_columns) * qs_viewHeight)

		# glBlitFramebuffer(SourceX0, SourceY0, SourceX1, SourceY1, 
		#               DestinationX0, DestinationY0, DestinationX1, DestinationY1, 
		#               GL_COLOR_BUFFER_BIT, GL_LINEAR)
		glBlitFramebuffer(0, 0, qs_viewWidth, qs_viewHeight, 
					  x, y, x+qs_viewWidth, y+qs_viewHeight, 
					  GL_COLOR_BUFFER_BIT, GL_LINEAR)

		glBindFramebuffer(GL_READ_FRAMEBUFFER, old_read_framebuffer[0])
		glBindFramebuffer(GL_DRAW_FRAMEBUFFER, old_draw_framebuffer[0])

	@staticmethod
	def _send_images_to_holoplay(self, context, filepaths, LKG_image):
		''' parses an array of textures, creates a quilt from it and stores it in an image datablock '''
		global hp_myQuilt
		global hp_imgQuilt
		global hp_imgDataBlockQuilt

		if hp_myQuilt == None:
			hp_myQuilt = self.setupMyQuilt(hp_myQuilt)		
		for i, filepath in enumerate(filepaths):
			LKG_image.filepath = filepath
			LKG_image.gl_load()
			bc = LKG_image.bindcode
			print("Adding image with bindcode " + str(bc) + " to quilt.")
			glActiveTexture(GL_TEXTURE0)
			glBindTexture(GL_TEXTURE_2D, bc)
			self.image_to_quilt(self, context, bc, i)
			glBindTexture(GL_TEXTURE_2D, 0)
		
		return self.copy_quilt_from_texture_to_image_datablock(hp_imgQuilt[0])

	@staticmethod
	def create_quilt_from_holoplay_multiview_image(self, context):
		''' Loads all multiview images from a render for the Looking Glass and returns an image datablock with the resulting quilt '''
		global hp_imgQuilt
		LKG_image = context.scene.LKG_image
		wm = context.window_manager

		# when the user has loaded an image in the LKG tools panel, assume it is meant for viewing in the LKG as multiview
		if LKG_image != None:
			num_multiview_images = int(wm.tilesHorizontal * wm.tilesVertical)
			multiview_first_image_path = LKG_image.filepath
			# split into file, view number and extension
			multiview_image_path_split = multiview_first_image_path.rsplit('.',2)
			self._LKGtexArray = []

			for i in range(num_multiview_images):
				img_str = multiview_image_path_split[0] + '.' + str(i).zfill(2) + '.' + multiview_image_path_split[2]
				# tex = bpy.data.images.load(img_str)
				# LKG_image.filepath = img_str
				# bpy.ops.image.reload()
				# LKG_image.gl_load()
				# self._LKGtexArray.append(LKG_image.bindcode)
				self._LKGtexArray.append(img_str)

			if hp_imgQuilt == None:
				hp_imgQuilt = self.setupMyQuilt(hp_imgQuilt)
			return self._send_images_to_holoplay(self, context, self._LKGtexArray, LKG_image)
		else:
			print("No looking glass image loaded")
			return None

	@staticmethod
	def copy_quilt_from_texture_to_image_datablock(quiltTexture):
		"""copy the current texture to a Blender image datablock"""
		global hp_myQuilt
		global hp_imgQuilt
		global hp_imgDataBlockQuilt

		print("Creating Buffer for Quilt")
		glActiveTexture(GL_TEXTURE0)
		glBindTexture(GL_TEXTURE_2D, quiltTexture)
		#batch.draw(shader)
		
		bufferForQuilt = Buffer(GL_BYTE, qs_width * qs_height * 4)
		glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, bufferForQuilt)
		glBindTexture(GL_TEXTURE_2D, 0)

		if hp_imgDataBlockQuilt == None:
			print("Creating new image for Quilt")
			hp_imgDataBlockQuilt = bpy.data.images.new("hp_imgDataBlockQuilt", qs_width, qs_height, float_buffer=True)
		# hp_imgDataBlockQuilt.pixels = [v / 255 for v in bufferForQuilt]
		# imageDataNp = np.asarray(bufferForQuilt, dtype=np.uint8)
		# imageDataNp = np.asarray(bufferForQuilt, dtype=np.float32)
		# imageDataNp = imageDataNp / 255
		# test = [v / 255 for v in bufferForQuilt]
		start_time = timeit.default_timer()
		hp_imgDataBlockQuilt.pixels.foreach_set(bufferForQuilt)
		print("Copying from buffer into image datablock took: %.6f" % (timeit.default_timer() - start_time))
		return hp_imgDataBlockQuilt
		# hp_imgDataBlockQuilt.pixels.foreach_set(hp_imgDataBlockQuilt.pixels/255)

	@staticmethod
	def copy_quilt_from_texture_to_numpy_array(quiltTexture):
		"""copy the current texture to a numpy array"""
		global hp_myQuilt
		global hp_imgQuilt
		global hp_imgDataBlockQuilt

		print("Creating Buffer for Quilt")
		glActiveTexture(GL_TEXTURE0)
		glBindTexture(GL_TEXTURE_2D, quiltTexture)
		
		bufferForQuilt = Buffer(GL_BYTE, qs_width * qs_height * 4)
		glGetTexImage(GL_TEXTURE_2D, 0, GL_RGBA, GL_UNSIGNED_BYTE, bufferForQuilt)
		glBindTexture(GL_TEXTURE_2D, 0)

		if hp_imgDataBlockQuilt == None:
			print("Creating new image for Quilt")
			hp_imgDataBlockQuilt = bpy.data.images.new("hp_imgDataBlockQuilt", qs_width, qs_height, float_buffer=True)
		# hp_imgDataBlockQuilt.pixels = [v / 255 for v in bufferForQuilt]
		
		start_time = timeit.default_timer()
		# imageDataNp = np.empty(qs_width * qs_height * 4, dtype=np.uint8)
		imageDataNp = np.empty(qs_width * qs_height * 4, dtype=np.float32)
		print("Allocating numpy array took: %.6f" % (timeit.default_timer() - start_time))
		start_time = timeit.default_timer()
		# lst = bufferForQuilt.to_list()
		print("Creating a list from buffer took: %.6f" % (timeit.default_timer() - start_time))
		start_time = timeit.default_timer()
		# imageDataNp = np.array(lst, dtype=np.uint8)
		# imageDataNp = np.fromiter(lst, dtype=np.uint8)
		hp_imgDataBlockQuilt.pixels.foreach_set(bufferForQuilt)
		# imageDataNp = np.fromiter(bufferForQuilt.to_list(), dtype=np.uint8) # why is this faster than without to_list()
		hp_imgDataBlockQuilt.pixels.foreach_get(imageDataNp)
		# imageDataList = bufferForQuilt.tolist()
		print("Copying from list into np array took: %.6f" % (timeit.default_timer() - start_time))
		# imageDataNp = np.asarray(bufferForQuilt, dtype=np.float32)
		# imageDataNp = imageDataNp / 255
		# test = [v / 255 for v in bufferForQuilt]
		# hp_imgDataBlockQuilt.pixels.foreach_set(imageDataNp)
		return imageDataNp

	@staticmethod
	def update_image(tex_id, target=GL_RGBA, texture=GL_TEXTURE0):
		"""copy the current buffer to the image"""
		glActiveTexture(texture)
		glBindTexture(GL_TEXTURE_2D, tex_id)
		glCopyTexSubImage2D(GL_TEXTURE_2D, 0, 100, 10, 0, 0, 256, 128)
		glBindTexture(GL_TEXTURE_2D, 0)

	@staticmethod
	def delete_image(tex_id):
		"""clear created image"""
		id_buf = Buffer(GL_INT, 1)
		id_buf.to_list()[0] = tex_id

		if glIsTexture(tex_id):
			glDeleteTextures(1, id_buf)

	@staticmethod
	def draw_new(context, texture_id, batch, shader):
		''' Draws a rectangle '''
		context = bpy.context
		scene = context.scene

		glActiveTexture(GL_TEXTURE0)
		glBindTexture(GL_TEXTURE_2D, texture_id)
		batch.draw(shader)
		glBindTexture(GL_TEXTURE_2D, 0)

	def modal(self, context, event):
		if context.area:
			context.area.tag_redraw()

		return {'PASS_THROUGH'}

	def invoke(self, context, event):
		global qs_viewWidth
		global qs_viewHeight
		global hp_myQuilt
		global hp_imgQuilt
		global hp
		global hpc_LightfieldVertShaderGLSL
		global hpc_LightfieldFragShaderGLSL

		if OffScreenDraw.is_enabled:
			print("Stopping drawing of Looking Glass Live View")
			self.cancel(context)

			return {'FINISHED'}
		elif looking_glass_settings.numDevices < 1:
			self.report({'ERROR'}, "No Looking Glass devices found.")
			return {'FINISHED'}
		else:
			# get the global properties from window manager
			wm = context.window_manager

			# holoplay core is loaded as global var in looking_glass_settings.py
			# hp = looking_glass_settings.hp

			# # currently this only supports the first connected LKG device TODO: support multiple devices
			# i = ctypes.c_int(0)

			# hp_deviceType = ctypes.create_string_buffer(1000)
			# hp.hpc_GetDeviceType(i, hp_deviceType, 1000)
			# print("Device type: " + str(hp_deviceType.value))

			# hp_winX = hp.hpc_GetDevicePropertyWinX(i)
			# hp_winY = hp.hpc_GetDevicePropertyWinY(i)
			# print("Position: " + str(hp_winX) + ", " + str(hp_winY))
			# hp_screenW = hp.hpc_GetDevicePropertyScreenW(i)
			# hp_screenH = hp.hpc_GetDevicePropertyScreenH(i)
			# print("Size: " + str(hp_screenW) + ", " + str(hp_screenH))

			# hp.hpc_GetDevicePropertyDisplayAspect.restype = ctypes.c_float
			# hp_displayAspect = hp.hpc_GetDevicePropertyDisplayAspect(i)
			# print("Aspect Ratio: " + str(hp_displayAspect))

			# hp.hpc_GetDevicePropertyPitch.restype = ctypes.c_float
			# hp_pitch = hp.hpc_GetDevicePropertyPitch(i)
			# print("Pitch: " + str(hp_pitch))

			# hp.hpc_GetDevicePropertyTilt.restype = ctypes.c_float
			# hp_tilt = hp.hpc_GetDevicePropertyTilt(i)
			# print("Tilt: " + str(hp_tilt))

			# hp.hpc_GetDevicePropertyCenter.restype = ctypes.c_float
			# hp_center = hp.hpc_GetDevicePropertyCenter(i)
			# print("Center: " + str(hp_center))

			# hp.hpc_GetDevicePropertySubp.restype = ctypes.c_float
			# hp_subP =  hp.hpc_GetDevicePropertySubp(i)
			# print("subp: " + str(hp_subP))

			# hp.hpc_GetDevicePropertyFringe.restype = ctypes.c_float
			# hp_fringe = hp.hpc_GetDevicePropertyFringe(i)
			# print("fringe: " + str(hp_fringe))

			# # the following all return int
			# hp_Ri = hp.hpc_GetDevicePropertyRi(i)
			# hp_Bi = hp.hpc_GetDevicePropertyBi(i)
			# hp_invView = hp.hpc_GetDevicePropertyInvView(i)
			# print(" RI: " + str(hp_Ri) + " BI: " + str(hp_Bi) + " invView: " + str(hp_invView))
			
			# TODO: Refactor			
			# pitch = hp_pitch
			# tilt = hp_tilt
			# center = hp_center
			# invView = hp_invView
			# subp = hp_subP
			# displayAspect = hp_displayAspect
			# ri = hp_Ri
			# bi = hp_Bi

			# coords_2D = [(1, -1), (-1, -1), (-1,1), (1, 1)]
			# hpc_LightfieldVertShaderGLSL = ctypes.c_char_p.in_dll(hp, "hpc_LightfieldVertShaderGLSLExported").value.decode("utf-8")
			# hpc_LightfieldFragShaderGLSL = ctypes.c_char_p.in_dll(hp, "hpc_LightfieldFragShaderGLSLExported").value.decode("utf-8")
			# shader = gpu.types.GPUShader(hpc_LightfieldVertShaderGLSL, hpc_LightfieldFragShaderGLSL)
			# #shader = gpu.shader.from_builtin('2D_IMAGE')
			# batch = batch_for_shader(shader, 'TRI_FAN', {"vertPos_data": coords_2D})

			# shader.bind()
			# #shader.uniform_float("brightness", 0.5)
			# shader.uniform_float("pitch", pitch)
			# shader.uniform_float("tilt", tilt)
			# shader.uniform_float("center", center)
			# shader.uniform_int("invView", invView)
			# shader.uniform_float("subp", subp)
			# shader.uniform_float("displayAspect", displayAspect)
			# shader.uniform_int("ri", ri)
			# shader.uniform_int("bi", bi)
			
			# quilt settings, put somewhere else
			qs_width = 4096
			qs_height = 4096
			qs_columns = 5
			qs_rows = 9
			# qs_totalViews = 45
			# overscan = 0
			# quiltInvert = 0
			# debug = 0
			
			qs_viewWidth = int(qs_width / qs_columns)
			qs_viewHeight = int(qs_height / qs_rows)
			
			# shader.uniform_float("tile", (qs_columns, qs_rows, qs_totalViews))
			# shader.uniform_float("viewPortion", (qs_viewWidth * qs_columns / float(qs_width),
			# 						   qs_viewHeight * qs_rows / float(qs_height)))
			# shader.uniform_int("overscan", overscan)
			# shader.uniform_int("quiltInvert", quiltInvert)
			# shader.uniform_float("quiltAspect", displayAspect)
			# shader.uniform_int("debug", debug)

			# start by setting both handlers to None for later checks
			OffScreenDraw._handle_draw_image_editor = None
			OffScreenDraw._handle_draw_3dview = None

			# LKG_image = context.scene.LKG_image

			# # when the user has loaded an image in the LKG tools panel, assume it is meant for viewing in the LKG as multiview
			# if LKG_image != None:
			# 	num_multiview_images = int(wm.tilesHorizontal * wm.tilesVertical)
			# 	multiview_first_image_path = LKG_image.filepath
			# 	# split into file, view number and extension
			# 	multiview_image_path_split = multiview_first_image_path.rsplit('.',2)
			# 	self._LKGtexArray = []

			# 	for i in range(num_multiview_images):
			# 		img_str = multiview_image_path_split[0] + '.' + str(i).zfill(2) + '.' + multiview_image_path_split[2]
			# 		# tex = bpy.data.images.load(img_str)
			# 		# LKG_image.filepath = img_str
			# 		# bpy.ops.image.reload()
			# 		# LKG_image.gl_load()
			# 		# self._LKGtexArray.append(LKG_image.bindcode)
			# 		self._LKGtexArray.append(img_str)

			# 	if hp_imgQuilt == None:
			# 		hp_imgQuilt = self.setupMyQuilt(hp_imgQuilt)
			# 	self._send_images_to_holoplay(self, context, self._LKGtexArray, LKG_image)
			# 	offscreens = False # this is to indicate to the draw handler that it should not use offscreen rendering but draw the images directly
			# 	OffScreenDraw.handle_add(self, context, offscreens, hp_imgQuilt[0], batch, shader)
			# else:
			# 	offscreens = self._setup_offscreens(context, qs_totalViews)
			# 	if hp_myQuilt == None:
			# 		hp_myQuilt = self.setupMyQuilt(hp_myQuilt)
				
			# 	self.draw_3dview_into_texture(self, context, offscreens)
			# 	self.copy_quilt_from_texture_to_image_datablock(hp_myQuilt[0])
			# 	#OffScreenDraw.handle_add(self, context, offscreens, hp_myQuilt[0], batch, shader)

			OffScreenDraw.is_enabled = True

			# if context.area:
			# 	# store the editor window from where the operator whas invoked
			# 	context.area.tag_redraw()
			
			# scn = context.scene			

			# the focal distance of the active camera is used as focal plane
			# thus it should not be 0 because then the system won't work
			try:
				cam = context.scene.camera
				if cam.data.dof.focus_distance == 0.0:
					# using distance of the camera to the center of the scene as educated guess
					# for the initial distance of the focal plane
					cam.data.dof.focus_distance = cam.location.magnitude
			except:
				print("Need an active camera in the scene")

			# check whether multiview render setup has been created
			cam_parent = bpy.data.objects.get("Multiview")
			if cam_parent is None:
				# change the render aspect ratio so the view in the looking glass does not get deformed
				aspect_ratio = wm.screenW / wm.screenH
				context.scene.render.resolution_x = context.scene.render.resolution_y * aspect_ratio
			
			# context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}

	def cancel(self, context):
		# OffScreenDraw.handle_remove()
		OffScreenDraw.is_enabled = False

		if context.area:
			context.area.tag_redraw()

		print("Cancel finished")

class looking_glass_send_quilt_to_holoplay_service(bpy.types.Operator):
	""" Creates a new window of type image editor """
	bl_idname = "lookingglass.send_quilt_to_holoplay_service"
	bl_label = "Send Quilt"
	bl_description = "Sends the currently loaded image to HoloPlay Service to display it in the Looking Glass."
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		global hp_imgDataBlockQuilt
		global hp_myQuilt
		global qs_width
		global qs_height
		global sock

		# print("Init Settings")
		start_time = timeit.default_timer()

		sock = looking_glass_settings.sock

		# wm = context.window_manager

		# ws_url = "ws://localhost:11222/driver"
		# driver_url = "ipc:///tmp/holoplay-driver.ipc"

		# ensure_site_packages([
		# 	("cbor", "cbor"),
		# 	("cffi","cffi"),
		# 	("pycparser","pycparser"),
		# 	("pynng","pynng"),
		# 	("sniffio", "sniffio"),
		# 	("Pillow", "Pillow")
		# ])

		# import pynng
		# import cbor
		# import PIL
		# from PIL import Image, ImageOps

		# demoval = 3

		# # This script should work identically whether addr = driver_url or addr = ws_url
		# addr = driver_url
		# if sock == None:
		# 	sock = pynng.Req0(recv_timeout=2000)
		# try:
		# 	sock.dial(addr, block = True)
		# except:
		# 	print("Could not open socket. Is driver running?")
		# 	sys.exit(1)
		# run_demo(sock, int(demoval))

		# demoval = 5
		# # response = run_demo(sock, int(demoval))
		# response = send_message(sock, {'cmd':{'info':{}},'bin':''})
		# # response_loaded = cbor.loads(response)
		# if response != None:
		# 	# create a dictionary with an index for this device
		# 	devices = response['devices']
		# 	print(devices)
		# 	if devices == []:
		# 		print("No Looking Glass devices found")
		# 	else:
		# 		print(devices)
		# 		wm.numDevicesConnected = 1
		qs_totalViews = 45
		od = OffScreenDraw
		if hp_myQuilt == None:
			hp_myQuilt = od.setupMyQuilt(hp_myQuilt)
		LKG_image = context.scene.LKG_image		
		if LKG_image != None:
			quilt = od.create_quilt_from_holoplay_multiview_image(od, context)
		else:
			offscreens = od._setup_offscreens(context, qs_totalViews)
			print("Setting up HoloPlay Service took: %.6f" % (timeit.default_timer() - start_time))
			start_time_offscreendraw = timeit.default_timer()
			od.draw_3dview_into_texture(od, context, offscreens)
			print("Drawing into offscreens took: %.6f" % (timeit.default_timer() - start_time_offscreendraw))
			start_time_quiltcopy = timeit.default_timer()
			quilt = od.copy_quilt_from_texture_to_image_datablock(hp_myQuilt[0])
			# quilt = hp_imgDataBlockQuilt		
			# quilt = od.copy_quilt_from_texture_to_numpy_array(hp_myQuilt[0])
			print("Copying quilt into np array took: %.6f" % (timeit.default_timer() - start_time_quiltcopy))
		send_quilt(sock, quilt, duration=int(7))
		# send_quilt_from_np(sock, quilt, qs_width, qs_height, duration=int(7))
		# sock.close()
		print("Done.")
		return {'FINISHED'}

def menu_func(self, context):
	''' Helper function to add the operator to menus '''
	self.layout.operator(OffScreenDraw.bl_idname)

def register():
	bpy.utils.register_class(OffScreenDraw)
	bpy.utils.register_class(looking_glass_send_quilt_to_holoplay_service)
	bpy.types.IMAGE_MT_view.append(menu_func)

def unregister():
	bpy.utils.unregister_class(looking_glass_send_quilt_to_holoplay_service)
	bpy.utils.unregister_class(OffScreenDraw)
	bpy.types.IMAGE_MT_view.remove(menu_func)

if __name__ == "__main__":
	register()
