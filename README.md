*Last updated: February 21, 2019*
*Version: 1.8*

This Getting Started Guide is for the Blender Add-on created specifically for use with the Looking Glass. It features live-display of the camera view in the image editor, an automatic render-setup for Cycles and the option to view rendered multi-view image sequences in the Looking Glass.

The addon requires Blender 2.79b, it does not work in Blender 2.8x yet.

### Installing

* If you have not done so, install the HoloPlay system library here: [HoloPlayAPI](http://static-files.lookingglassfactory.com.s3.amazonaws.com/HoloPlayCAPI/Install%20HoloPlayCAPI.exe)
    * Do **not** uncheck the _Add to PATH_ option, as the Blender Add-on requires this.
* Open Blender, and go to _File → User Preferences → Add-ons → Install Add-on from file_.
* Select the .zip and click "Install Add-on from file" on the top right.
* Enable the addon by checking the box next to it on the left.
* Click on the triangle to open up the addon preferences.
    * The calibration loader should already be set there. In that case everything is fine.
    * If not, click on the file browser icon.
    * Locate the calibration loader and click accept.
* Click "Save User Settings" to keep the addon enabled.

### Usage

* The main UI can be found in the _3D Tool Shelf → Looking Glass Tab_.
* **Create Render Setup** will place 45 (invisible) cameras parented to an empty with cube representation into the scene. The cube determines what is visible inside the Looking Glass after render. The cameras are parented to the cube so move, rotate and scale the cube to place the cameras in the scene. The setup created uses the Blender multiview system.
* **Create LKG Window** opens up a detached window with image editor ready. In the image editor use the new menu item _View → Looking Glass Live View_ to start the live display of the viewport camera. Minimize the bar at the bottom so that the entirety of the window is just the Looking Glass preview, otherwise the center will be off when going fullscreen. Next place the window in the Looking Glass and use ALT + F11 to make it fullscreen.
    * Make sure you are using extended mode in Windows display settings to use the live preview!

### Viewing your Multiview Renders
* **LKG image to view** You can select an image rendered for the LKG in Blender here. Only images that have been saved to disk as multiview sequence work. The LKG window will show the image as long as one is selected in this field but you will have to run the _View → Looking Glass Live View_ command again.

## Authors

* **Gottfried Hofmann** 
* **Kyle Appelgate** 

## License

The blender addon portion of this project is licensed under the GPL v2 License - see the [LICENSE](LICENSE) file for details.

The HoloPlayAPI is copyright Looking Glass Factory 2018, and is licensed under the following agreement:
[http://static-files.lookingglassfactory.com.s3.amazonaws.com/HoloPlayCAPI/License.pdf](http://static-files.lookingglassfactory.com.s3.amazonaws.com/HoloPlayCAPI/License.pdf)
