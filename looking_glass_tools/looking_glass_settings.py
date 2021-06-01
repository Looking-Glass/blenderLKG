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

import ctypes
import sys
import bpy
import time
import io
import numpy as np
import timeit
from . holoplay_service_api_commands import *
from . import cbor
from . import cffi

hardwareVersion = None

def ensure_site_packages(packages):
    """ `packages`: list of tuples (<import name>, <pip name>) """

    if not packages:
        return

    import site
    import importlib.util

    sys.path.append(site.getusersitepackages())

    modules_to_install = [module[1] for module in packages if not importlib.util.find_spec(module[0])]

    if modules_to_install:
        import subprocess

        if bpy.app.version < (2,91,0):
            python_binary = bpy.app.binary_path_python
        else:
            python_binary = sys.executable

        subprocess.run([python_binary, '-m', 'ensurepip'], check=True)
        subprocess.run([python_binary, '-m', 'pip', 'install', *modules_to_install, "--user"], check=True)

def send_message(sock, inputObj):
    import pynng
    from . import cbor

    out = cbor.dumps(inputObj)
    print("---------------")
    print("Command (" + str(len(out)) + " bytes, "+str(len(inputObj['bin']))+" binary): ")
    print(inputObj['cmd'])
    print("---------------")
    sock.send(out)
    # Driver will respond with a CBOR-formatted error message / information packet
    response = sock.recv()
    print("Response (" + str(len(response)) + " bytes): ")
    response_load = cbor.loads(response)
    print(response_load)
    print("---------------")
    return response_load

def send_quilt(sock, quilt, duration=10):
    print("===================================================")
    print("Sending quilt to HoloPlay Service")

    wm = bpy.context.window_manager
    aspect = wm.aspect
    W = wm.quiltX
    H = wm.quiltY
    vx = wm.tileX
    vy = wm.tileY
    vtotal = vx*vy

    from PIL import Image, ImageOps

    start_time = timeit.default_timer()
    print("Show a single quilt for " + str(duration) + " seconds, then wipe.")
    print("===================================================")

    # we need to get the data from a Blender image datablock because this is where we would put the image aquired from OpenGL
    # in the live view solution
    img0 = quilt
    W,H = img0.size

    # pre-allocate numpy array for better performance
    px0 = np.zeros(H*W*4, dtype=np.float32)
    # foreach_get is probably the fastest method to aquire the pixel values from a Blender image datablock
    img0.pixels.foreach_get(px0)
    print("Reading image from Blender image datablock: %.6f" % (timeit.default_timer() - start_time))

    # we need to convert the floats to integers from 0-255 for most image formats like PNG or BMP which can be send to HoloPlay Service
    # np.multiply(px0, 255, out=px0, casting="unsafe")
    px0 = px0 * 255
    pixels=px0.astype(np.uint8, order="C")

    pimg_time = timeit.default_timer()
    # for some reason the following only works when we create a PIL Image from a bytes-stream
    # so we need to convert the numpy array to bytes and read that
    pimg = Image.frombytes("RGBA", (W,H),  pixels.tobytes())

    # the result is flipped, probably due to numpy, flip it back
    pimg_flipped = ImageOps.flip(pimg)
    print("Converting pixels to bytes-stream and flipping took: %.6f" % (timeit.default_timer() - pimg_time))

    # the idea is that we convert the PIL image to a simple file format HoloPlay Service / stb_image can read
    # and store it in a BytesIO object instead of disk
    output = io.BytesIO()
    pimg_flipped.convert('RGBA').save(output, 'BMP')

    # the contents of the BytesIO object becomes our blob we send to HoloPlay Service
    blob = output.getvalue()
    settings = {'vx': vx,'vy': vy,'vtotal': vtotal,'aspect': aspect}
    send_message(sock, show_quilt(blob, settings))
    print("Reading quilt from Blender image datablock and sending it to HoloPlay Service took: %.6f" % (timeit.default_timer() - start_time))

# def send_quilt_from_np(sock, quilt, W=4096, H=4096, duration=10):
def send_quilt_from_np(sock, quilt, W=4096, H=4096, duration=10):
    print("===================================================")
    print("Sending quilt to HoloPlay Service")

    wm = bpy.context.window_manager
    aspect = wm.aspect
    W = wm.quiltX
    H = wm.quiltY
    vx = wm.tileX
    vy = wm.tileY
    vtotal = vx*vy

    from PIL import Image, ImageOps

    start_time = timeit.default_timer()

    # we get the data from the live view as numpy array
    px0 = quilt
    #W,H = px0.size

    # we need to convert the 0-1 floats to integers from 0-255
    # np.multiply(px0, 255, out=px0, casting="unsafe")
    pixels=px0.astype(np.uint8, order="C")

    pimg_time = timeit.default_timer()
    # for some reason the following only works when we create a PIL Image from a bytes-stream
    # so we need to convert the numpy array to bytes and read that
    pimg = Image.frombytes("RGBA", (W,H),  pixels.tobytes())


    # the result is flipped, probably due to numpy, flip it back
    pimg_flipped = ImageOps.flip(pimg)
    print("Converting pixels to bytes-stream and flipping took: %.6f" % (timeit.default_timer() - pimg_time))

    # the idea is that we convert the PIL image to a simple file format HoloPlay Service / stb_image can read
    # and store it in a BytesIO object instead of disk
    output = io.BytesIO()
    pimg_flipped.convert('RGBA').save(output, 'BMP')

    # the contents of the BytesIO object becomes our blob we send to HoloPlay Service
    blob = output.getvalue()
    settings = {'vx': vx,'vy': vy,'vtotal': vtotal,'aspect': aspect}
    send_message(sock, show_quilt(blob, settings))
    print("Reading quilt from numpy array and sending it to HoloPlay Service took in total: %.6f" % (timeit.default_timer() - start_time))

def init():
    global hp
    global sock
    global numDevices
    global screenW
    global screenH
    global aspect
    global hardwareVersion

    print("Init Settings")
    start_time = timeit.default_timer()

    wm = bpy.context.window_manager

    ws_url = "ws://localhost:11222/driver"
    driver_url = "ipc:///tmp/holoplay-driver.ipc"

    ensure_site_packages([
        ("pynng","pynng"),
        ("PIL", "Pillow")
    ])

    import pynng

    # This script should work identically whether addr = driver_url or addr = ws_url
    addr = driver_url

    sock = pynng.Req0(recv_timeout=2000)
    try:
        sock.dial(addr, block = True)
    except:
        print("Could not open socket. Is driver running?")
        sock = None
        return False

    response = send_message(sock, {'cmd':{'info':{}},'bin':''})
    if response != None:
        # create a dictionary with an index for this device
        devices = response['devices']
        if devices == []:
            print("No Looking Glass devices found")
        else:
            print("Reading settings from device")
            screenW = devices[0]['calibration']['screenW']['value']
            screenH = devices[0]['calibration']['screenH']['value']
            quiltX = devices[0]['defaultQuilt']['quiltX']
            quiltY = devices[0]['defaultQuilt']['quiltY']
            tileX = devices[0]['defaultQuilt']['tileX']
            tileY = devices[0]['defaultQuilt']['tileY']
            hardwareVersion = devices[0]['hardwareVersion'] # not storing this in wm because we need to change this to support multiple devices in the future
            aspect = screenW / screenH
            wm.screenW = screenW
            wm.screenH = screenH
            wm.aspect = aspect
            wm.quiltX = quiltX
            wm.quiltY = quiltY
            wm.tileX = tileX
            wm.tileY = tileY
            if hardwareVersion == 'portrait':
                wm.viewX = 420
                wm.viewY = 560
                wm.quiltX = 3360
                wm.quiltY = 3360
            # print(devices)
            # print(hardwareVersion)
            wm.numDevicesConnected = 1 # temporarily support only one device due to the way we globally store vars in the wm

    print("Number of devices found: " + str(wm.numDevicesConnected))

class looking_glass_reconnect_to_holoplay_service(bpy.types.Operator):
    """ Reconnects to Holoplay Service """
    bl_idname = "lookingglass.reconnect_to_holoplay_service"
    bl_label = "Reconnect to Service"
    bl_description = "Re-Initializes the connection to HoloPlay Service"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        init()
        return {'FINISHED'}
