# blenderLKG
Blender SKD for the Looking Glass. Features live-display of the camera view in the image editor, an automatic render-setup for Cycles and the option to view rendered multiview image sequences in the Looking Glass.

### Prerequisites

The addon requires Blender 2.79b, it does not work in Blender 2.8x yet.
It also requires the HoloPlay C API to be installed, which can be downloaded here: http://static-files.lookingglassfactory.com.s3.amazonaws.com/HoloPlayCAPI/Install%20HoloPlayCAPI.exe (must not uncheck the Add to PATH option, as the Blender plugin uses this)

### Installing

* Go to _File → User Preferences → Add-ons → Install Add-on from file_.
* Select the .zip and click "Install Add-on from file" on the top right.
* Enable the addon by checking the box next to it on the left.
* Click on the triangle to open up the addon preferences.
    * The calibration loader should already be set there. In that case everything is fine.
    * If not, click on the file browser icon.
    * Locate the calibration loader and click accept.
* Click "Save User Settings" to keep the addon enabled.

### Usage

* The main UI can be found in the _Tool Shelf → Looking Glass Tab_.
* **Create Render Setup** will place 32 (invisible) cameras parented to an empty with cube representation into the scene. The cube determines what is visible inside the Looking Glass after render. The cameras are parented to the cube so move, rotate and scale the cube to place the cameras in the scene. The setup created uses the Blender multiview system.
* **Create LKG Window** opens up a detached window with image editor ready. In the image editor use the new menu item _View → Looking Glass Live View_ to start the live display of the viewport camera. Next place the window in the Looking Glass and use ALT + F11 to make it fullscreen.
* **LKG image to view** You can select an image rendered for the LKG in Blender here. Only images that have been saved to disk as multiview sequence work. The LKG window will show the image as long as one is selected in this field but you will have to run the _View → Looking Glass Live View_ command again.


## Authors

* **Gottfried Hofmann** 
* **Kyle Appelgate** 

## License

The blender addon portion of this project is licensed under the GPL v2 License - see the [LICENSE](LICENSE) file for details.

The HoloPlayAPI is copyright Looking Glass Factory 2018, and is licensed under the following agreement:
https://lookingglassfactory.com/holoplay-sdk-license-agreement/

The HoloPlayAPI is **NOT** to be distributed with the Blender Addon! It will be included in an installation we will be distributing to Looking Glass users, which the Blender addon will make calls to.

