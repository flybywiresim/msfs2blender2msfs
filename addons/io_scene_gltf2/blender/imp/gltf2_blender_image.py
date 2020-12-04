# Copyright 2018-2019 The glTF-Blender-IO authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import bpy
import os
import tempfile
import numpy
from os.path import dirname, join, isfile, basename, normpath
import urllib.parse
import re

from ...io.imp.gltf2_io_binary import BinaryData


# Note that Image is not a glTF2.0 object
class BlenderImage():
    """Manage Image."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    # A32NX
    # Original is from https://github.com/bestdani/msfs2blend
    @staticmethod
    def convert_normal_image(normal_image):
        pixels = numpy.array(normal_image.pixels[:]).reshape((-1, 4))
        rgb_pixels = pixels[:, 0:3]
        rgb_pixels[:, 1] = 1.0 - rgb_pixels[:, 1]
        rgb_pixels[:, 2] = numpy.sqrt(
            1 - (rgb_pixels[:, 0] - 0.5) ** 2 - (rgb_pixels[:, 1] - 0.5) ** 2
        )
        pixel_data = pixels.reshape((-1, 1)).transpose()[0]
        normal_image.pixels = pixel_data
        try:
            normal_image.save()
        except RuntimeError:
            print(f"ERROR: could not save converted image {normal_image.name}")

    @staticmethod
    def create(gltf, img_idx, label=''):
        """Image creation."""
        img = gltf.data.images[img_idx]
        img_name = img.name

        if img.blender_image_name is not None:
            # Image is already used somewhere
            return

        tmp_dir = None
        try:
            # if img.uri is not None and not img.uri.startswith('data:'):
            # Image stored in a file
            img_from_file = True
            path = join(dirname(gltf.filename), _uri_to_path(img.uri))
            img_name = img_name or basename(path)
            if not isfile(path):
                gltf.log.error("Missing file (index " + str(img_idx) + "): " + img.uri)
                return
            # else:
            #     # Image stored as data => create a tempfile, pack, and delete file
            #     img_from_file = False
            #     img_data = BinaryData.get_image_data(gltf, img_idx)
            #     if img_data is None:
            #         return
            #     img_name = img_name or 'Image_%d' % img_idx
            #     tmp_dir = tempfile.TemporaryDirectory(prefix='gltfimg-')
            #     filename = _filenamify(img_name) or 'Image_%d' % img_idx
            #     filename += _img_extension(img)
            #     path = join(tmp_dir.name, filename)
            #     with open(path, 'wb') as f:
            #         f.write(img_data)

            num_images = len(bpy.data.images)
            blender_image = bpy.data.images.load(os.path.abspath(path), check_existing=img_from_file)
            # A32NX
            print('blender image create bpy.data.images.load(path) ' + str(path))
            if label == 'NORMALMAP':
                BlenderImage.convert_normal_image(blender_image)
            if len(bpy.data.images) != num_images:  # If created a new image
                blender_image.name = img_name
                if gltf.import_settings['import_pack_images'] or not img_from_file:
                    blender_image.pack()

            img.blender_image_name = blender_image.name

        finally:
            if tmp_dir is not None:
                tmp_dir.cleanup()

def _uri_to_path(uri):
    uri = urllib.parse.unquote(uri)
    return normpath(uri)

def _img_extension(img):
    if img.mime_type == 'image/png':
        return '.png'
    if img.mime_type == 'image/jpeg':
        return '.jpg'
    return ''

def _filenamify(s):
    s = s.strip().replace(' ', '_')
    return re.sub(r'(?u)[^-\w.]', '', s)
