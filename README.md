# blenderLKG
Blender SKD for the Looking Glass. Features live-display of the camera view in the image editor and an automatic render-setup for Cycles.

### Prerequisites

The addon requires Blender 2.79b, it does not work in Blender 2.8x yet.

### Installing

```
* Go to File -> User Preferences -> Add-ons -> Install Add-on from file.
* Select the .zip and click "Install Add-on from file" on the top right.
* Enable the addon by checking the box next to it on the left.
* Click on the triangle to open up the addon preferences.
* In the addon preferences, click on the file browser icon.
* Locate the calibration loader and click accept.
* Click "Save User Settings" to keep the addon enabled.
```

### Usage

```
* The main UI can be found in the Tool Shelf -> Looking Glass Tab.
* **Create Live Window** opens up a detached window with image editor ready. In the image editor use the new menu item View -> Looking Glass Live View to start the live display of the viewport camera. Next place the window in the Looking Glass and use ALT + F11 to make it fullscreen.
* **Create Render Setup** will place 32 cameras parented to a cube into the scene. The cube determines what is visible inside the Looking Glass after render. The cameras are parented to the cube so move, rotate and scale the cube to place the cameras in the scene. The setup created uses the Blender multiview system.
```

## Authors

* **Gottfried Hofmann** 
* **Kyle Appelgate** 

## License

This project is licensed under the GPL v2 License - see the [LICENSE.md](LICENSE.md) file for details
