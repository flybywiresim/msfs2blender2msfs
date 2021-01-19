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
from mathutils import Vector, Quaternion, Matrix
import subprocess
import pathlib
import os
import configparser
import codecs
from .gltf2_blender_scene import BlenderScene


class BlenderGlTF():
    """Main glTF import class."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def create(gltf, report, addon_prefs, import_settings, texture_folder_name, filepath):
        BlenderGlTF.load_dds_images(gltf, report, addon_prefs, import_settings, texture_folder_name, filepath)
        """Create glTF main method, with optional profiling"""
        profile = bpy.app.debug_value == 102
        if profile:
            import cProfile, pstats, io
            from pstats import SortKey
            pr = cProfile.Profile()
            pr.enable()
            BlenderGlTF._create(gltf)
            pr.disable()
            s = io.StringIO()
            sortby = SortKey.TIME
            ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
            ps.print_stats()
            print(s.getvalue())
        else:
            BlenderGlTF._create(gltf)

    @staticmethod
    def _create(gltf):
        """Create glTF main worker method."""
        BlenderGlTF.set_convert_functions(gltf)
        BlenderGlTF.pre_compute(gltf)
        BlenderScene.create(gltf)

    @staticmethod
    def set_convert_functions(gltf):
        yup2zup = bpy.app.debug_value != 100

        if yup2zup:
            # glTF Y-Up space --> Blender Z-up space
            # X,Y,Z --> X,-Z,Y
            def convert_loc(x): return Vector([x[0], -x[2], x[1]])
            def convert_quat(q): return Quaternion([q[3], q[0], -q[2], q[1]])
            def convert_normal(n): return Vector([n[0], -n[2], n[1]])
            def convert_scale(s): return Vector([s[0], s[2], s[1]])
            def convert_matrix(m):
                return Matrix([
                    [ m[0], -m[ 8],  m[4],  m[12]],
                    [-m[2],  m[10], -m[6], -m[14]],
                    [ m[1], -m[ 9],  m[5],  m[13]],
                    [ m[3], -m[11],  m[7],  m[15]],
                ])

            # Correction for cameras and lights.
            # glTF: right = +X, forward = -Z, up = +Y
            # glTF after Yup2Zup: right = +X, forward = +Y, up = +Z
            # Blender: right = +X, forward = -Z, up = +Y
            # Need to carry Blender --> glTF after Yup2Zup
            gltf.camera_correction = Quaternion((2**0.5/2, 2**0.5/2, 0.0, 0.0))

        else:
            def convert_loc(x): return Vector(x)
            def convert_quat(q): return Quaternion([q[3], q[0], q[1], q[2]])
            def convert_normal(n): return Vector(n)
            def convert_scale(s): return Vector(s)
            def convert_matrix(m):
                return Matrix([m[0::4], m[1::4], m[2::4], m[3::4]])

            # Same convention, no correction needed.
            gltf.camera_correction = None

        gltf.loc_gltf_to_blender = convert_loc
        gltf.quaternion_gltf_to_blender = convert_quat
        gltf.normal_gltf_to_blender = convert_normal
        gltf.scale_gltf_to_blender = convert_scale
        gltf.matrix_gltf_to_blender = convert_matrix

    @staticmethod
    def pre_compute(gltf):
        """Pre compute, just before creation."""
        # default scene used
        gltf.blender_scene = None

        # Check if there is animation on object
        # Init is to False, and will be set to True during creation
        gltf.animation_object = False

        # Blender material
        if gltf.data.materials:
            for material in gltf.data.materials:
                material.blender_material = {}

        # images
        if gltf.data.images is not None:
            for img in gltf.data.images:
                img.blender_image_name = None

        if gltf.data.nodes is None:
            # Something is wrong in file, there is no nodes
            return

        for node in gltf.data.nodes:
            # Weight animation management
            node.weight_animation = False

        # Dispatch animation
        if gltf.data.animations:
            for node in gltf.data.nodes:
                node.animations = {}

            track_names = set()
            for anim_idx, anim in enumerate(gltf.data.animations):
                # Pick pair-wise unique name for each animation to use as a name
                # for its NLA tracks.
                desired_name = anim.name or "Anim_%d" % anim_idx
                anim.track_name = BlenderGlTF.find_unused_name(track_names, desired_name)
                track_names.add(anim.track_name)

                for channel_idx, channel in enumerate(anim.channels):
                    if channel.target.node is None:
                        continue

                    if anim_idx not in gltf.data.nodes[channel.target.node].animations.keys():
                        gltf.data.nodes[channel.target.node].animations[anim_idx] = []
                    gltf.data.nodes[channel.target.node].animations[anim_idx].append(channel_idx)
                    # Manage node with animation on weights, that are animated in meshes in Blender (ShapeKeys)
                    if channel.target.path == "weights":
                        gltf.data.nodes[channel.target.node].weight_animation = True

        # Meshes
        if gltf.data.meshes:
            for mesh in gltf.data.meshes:
                mesh.blender_name = {}  # caches Blender mesh name

        # Calculate names for each mesh's shapekeys
        for mesh in gltf.data.meshes or []:
            mesh.shapekey_names = []
            used_names = set()

            # Some invalid glTF files has empty primitive tab
            if len(mesh.primitives) > 0:
                for sk, target in enumerate(mesh.primitives[0].targets or []):
                    if 'POSITION' not in target:
                        mesh.shapekey_names.append(None)
                        continue

                    # Check if glTF file has some extras with targetNames. Otherwise
                    # use the name of the POSITION accessor on the first primitive.
                    shapekey_name = None
                    if mesh.extras is not None:
                        if 'targetNames' in mesh.extras and sk < len(mesh.extras['targetNames']):
                            shapekey_name = mesh.extras['targetNames'][sk]
                    if shapekey_name is None:
                        if gltf.data.accessors[target['POSITION']].name is not None:
                            shapekey_name = gltf.data.accessors[target['POSITION']].name
                    if shapekey_name is None:
                        shapekey_name = "target_" + str(sk)

                    shapekey_name = BlenderGlTF.find_unused_name(used_names, shapekey_name)
                    used_names.add(shapekey_name)

                    mesh.shapekey_names.append(shapekey_name)

    @staticmethod
    def find_unused_name(haystack, desired_name):
        """Finds a name not in haystack and <= 63 UTF-8 bytes.
        (the limit on the size of a Blender name.)
        If a is taken, tries a.001, then a.002, etc.
        """
        stem = desired_name[:63]
        suffix = ''
        cntr = 1
        while True:
            name = stem + suffix

            if len(name.encode('utf-8')) > 63:
                stem = stem[:-1]
                continue

            if name not in haystack:
                return name

            suffix = '.%03d' % cntr
            cntr += 1

    # Original is from https://github.com/bestdani/msfs2blend
    @staticmethod
    def load_dds_images(gltf, report, addon_prefs, import_settings, texture_folder_name, filepath):
        file_path = pathlib.Path(filepath)
        textures_allowed = addon_prefs.textures_allowed
        if addon_prefs.flightsim_dir in filepath or import_settings["include_sim_textures"]: # we are importing something in the flight sim path, OR the user has specified to include simulator texture files
            texture_in_dir = file_path.parent.parent / texture_folder_name
            common_texture_in_dir = pathlib.Path(addon_prefs.flightsim_dir) # emulate asobo's file system
        else: # we are importing outside of the flight sim path and the user doesn't want to import flight simulator textures
            texture_in_dir = file_path.parent.parent / texture_folder_name
            common_texture_in_dir = None # don't look for common textures

        if textures_allowed:
            texconv_path = pathlib.Path(addon_prefs.texconv_file)
            texture_out_dir = pathlib.Path(addon_prefs.texture_target_dir)
        else:
            texconv_path = None
            texture_out_dir = None

        if gltf.data.images is not None:
            result = BlenderGlTF.convert_images(gltf, texture_in_dir, common_texture_in_dir, texconv_path, texture_out_dir, report)
        else:
            result = None

        print('done doing tex things ' + str(result))

    # Original is from https://github.com/bestdani/msfs2blend
    @staticmethod
    def convert_images(gltf, texture_in_dir, common_texture_in_dir, texconv_path, texture_out_dir, report) -> list:
        to_convert_images = []
        converted_images = []
        final_image_paths = []
        common_files = []
        if common_texture_in_dir is not None:
            for root, _, files in os.walk(common_texture_in_dir):
                for file in files:
                    common_files.append((root, file))
        for i, image in enumerate(gltf.data.images):
            try:
                dds_file = texture_in_dir / image.uri
                # if file doesnt exist
                # check in detail maps folder
            except KeyError:
                report({'ERROR'}, f"invalid image at {i}. Try enabling Flight Simulator textures and making sure your simulator location is correct in add-on preferences. Also be sure to check if the texture actually exists")
                final_image_paths.append(None)

            if not dds_file.exists():
                if common_texture_in_dir is not None and common_files:
                    for root, file in common_files:
                        if file == image.uri:
                            if "Community" in root: # community textures always override official files
                                config_file = pathlib.Path(root).parent / "aircraft.cfg"
                                if config_file.exists():
                                    config = configparser.ConfigParser(strict = False)
                                    config.read_file(codecs.open(config_file, "r", "utf-8"))
                                    if "VARIATION" in config.sections(): # this is a livery, skip the texture
                                        continue # something to note - some liveries could be misconfigured and not have a variation section, in which case it would be treated as a regular aircraft, causing an issue. at some point this should probably be fixed, but as the circumstances are rare it's fine
                                dds_file = pathlib.Path(root) / file
                                break
                            else:
                                dds_file = pathlib.Path(root) / file # no continue since we still want to search for community textures
                if not dds_file.exists():
                    report({'ERROR'}, f"Invalid image file location at {i}: {dds_file}. Try enabling Flight Simulator textures and making sure your simulator location is correct in add-on preferences. Also be sure to check if the texture actually exists")
                    final_image_paths.append(None)
                            
            final_image_paths.append('')
            if dds_file is None: # if the file does not exist, append a "fake" path
                to_convert_images.append('')
            else:
                to_convert_images.append(str(dds_file))

        output_dir_param = str(texture_out_dir)
        texture_out_dir.mkdir(parents=True, exist_ok=True)
        report({'INFO'}, "converting images with texconv")
        try:
            output_lines = subprocess.run(
                [
                    str(texconv_path),
                    '-y',
                    '-o', output_dir_param,
                    '-f', 'rgba',
                    '-ft', 'png',
                    *to_convert_images
                ],
                check=True,
                capture_output=True
            ).stdout.decode('cp1252').split('\r\n')
        except subprocess.CalledProcessError as e:
            report({'ERROR'}, f"could not convert image textures {e}")
            return final_image_paths
        else:
            for line in output_lines:
                line: str
                if line.startswith('writing'):
                    png_file = line[len('writing '):]
                    path = pathlib.Path(png_file)
                    if path.exists():
                        converted_images.append(path)
                    else:
                        converted_images.append(None)
                elif line.startswith('reading') and 'FAILED' in line: # this gets called if we added a fake path
                    converted_images.append(None)

            conv_i = 0
            for i, image in enumerate(final_image_paths):
                try:
                    # final_image_paths[i] = converted_images[conv_i]
                    gltf.data.images[conv_i].uri = str(converted_images[conv_i])
                except IndexError:
                    final_image_paths[i] = None
                else:
                    conv_i += 1
            return final_image_paths