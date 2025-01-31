# Copyright 2018-2021 The glTF-Blender-IO authors.
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
import re
import os
import json
import subprocess
import urllib.parse
from typing import List
from pathlib import Path

from ... import get_version_string
from io_scene_gltf2_msfs.io.com import gltf2_io
from io_scene_gltf2_msfs.io.com import gltf2_io_debug
from io_scene_gltf2_msfs.io.com import gltf2_io_extensions
from io_scene_gltf2_msfs.io.exp import gltf2_io_binary_data
from io_scene_gltf2_msfs.io.exp import gltf2_io_buffer
from io_scene_gltf2_msfs.io.exp import gltf2_io_image_data
from io_scene_gltf2_msfs.blender.exp import gltf2_blender_export_keys
from io_scene_gltf2_msfs.io.exp.gltf2_io_user_extensions import export_user_extensions

MS_FILETIME_EPOCH = 116444736000000000


class GlTF2Exporter:
    """
    The glTF exporter flattens a scene graph to a glTF serializable format.

    Any child properties are replaced with references where necessary
    """

    def __init__(self, export_settings):
        self.export_settings = export_settings
        self.__finalized = False

        copyright = export_settings[gltf2_blender_export_keys.COPYRIGHT] or None
        asset = gltf2_io.Asset(
            copyright=copyright,
            extensions=None,
            extras=None,
            generator="Khronos glTF Blender I/O v" + get_version_string(),
            min_version=None,
            version="2.0",
        )

        export_user_extensions("gather_asset_hook", export_settings, asset)

        self.__gltf = gltf2_io.Gltf(
            accessors=[],
            animations=[],
            asset=asset,
            buffers=[],
            buffer_views=[],
            cameras=[],
            extensions={},
            extensions_required=[],
            extensions_used=[],
            extras=None,
            images=[],
            materials=[],
            meshes=[],
            nodes=[],
            samplers=[],
            scene=-1,
            scenes=[],
            skins=[],
            textures=[],
        )

        self.__buffer = gltf2_io_buffer.Buffer()
        self.__images = {}

        # mapping of all glTFChildOfRootProperty types to their corresponding root level arrays
        self.__childOfRootPropertyTypeLookup = {
            gltf2_io.Accessor: self.__gltf.accessors,
            gltf2_io.Animation: self.__gltf.animations,
            gltf2_io.Buffer: self.__gltf.buffers,
            gltf2_io.BufferView: self.__gltf.buffer_views,
            gltf2_io.Camera: self.__gltf.cameras,
            gltf2_io.Image: self.__gltf.images,
            gltf2_io.Material: self.__gltf.materials,
            gltf2_io.Mesh: self.__gltf.meshes,
            gltf2_io.Node: self.__gltf.nodes,
            gltf2_io.Sampler: self.__gltf.samplers,
            gltf2_io.Scene: self.__gltf.scenes,
            gltf2_io.Skin: self.__gltf.skins,
            gltf2_io.Texture: self.__gltf.textures,
        }

        self.__propertyTypeLookup = [
            gltf2_io.AccessorSparseIndices,
            gltf2_io.AccessorSparse,
            gltf2_io.AccessorSparseValues,
            gltf2_io.AnimationChannel,
            gltf2_io.AnimationChannelTarget,
            gltf2_io.AnimationSampler,
            gltf2_io.Asset,
            gltf2_io.CameraOrthographic,
            gltf2_io.CameraPerspective,
            gltf2_io.MeshPrimitive,
            gltf2_io.TextureInfo,
            gltf2_io.MaterialPBRMetallicRoughness,
            gltf2_io.MaterialNormalTextureInfoClass,
            gltf2_io.MaterialOcclusionTextureInfoClass,
        ]

        self.__traverse(asset)

    @property
    def glTF(self):
        if not self.__finalized:
            raise RuntimeError("glTF requested, but buffers are not finalized yet")
        return self.__gltf

    def add_asobo_buffer_views(
        self, buffer_views
    ):  # This assumes there are no buffer views already in the glTF
        for asobo_buffer_view in buffer_views:
            # Add the buffer view to the glTF buffer views
            self.__gltf.buffer_views.append(asobo_buffer_view)
            binary_data = asobo_buffer_view.buffer.to_bytes()
            offset = self.__buffer.add(binary_data)
            asobo_buffer_view.buffer = 0
            asobo_buffer_view.byte_length = len(binary_data)
            asobo_buffer_view.byte_offset = offset

    def finalize_buffer(self, output_path=None, buffer_name=None, is_glb=False):
        """Finalize the glTF and write buffers."""
        if self.__finalized:
            raise RuntimeError("Tried to finalize buffers for finalized glTF file")

        if self.__buffer.byte_length > 0:
            if is_glb:
                uri = None
            elif output_path and buffer_name:
                with open(output_path + buffer_name, "wb") as f:
                    f.write(self.__buffer.to_bytes())
                uri = buffer_name
            else:
                uri = self.__buffer.to_embed_string()

            buffer = gltf2_io.Buffer(
                byte_length=self.__buffer.byte_length,
                extensions=None,
                extras=None,
                name=None,
                uri=uri,
            )
            self.__gltf.buffers.append(buffer)

        self.__finalized = True

        if is_glb:
            return self.__buffer.to_bytes()

    def add_draco_extension(self):
        """
        Register Draco extension as *used* and *required*.

        :return:
        """
        self.__gltf.extensions_required.append("KHR_draco_mesh_compression")
        self.__gltf.extensions_used.append("KHR_draco_mesh_compression")

    def finalize_images(self):
        """
        Write all images.
        """
        output_path = self.export_settings[gltf2_blender_export_keys.TEXTURE_DIRECTORY]

        if self.__images:
            os.makedirs(output_path, exist_ok=True)

        for name, image in self.__images.items():
            is_dds = image._dds_format != gltf2_io_image_data.DDSFormat.NONE
            if is_dds:
                # If output folder is named model, and there is an accompanying folder named texture, put textures there
                dir_name = os.path.dirname(output_path)
                if os.path.basename(dir_name).lower() == "model":
                    # Check for texture folder
                    texture_folder = os.path.join(os.path.dirname(dir_name), "TEXTURE")
                    if os.path.exists(texture_folder):
                        output_path = texture_folder

                dst_path = (
                    output_path + "/" + name + ".png"
                )  # We need to save as a PNG first in order to convert to DDS
            else:
                dst_path = output_path + "/" + name + image.file_extension
            with open(dst_path, "wb") as f:
                f.write(image.data)

            # Convert to DDS
            if is_dds:
                dds_format_table = {
                    gltf2_io_image_data.DDSFormat.BC1_UNORM: "BC1_UNORM",
                    gltf2_io_image_data.DDSFormat.BC3_UNORM: "BC3_UNORM",
                    gltf2_io_image_data.DDSFormat.BC5_SNORM: "BC5_SNORM",
                    gltf2_io_image_data.DDSFormat.BC7_UNORM: "BC7_UNORM",
                }
                dds_format = dds_format_table[image._dds_format]

                png_path = dst_path  # get old path, then get new path
                dst_path = output_path + "/" + name + image.file_extension

                texconv_path = self.export_settings["addon_settings"].texconv_file

                # Convert png_path to a Path (sometimes there is mixed forward slash and backslashes which causes an issue. Converting fixes that)
                png_path = Path(png_path)

                if texconv_path is None:
                    gltf2_io_debug.print_console(
                        "WARNING", "No texconv file is set, cannot convert image to DDS"
                    )
                else:
                    try:
                        output_lines = (
                            subprocess.run(
                                [
                                    texconv_path,
                                    "-y",
                                    "-o",
                                    str(os.path.dirname(png_path)),
                                    "-f",
                                    dds_format,
                                    str(png_path),
                                ],
                                check=True,
                                capture_output=True,
                            )
                            .stdout.decode("cp1252")
                            .split("\r\n")
                        )
                    except subprocess.CalledProcessError as e:
                        gltf2_io_debug.print_console(
                            "ERROR",
                            "Could not convert image {}: {}".format(png_path, e),
                        )
                        return None
                    else:
                        # Remove PNG file
                        os.remove(str(png_path))

                    # Get DDS file path
                    dds_path = None
                    for line in output_lines:
                        line = line.lstrip()
                        if line.startswith("writing "):
                            file = Path(line.split("writing ")[1])
                            if file.exists():
                                dds_path = file
                            else:
                                gltf2_io_debug.print_console(
                                    "ERROR",
                                    "Could not convert {} to DDS".format(png_path),
                                )

                    if dds_path is not None:
                        # Calculate file modified date with MSFS epoch
                        dds_file_stat = Path(dds_path).stat()
                        dds_file_mtime = (
                            dds_file_stat.st_mtime_ns / 100
                        ) + MS_FILETIME_EPOCH

                        # Now write the JSON file
                        dds_json = {
                            "Version": 2,
                            "SourceFileDate": dds_file_mtime,
                            "Flags": None,  # TODO: flags
                            "HasTransp": "A" in image._channels,
                        }

                        with open(f"{dds_path}.json", "w") as f:
                            json.dump(dds_json, f)

    def add_scene(self, scene: gltf2_io.Scene, active: bool = False):
        """
        Add a scene to the glTF.

        The scene should be built up with the generated glTF classes
        :param scene: gltf2_io.Scene type. Root node of the scene graph
        :param active: If true, sets the glTD.scene index to the added scene
        :return: nothing
        """
        if self.__finalized:
            raise RuntimeError("Tried to add scene to finalized glTF file")

        # for node in scene.nodes:
        #     self.__traverse(node)
        scene_num = self.__traverse(scene)
        if active:
            self.__gltf.scene = scene_num

    def add_animation(self, animation: gltf2_io.Animation):
        """
        Add an animation to the glTF.

        :param animation: glTF animation, with python style references (names)
        :return: nothing
        """
        if self.__finalized:
            raise RuntimeError("Tried to add animation to finalized glTF file")

        self.__traverse(animation)

    def add_asobo_asset_extensions(self, extensions):
        """
        Add Asobo asset extensions to the glTF.

        :param extensions: glTF extensions in a dictionary
        :return: nothing
        """
        if self.__finalized:
            raise RuntimeError(
                "Tried to add Asobo asset extensions to finalized glTF file"
            )

        for key, value in extensions.items():
            self.__gltf.asset.extensions[key] = value

            # Add extension to extensions used
            self.add_extension_used(key)

    def __to_reference(self, property):
        """
        Append a child of root property to its respective list and return a reference into said list.

        If the property is not child of root, the property itself is returned.
        :param property: A property type object that should be converted to a reference
        :return: a reference or the object itself if it is not child or root
        """
        gltf_list = self.__childOfRootPropertyTypeLookup.get(type(property), None)
        if gltf_list is None:
            # The object is not of a child of root --> don't convert to reference
            return property

        return self.__append_unique_and_get_index(gltf_list, property)

    def add_extension_required(self, extension):
        """
        Add an extension to extensionsRequired in the glTF.

        :param extension: a glTF extension
        :return: nothing
        """
        if extension not in self.__gltf.extensions_required:
            self.__gltf.extensions_required.append(extension)

    def add_extension_used(self, extension):
        """
        Add an extension to extensionsUsed in the glTF.

        :param extension: a glTF extension
        :return: nothing
        """
        if extension not in self.__gltf.extensions_used:
            self.__gltf.extensions_used.append(extension)

    @staticmethod
    def __append_unique_and_get_index(target: list, obj):
        if obj in target:
            return target.index(obj)
        else:
            index = len(target)
            target.append(obj)
            return index

    def __add_image(self, image: gltf2_io_image_data.ImageData):
        name = image.adjusted_name()
        count = 1
        regex = re.compile(r"-\d+$")
        while name in self.__images.keys():
            regex_found = re.findall(regex, name)
            if regex_found:
                name = re.sub(regex, "-" + str(count), name)
            else:
                name += "-" + str(count)

            count += 1
        # TODO: allow embedding of images (base64)

        self.__images[name] = image

        texture_dir = self.export_settings[gltf2_blender_export_keys.TEXTURE_DIRECTORY]
        abs_path = os.path.join(texture_dir, name + image.file_extension)
        rel_path = os.path.relpath(
            abs_path,
            start=self.export_settings[gltf2_blender_export_keys.FILE_DIRECTORY],
        )
        return _path_to_uri(rel_path)

    @classmethod
    def __get_key_path(cls, d: dict, keypath: List[str], default):
        """Create if necessary and get the element at key path from a dict"""
        key = keypath.pop(0)

        if len(keypath) == 0:
            v = d.get(key, default)
            d[key] = v
            return v

        d_key = d.get(key, {})
        d[key] = d_key
        return cls.__get_key_path(d[key], keypath, default)

    def traverse_extensions(self):
        self.__traverse(self.__gltf.extensions)

    def __traverse(self, node):
        """
        Recursively traverse a scene graph consisting of gltf compatible elements.

        The tree is traversed downwards until a primitive is reached. Then any ChildOfRoot property
        is stored in the according list in the glTF and replaced with a index reference in the upper level.
        """

        def __traverse_property(node):
            for member_name in [
                a
                for a in dir(node)
                if not a.startswith("__") and not callable(getattr(node, a))
            ]:
                new_value = self.__traverse(getattr(node, member_name))
                setattr(
                    node, member_name, new_value
                )  # usually this is the same as before

                # # TODO: maybe with extensions hooks we can find a more elegant solution
                # if member_name == "extensions" and new_value is not None:
                #     for extension_name in new_value.keys():
                #         self.__append_unique_and_get_index(self.__gltf.extensions_used, extension_name)
                #         self.__append_unique_and_get_index(self.__gltf.extensions_required, extension_name)
            return node

        # traverse nodes of a child of root property type and add them to the glTF root
        if type(node) in self.__childOfRootPropertyTypeLookup:
            node = __traverse_property(node)
            idx = self.__to_reference(node)
            # child of root properties are only present at root level --> replace with index in upper level
            return idx

        # traverse lists, such as children and replace them with indices
        if isinstance(node, list):
            for i in range(len(node)):
                node[i] = self.__traverse(node[i])
            return node

        if isinstance(node, dict):
            for key in node.keys():
                node[key] = self.__traverse(node[key])
            return node

        # traverse into any other property
        if type(node) in self.__propertyTypeLookup:
            return __traverse_property(node)

        # binary data needs to be moved to a buffer and referenced with a buffer view
        if isinstance(node, gltf2_io_binary_data.BinaryData):
            buffer_view = self.__buffer.add_and_get_view(node)
            return self.__to_reference(buffer_view)

        # image data needs to be saved to file
        if isinstance(node, gltf2_io_image_data.ImageData):
            image = self.__add_image(node)
            return image

        # extensions
        if isinstance(node, gltf2_io_extensions.Extension):
            extension = self.__traverse(node.extension)
            self.__append_unique_and_get_index(self.__gltf.extensions_used, node.name)
            if node.required:
                self.__append_unique_and_get_index(
                    self.__gltf.extensions_required, node.name
                )

            # extensions that lie in the root of the glTF.
            # They need to be converted to a reference at place of occurrence
            if isinstance(node, gltf2_io_extensions.ChildOfRootExtension):
                root_extension_list = self.__get_key_path(
                    self.__gltf.extensions, [node.name] + node.path, []
                )
                idx = self.__append_unique_and_get_index(root_extension_list, extension)
                return idx

            return extension

        # do nothing for any type that does not match a glTF schema (primitives)
        return node


def _path_to_uri(path):
    path = os.path.normpath(path)
    path = path.replace(os.sep, "/")
    return urllib.parse.quote(path)
