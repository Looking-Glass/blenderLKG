*Last updated: May 06, 2021*
*Version: 3.1*

This Getting Started Guide is for the Blender Add-on created specifically for use with the Looking Glass. It features live-display of the camera view in the image editor, an automatic render-setup for Cycles and the option to view rendered multi-view image sequences in the Looking Glass.

The version of the addon requires at least Blender 2.92.

### Installing

* If you have not done so, install HoloPlayService.

* Open Blender, and go to _Edit → Preferences → Add-ons → Install..._.
* Select the .zip and click "Install Add-on from file" on the top right.
* Enable the addon by checking the box next to it on the left.
* Click "Save User Settings" to keep the addon enabled.

### Usage

* The main UI can be found in the _Sidebar → LKG Tab_.
* **Create Render Setup** will place 45 (invisible) cameras parented to an object that represents the frustum into the scene. The frustum determines what is visible inside the Looking Glass after render. The cameras are parented to the frustum so move, rotate and scale the frumstum to place the cameras in the scene. The setup created uses the Blender multiview system.
* **Send Quilt** will show the current frame of the viewport or the rendering open in the image selector in the Looking Glass.

### Rendering and saving
* Rendering works using the multiview system in Blender so you can render with F12 or render animations with CTRL+F12. The only difference to regular rendering is that Blender will store 45 images to disk for every frame rendered. Each of those images corresponds to one view of the 45 cameras.

### Viewing your Multiview Renders
* **LKG image to view** You can select an image rendered for the LKG in Blender here. Only images that have been saved to disk as multiview sequence work. The LKG window will show the image as long as one is selected in this field but you will have to run the _View → Looking Glass Live View_ command again.
* Support for viewing rendered animations is not yet implemented but upcoming.

## Authors

* **Gottfried Hofmann** 
* **Kyle Appelgate**
* **Evan Kahn** 

## License

The Blender addon portion of this project is licensed under the GPL v2 License - see the [LICENSE](LICENSE) file for details.
