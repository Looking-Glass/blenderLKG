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
import os
import ctypes
from bgl import *
from math import *
from mathutils import *
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import FloatProperty, PointerProperty
from gpu_extras.presets import draw_texture_2d

# only works when DLL is correctly installed
#holoplay = ctypes.CDLL("HoloPlayAPI")
# for testing purposes of the latest lib version the path to HoloPlay is hardcoded
holoplay = ctypes.CDLL("c:\\tmp\\HoloPlayAPI")

# some global vars we need to get rid of
qs_width = 4096
qs_height = 4096
qs_viewWidth = 819
qs_viewHeight = 455
qs_columns = 5
qs_rows = 9
qs_numViews = 45

hp_myQuilt = None

class OffScreenDraw(bpy.types.Operator):
	bl_idname = "view3d.offscreen_draw"
	bl_label = "Looking Glass Live View"

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
			tmp_view = (((-1)*view_cone) / 2 + view_cone * (i / (total_views-1))) * (-1) #the last (-1) is to invert the order
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
			#matrices in Blender need to be copied, otherwise it is only a link
			mv_temp = modelview_matrix.copy()
			mv_temp[0][3] += off
			modelview_matrices.append(mv_temp)
			
		return modelview_matrices
	
	@staticmethod
	def setup_projection_matrices(projection_matrix, projection_offsets):
		''' the projection matrices need to be offset (similar to lens shift in Cycles) '''
		projection_matrices = list()
		
		for off in projection_offsets:
			#matrices in Blender need to be copied, otherwise it is only a link
			proj_temp = projection_matrix.copy()
			proj_temp[0][2] += off
			projection_matrices.append(proj_temp)
			
		return projection_matrices
	
	@staticmethod
	def update_offscreens(self, context, offscreen, modelview_matrices, projection_matrices, quilt):
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

		if hp_myQuilt == None:
			self.setupMyQuilt()
		
		# find the image editor window and create a faux context
		""" for window in bpy.context.window_manager.windows:
			screen = window.screen
			for area in screen.areas:
				if area.type == 'VIEW_3D':
					for region in area.regions:
						if region.type == 'WINDOW':
							for space in area.spaces:
								if space.type == 'VIEW_3D': 
									override = {'area': area,
									'region': region,
									'space_data': space,
									'scene': context.scene,
									'view_layer': context.view_layer,
									} """
		
		with offscreen.bind():
			for view in range(qs_numViews):
				""" offscreen.draw_view3d(
					scene,
					override['view_layer'],
					override['space_data'],
					override['region'],
					modelview_matrices[view],
					projection_matrices[view],
					) """
				offscreen.draw_view3d(
					scene,
					context.view_layer,
					context.space_data,
					context.region,
					modelview_matrices[view],
					projection_matrices[view],
					)

				glReadBuffer(GL_BACK)				
				glBindTexture(GL_TEXTURE_2D, quilt)
				x = int((view % qs_columns) * qs_viewWidth)
				y = int(floor(view / qs_columns) * qs_viewHeight)
				#print("X: " + str(x) + " Y: " + str(y))

				''' glCopyTexSubImage2D works like a direct call to glReadPixels, saves one step '''
				glCopyTexSubImage2D(GL_TEXTURE_2D, 0,x,y,0,0,qs_viewWidth, qs_viewHeight)



	def _setup_matrices_from_existing_cameras(self, context, cam_parent):
		modelview_matrices = []
		projection_matrices = []
		for cam in cam_parent.children:
			modelview_matrix, projection_matrix = self._setup_matrices_from_camera(context, cam)
			modelview_matrices.append(modelview_matrix)
			projection_matrices.append(projection_matrix)
		return modelview_matrices, projection_matrices
		
			
	@staticmethod
	def draw_callback_px(self, context, offscreen, quilt):
		''' Manges the draw handler for the live view '''
		scene = context.scene
		render = scene.render
		wm = context.window_manager

		#should be the same aspect ratio as the looking glass display
		aspect_ratio = render.resolution_x / render.resolution_y
		
		total_views = wm.tilesHorizontal * wm.tilesVertical

		#check whether multiview render setup has been created
		cam_parent = bpy.data.objects.get("Multiview")
		if cam_parent is not None:
			modelview_matrices, projection_matrices = self._setup_matrices_from_existing_cameras(context, cam_parent)			
		else:
			camera_active = scene.camera
			modelview_matrix, projection_matrix = self._setup_matrices_from_camera(context, camera_active)
			
			# compute the field of view from projection matrix directly
			# because focal length fov in Cycles is relative to the longer side of the view rectangle
			view_cone = 2.0*atan( 1.0/projection_matrix[1][1] ) 	   
			view_angles = self.compute_view_angles(view_cone, total_views)
			
			if camera_active.data.dof_object == None:
				convergence_distance = camera_active.data.dof_distance
			else:
				convergence_vector = camera_active.location - camera_active.data.dof_object.location
				convergence_distance = convergence_vector.magnitude

			size = convergence_distance * tan(view_cone * 0.5)
			
			x_offsets = self.compute_x_offsets(convergence_distance, view_angles)		
			projection_offsets = self.compute_projection_offsets(x_offsets, aspect_ratio, size)

			#create lists of matrices for modelview and projection
			modelview_matrices = self.setup_modelview_matrices(modelview_matrix, x_offsets)
			projection_matrices = self.setup_projection_matrices(projection_matrix, projection_offsets)
		
		# render the scene total_views times from different angles and store the results in a quilt
		self.update_offscreens(self, context, offscreen, modelview_matrices, projection_matrices, quilt)		

		print("glGetError before draw: " + str(glGetError()))
		#self._opengl_draw(context, offscreens, aspect_ratio, 1.0)
		self.draw(context, quilt)

	@staticmethod
	def draw_callback_viewer(self, context):
		''' Manages the draw handler for the multiview image viewer '''
		scene = context.scene
		render = scene.render

		#should be the same aspect ratio as the looking glass display
		aspect_ratio = render.resolution_x / render.resolution_y

		if scene.LKG_image != None:
			offscreens = None
			#self._opengl_draw(context, offscreens, aspect_ratio, 1.0)
			texture = holoplay.hp_getQuiltTexture()
			self.draw(context, texture)
		else:
			print("No image selected to draw in the LKG, removing viewer")
			self.cancel(context)

		
	@staticmethod
	def draw_callback_3dview(self, context):
		''' Redraw the area stored in self.area whenever the 3D view updates '''
		self.area.tag_redraw()

	@staticmethod
	def handle_add(self, context, offscreen, quilt):
		''' The handler in the image editor is to actually draw the lenticular image.
			The handler in the 3D view is meant to send update triggers to the image
			editor handler whenever the 3D view updates. '''
		OffScreenDraw._handle_draw = bpy.types.SpaceView3D.draw_handler_add(
				self.draw_callback_px, (self, context, offscreen, quilt),
				'WINDOW', 'POST_PIXEL',
				)
		OffScreenDraw._handle_draw_3dview = bpy.types.SpaceView3D.draw_handler_add(
				self.draw_callback_3dview, (self, context),
				'WINDOW', 'POST_PIXEL',
				)

	@staticmethod
	def handle_add_viewer(self, context):
		''' The handler to view multiview image sequences '''
		OffScreenDraw._handle_draw = bpy.types.SpaceImageEditor.draw_handler_add(
				self.draw_callback_viewer, (self, context),
				'WINDOW', 'POST_PIXEL',
				)

	@staticmethod
	def handle_remove():
		if OffScreenDraw._handle_draw is not None:
			bpy.types.SpaceImageEditor.draw_handler_remove(OffScreenDraw._handle_draw, 'WINDOW')

		OffScreenDraw._handle_draw = None
		
		if OffScreenDraw._handle_draw_3dview is not None:
			bpy.types.SpaceView3D.draw_handler_remove(OffScreenDraw._handle_draw_3dview, 'WINDOW')

		OffScreenDraw._handle_draw_3dview = None

	@staticmethod
	def _setup_offscreens(context, num_offscreens = 1):
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
		
		modelview_matrix = camera.matrix_world.inverted()
		projection_matrix = camera.calc_matrix_camera(
				context.evaluated_depsgraph_get(),
				x=render.resolution_x,
				y=render.resolution_y,
				scale_x=render.pixel_aspect_x,
				scale_y=render.pixel_aspect_y,
				)
				
		return modelview_matrix, projection_matrix

	@staticmethod
	def setupMyQuilt():
		''' Create Quilt Texture '''
		global hp_myQuilt    
		global qs_width
		global qs_height
		hp_myQuilt = Buffer(GL_INT, 1)
		glGenTextures(1, hp_myQuilt)
		glBindTexture(GL_TEXTURE_2D, hp_myQuilt[0])
		
		glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, qs_width, qs_height, 0, GL_RGB, GL_UNSIGNED_BYTE, None)
		
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
		glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
		
	@staticmethod
	def _update_offscreen_m(self, context, offscreen, modelview_matrix, projection_matrix, view):
		''' render viewport into offscreen buffer using matrices '''
		scene = bpy.context.scene
		#context_real = bpy.context
		#view_layer = bpy.context.view_layer

		global qs_width
		global qs_height
		global qs_viewWidth
		global qs_viewHeight
		global qs_columns
		global qs_rows
		global qs_numViews

		global hp_myQuilt

		if hp_myQuilt == None:
			self.setupMyQuilt()

		offscreen.bind()
		#bufferForImage = Buffer(GL_BYTE, qs_viewWidth * qs_viewHeight * 4)

		#print("Drawing View3D into Offscreen Buffer")
		offscreen.draw_view3d(
				scene,
				context['view_layer'],
				context['space_data'],
				context['region'],
				modelview_matrix,
				projection_matrix,
				)

		glReadBuffer(GL_BACK)
		glReadPixels(0, 0, qs_viewWidth, qs_viewHeight, GL_RGBA, GL_UNSIGNED_BYTE, bufferForImage)
		
		glBindTexture(GL_TEXTURE_2D, hp_myQuilt[0])
		x = int((view % qs_columns) * qs_viewWidth)
		y = int(floor(view / qs_columns) * qs_viewHeight)
		print("X: " + str(x) + " Y: " + str(y))
		
		glTexSubImage2D(GL_TEXTURE_2D, 0,x,y,qs_viewWidth, qs_viewHeight, GL_RGBA, GL_UNSIGNED_BYTE, bufferForImage)

		offscreen.unbind()

		
				
		# added dll call to add offscreen texture to quilt -k
		# todo: once dll is update won't have to bind texture
		# glActiveTexture(GL_TEXTURE0)
		# glBindTexture(GL_TEXTURE_2D, offscreen.color_texture)
		# print("glGetError() before copyViewToQuilt: " + str(glGetError()))
		# holoplay.hp_copyViewToQuilt(ctypes.c_uint(view))
		# print("glGetError() after copyViewToQuilt: " + str(glGetError()))

	@staticmethod
	def _send_images_to_holoplay(images):
		''' parses an array of textures and sends it to the holoplay SDK '''
		for i,image in enumerate(images):
			print(image.name)
			image.gl_load()
			glActiveTexture(GL_TEXTURE0)
			glBindTexture(GL_TEXTURE_2D, image.bindcode)
			holoplay.hp_copyViewToQuilt(ctypes.c_uint(i))

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
	def draw(context, texture_id):
		''' Draws a rectangle '''
		context = bpy.context
		scene = context.scene
		global hp_myQuilt
		
					#positions  	#colors 		 #texture coords
		vertices = [1.0,  1.0, 0.0,   1.0, 0.0, 0.0,   1.0, 1.0,   # top right
					1.0, -1.0, 0.0,   0.0, 1.0, 0.0,   1.0, 0.0,   # bottom right
					-1.0, -1.0, 0.0,   0.0, 0.0, 1.0,   0.0, 0.0,   # bottom left
					-1.0,  1.0, 0.0,   1.0, 1.0, 0.0,   0.0, 1.0]   # top left 
		
		indices = [0, 1, 3, # first triangle
					1, 2, 3] # second triangle
		
		verco_buf = Buffer(GL_FLOAT, len(vertices), vertices)
		indices_buf = Buffer(GL_INT, len(indices), indices)
		
		id_buf = Buffer(GL_INT, 1)
		vao_buf = Buffer(GL_INT, 1)
		ebo_buf = Buffer(GL_INT, 1)
		glGenBuffers(1, id_buf)
		glGenBuffers(1, ebo_buf)
		glGenVertexArrays(1, vao_buf)
		# bind the Vertex Array Object first, then bind and set vertex buffer(s), and then configure vertex attributes(s).
		glBindVertexArray(vao_buf[0])

		glBindBuffer(GL_ARRAY_BUFFER, id_buf[0])
		glBufferData(GL_ARRAY_BUFFER, 128, verco_buf, GL_STATIC_DRAW)

		
		glGenBuffers(1, ebo_buf)
		glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo_buf[0])
		glBufferData(GL_ELEMENT_ARRAY_BUFFER, 48, indices_buf, GL_STATIC_DRAW)

		# position attribute
		glVertexAttribPointer(0,3,GL_FLOAT,GL_FALSE,32,None)
		glEnableVertexAttribArray(0)

		#color attribute
		glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 32, 12)
		glEnableVertexAttribArray(1)

		#texture coordinates attribute
		glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 32, 24)
		glEnableVertexAttribArray(2)
		
		# get shader from holoplay but quilt from own setup
		glUseProgram(holoplay.hp_getLightfieldShader())
		glBindVertexArray(vao_buf[0])
		#glBindTexture(GL_TEXTURE_2D, holoplay.hp_getQuiltTexture())
		glActiveTexture(GL_TEXTURE0)
		glBindTexture(GL_TEXTURE_2D, texture_id)
		glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, 0)
		print("Drawn")

	# operator functions
	@classmethod
	def poll(cls, context):
		''' Limit the operator to the area type specified '''
		return context.area.type == 'IMAGE_EDITOR'

	def modal(self, context, event):
		if context.area:
			context.area.tag_redraw()

		return {'PASS_THROUGH'}

	def invoke(self, context, event):
		global qs_viewWidth
		global qs_viewHeight
		global hp_myQuilt
		
		if OffScreenDraw.is_enabled:
			self.cancel(context)

			return {'FINISHED'}

		else:
			# get the global properties from window manager
			wm = context.window_manager	

			# initialize holoplay plugin -k
			holoplay.hp_initialize()

			# when the user has loaded an image in the LKG tools panel, assume it is meant for viewing in the LKG as multiview
			if context.scene.LKG_image != None:
				num_multiview_images = int(wm.tilesHorizontal * wm.tilesVertical)
				multiview_first_image_path = context.scene.LKG_image.filepath
				#split into file, view number and extension
				multiview_image_path_split = multiview_first_image_path.rsplit('.',2)
				self._LKGtexArray = []

				for i in range(num_multiview_images):
					img_str = multiview_image_path_split[0] + '.' + str(i).zfill(2) + '.' + multiview_image_path_split[2]
					tex = bpy.data.images.load(img_str)
					self._LKGtexArray.append(tex)

				self._send_images_to_holoplay(self._LKGtexArray)
				OffScreenDraw.handle_add_viewer(self, context)
			else:
				offscreen = self._setup_offscreens(context, 1)
				#bufferForImage = Buffer(GL_BYTE, qs_viewWidth * qs_viewHeight * 4)
				if hp_myQuilt == None:
					self.setupMyQuilt()
				OffScreenDraw.handle_add(self, context, offscreen, hp_myQuilt[0])

			OffScreenDraw.is_enabled = True

			if context.area:
				# store the editor window from where the operator whas invoked
				context.area.tag_redraw()
			
			scn = context.scene			

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

			#check whether multiview render setup has been created
			cam_parent = bpy.data.objects.get("Multiview")
			if cam_parent is None:
				# change the render aspect ratio so the view in the looking glass does not get deformed
				aspect_ratio = wm.screenW / wm.screenH
				context.scene.render.resolution_x = context.scene.render.resolution_y * aspect_ratio

			context.window_manager.modal_handler_add(self)
			return {'RUNNING_MODAL'}

	def cancel(self, context):
		OffScreenDraw.handle_remove()
		OffScreenDraw.is_enabled = False
		holoplay.hp_release()

		if context.area:
			context.area.tag_redraw()

# ------------ UI Functions -------------
class looking_glass_window_setup(bpy.types.Operator):
	""" Creates a new window of type image editor """
	bl_idname = "lookingglass.window_setup"
	bl_label = "Create Window"
	bl_description = "Creates a new window of type image editor that can be used in the looking glass display."
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		# Call user prefs window
		bpy.ops.screen.area_dupli('INVOKE_DEFAULT')

		# Change area type
		area = bpy.context.window_manager.windows[-1].screen.areas[0]
		area.type = 'IMAGE_EDITOR'
		OffScreenDraw.area = area
		return {'FINISHED'}

def menu_func(self, context):
	''' Helper function to add the operator to menus '''
	self.layout.operator(OffScreenDraw.bl_idname)

def register():
	bpy.utils.register_class(OffScreenDraw)
	bpy.utils.register_class(looking_glass_window_setup)
	bpy.types.IMAGE_MT_view.append(menu_func)

def unregister():
	bpy.utils.unregister_class(looking_glass_window_setup)
	bpy.utils.unregister_class(OffScreenDraw)
	bpy.types.IMAGE_MT_view.remove(menu_func)

if __name__ == "__main__":
	register()