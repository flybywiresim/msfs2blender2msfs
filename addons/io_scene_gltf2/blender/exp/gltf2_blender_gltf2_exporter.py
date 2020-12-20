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
import re
import os
import urllib.parse
import ctypes
import struct
from typing import List

from ... import get_version_string
from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.io.com import gltf2_io_extensions
# from io_scene_gltf2.io.com import gltf2_io_constants
from io_scene_gltf2.io.exp import gltf2_io_binary_data
from io_scene_gltf2.io.exp import gltf2_io_buffer
from io_scene_gltf2.io.exp import gltf2_io_asobo_buffer
from io_scene_gltf2.io.exp import gltf2_io_image_data
from io_scene_gltf2.blender.exp import gltf2_blender_export_keys


STRUCT_POSITION = struct.Struct('fff')
STRUCT_TANGENT = struct.Struct('bbbb')
STRUCT_NORMAL = struct.Struct('bbbb')
STRUCT_UV = struct.Struct('ee')
STRUCT_JOINT = struct.Struct('HHHH')
STRUCT_WEIGHT1 = struct.Struct('f')
STRUCT_WEIGHT4 = struct.Struct('HHHH')
STRUCT_COLOR_VTX = struct.Struct('HHHH')
STRUCT_COLOR_BLEND = struct.Struct('bbbb')

# attr_to_struct_vtx = {
#     "POSITION": STRUCT_POSITION,
#     "TANGENT": STRUCT_TANGENT,
#     "NORMAL": STRUCT_NORMAL,
#     "TEXCOORD_0": STRUCT_UV,
#     "TEXCOORD_1": STRUCT_UV,
#     "COLOR_0": STRUCT_COLOR_VTX,
# }

# attr_to_struct_blend1 = {
#     "POSITION": STRUCT_POSITION,
#     "TANGENT": STRUCT_TANGENT,
#     "NORMAL": STRUCT_NORMAL,
#     "TEXCOORD_0": STRUCT_UV,
#     "TEXCOORD_1": STRUCT_UV,
#     "JOINTS_0": STRUCT_JOINT,
#     "WEIGHTS_0": STRUCT_WEIGHT1,
#     "COLOR_0": STRUCT_COLOR_BLEND,
# }

# attr_to_struct_blend4 = {
#     "POSITION": STRUCT_POSITION,
#     "TANGENT": STRUCT_TANGENT,
#     "NORMAL": STRUCT_NORMAL,
#     "TEXCOORD_0": STRUCT_UV,
#     "TEXCOORD_1": STRUCT_UV,
#     "JOINTS_0": STRUCT_JOINT,
#     "WEIGHTS_0": STRUCT_WEIGHT4,
#     "COLOR_0": STRUCT_COLOR_BLEND,
# }


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
            generator='Khronos glTF Blender I/O v' + get_version_string(),
            min_version=None,
            version='2.0')

        self.component_nb_dict = {}
        self.component_nb_dict['SCALAR'] = 1
        self.component_nb_dict['VEC2'] = 2
        self.component_nb_dict['VEC3'] = 3
        self.component_nb_dict['VEC4'] = 4
        self.component_nb_dict['MAT2'] = 4
        self.component_nb_dict['MAT3'] = 9
        self.component_nb_dict['MAT4'] = 16

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
            textures=[]
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
            gltf2_io.Texture: self.__gltf.textures
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
            gltf2_io.MaterialOcclusionTextureInfoClass
        ]

        # These are the 8 predefined buffer views that asobo models use
        # No other buffer views should be created
        self.__asobo_buffer_views = {
            'bufferViewFloatMat4': None,
            'bufferViewAnimationFloatScalar': None,
            'bufferViewAnimationFloatVec3': None,
            'bufferViewAnimationFloatVec4': None,
            'BufferViewVertexND': None,
            'BufferViewIndex': None,
            'BufferViewVertex4Blend': None,
            'BufferViewVertex1Blend': None,
        }

        self.__asobo_buffer_views['bufferViewFloatMat4'] = gltf2_io.BufferView(
            buffer=gltf2_io_asobo_buffer.AsoboBuffer(),
            byte_length=0,
            byte_offset=None,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='bufferViewFloatMat4',
            target=None
        )
        self.__gltf.buffer_views.append(self.__asobo_buffer_views['bufferViewFloatMat4'])

        self.__asobo_buffer_views['bufferViewAnimationFloatScalar'] = gltf2_io.BufferView(
            buffer=gltf2_io_asobo_buffer.AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='bufferViewAnimationFloatScalar',
            target=None
        )
        self.__gltf.buffer_views.append(self.__asobo_buffer_views['bufferViewAnimationFloatScalar'])

        self.__asobo_buffer_views['bufferViewAnimationFloatVec3'] = gltf2_io.BufferView(
            buffer=gltf2_io_asobo_buffer.AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='bufferViewAnimationFloatVec3',
            target=None
        )
        self.__gltf.buffer_views.append(self.__asobo_buffer_views['bufferViewAnimationFloatVec3'])

        self.__asobo_buffer_views['bufferViewAnimationFloatVec4'] = gltf2_io.BufferView(
            buffer=gltf2_io_asobo_buffer.AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='bufferViewAnimationFloatVec4',
            target=None
        )
        self.__gltf.buffer_views.append(self.__asobo_buffer_views['bufferViewAnimationFloatVec4'])

        self.__asobo_buffer_views['BufferViewVertexND'] = gltf2_io.BufferView(
            buffer=gltf2_io_asobo_buffer.AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=36,
            extensions=None,
            extras=None,
            name='BufferViewVertexND',
            target=34962
        )
        self.__gltf.buffer_views.append(self.__asobo_buffer_views['BufferViewVertexND'])

        self.__asobo_buffer_views['BufferViewIndex'] = gltf2_io.BufferView(
            buffer=gltf2_io_asobo_buffer.AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='BufferViewIndex',
            target=34963
        )
        self.__gltf.buffer_views.append(self.__asobo_buffer_views['BufferViewIndex'])

        self.__asobo_buffer_views['BufferViewVertex4Blend'] = gltf2_io.BufferView(
            buffer=gltf2_io_asobo_buffer.AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=48,
            extensions=None,
            extras=None,
            name='BufferViewVertex4Blend',
            target=34962
        )
        self.__gltf.buffer_views.append(self.__asobo_buffer_views['BufferViewVertex4Blend'])

        self.__asobo_buffer_views['BufferViewVertex1Blend'] = gltf2_io.BufferView(
            buffer=gltf2_io_asobo_buffer.AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=44,
            extensions=None,
            extras=None,
            name='BufferViewVertex1Blend',
            target=34962
        )
        self.__gltf.buffer_views.append(self.__asobo_buffer_views['BufferViewVertex1Blend'])

    @property
    def glTF(self):
        if not self.__finalized:
            raise RuntimeError("glTF requested, but buffers are not finalized yet")
        return self.__gltf

    # Add data from all asobo buffers views into main buffer
    def finalize_asobo_buffers(self): # i really really really hate this function - should find a way around this at some point. the reason it's needed is because not all hard-coded buffers are needed, and some will export without any data causing an error
        newBufferViews = []
        for x in self.__asobo_buffer_views:
            asobo_buffer_view = self.__asobo_buffer_views[x]
            binary_data = asobo_buffer_view.buffer.to_bytes()
            if binary_data == b'': # the buffer won't be needed to be exported since there is no data associated with it
                continue
            offset = self.__buffer.add(binary_data)
            asobo_buffer_view.buffer = 0
            asobo_buffer_view.byte_length = len(binary_data)
            asobo_buffer_view.byte_offset = offset
            newBufferViews.append(asobo_buffer_view.to_dict())
        old_buffers = self.__gltf.buffer_views
        if len(old_buffers) != len(newBufferViews): # we don't need to re-index if nothing changed
            data = self.__gltf.to_dict()
            for accessor in data['accessors']:
                bufferIndex = accessor['bufferView']
                bufferName = old_buffers[bufferIndex].name
                for index, buffer in enumerate(newBufferViews):
                    if bufferName == buffer:
                        data['accessors'][data['accessors'].index(accessor)]['bufferView'] = index
                        break
            data['bufferViews'] = newBufferViews
            self.__gltf = gltf2_io.gltf_from_dict(data)


    def finalize_buffer(self, output_path=None, buffer_name=None, is_glb=False):
        """Finalize the glTF and write buffers."""
        if self.__finalized:
            raise RuntimeError("Tried to finalize buffers for finalized glTF file")

        self.finalize_asobo_buffers()

        if self.__buffer.byte_length > 0:
            if is_glb:
                uri = None
            elif output_path and buffer_name:
                with open(output_path + buffer_name, 'wb') as f:
                    f.write(self.__buffer.to_bytes())
                uri = buffer_name
            else:
                uri = self.__buffer.to_embed_string()

            buffer = gltf2_io.Buffer(
                byte_length=self.__buffer.byte_length,
                extensions=None,
                extras=None,
                name=None,
                uri=uri
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
        self.__gltf.extensions_required.append('KHR_draco_mesh_compression')
        self.__gltf.extensions_used.append('KHR_draco_mesh_compression')

    def finalize_images(self):
        """
        Write all images.
        """
        output_path = self.export_settings[gltf2_blender_export_keys.TEXTURE_DIRECTORY]

        if self.__images:
            os.makedirs(output_path, exist_ok=True)

        for name, image in self.__images.items():
            dst_path = output_path + "/" + name + image.file_extension
            with open(dst_path, 'wb') as f:
                f.write(image.data)

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

    def add_original_extensions(self, requiredExtensions, usedExtensions):
        if self.__finalized:
            raise RuntimeError("Tried to add animation to finalized glTF file")

        self.__gltf.extensions_required += requiredExtensions
        self.__gltf.extensions_used += usedExtensions

    def add_asobo_bounding_box(self, extensions):
        if self.__finalized:
            raise RuntimeError("Tried to add animation to finalized glTF file")

        self.__gltf.asset.extensions = extensions

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

    @staticmethod
    def __append_unique_and_get_index(target: list, obj):
        if obj in target:
            return target.index(obj)
        else:
            index = len(target)
            target.append(obj)
            return index

    def __add_image(self, image: gltf2_io_image_data.ImageData):
        # name = image.adjusted_name()
        name = image.name
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

    def __handle_mesh(self, mesh):
        if any('BLEND' in x.extras['ASOBO_primitive']['VertexType'] for x in mesh.primitives):
            print(f'__handle_mesh skinned {mesh.name}')
            # Each primitive gets its own accessors
            for i, primitive in enumerate(mesh.primitives):
                is_blend4 = primitive.extras['ASOBO_primitive']['VertexType'] == 'BLEND4'
                buffer_view_name = 'BufferViewVertex4Blend' if is_blend4 else 'BufferViewVertex1Blend'
                blend_buffer_view = self.__asobo_buffer_views[buffer_view_name]
                expected_byte_stride = 48 if is_blend4 else 44

                the_buffer = ctypes.create_string_buffer(expected_byte_stride * primitive.attributes['POSITION'].count)

                # for attr in primitive.attributes:
                #     attr_accessor = primitive.attributes[attr]
                #     attr_accessor.buffer_view = gltf2_io_binary_data.BinaryData.from_list(attr_accessor.buffer_view, attr_accessor.component_type)
            
                offset = blend_buffer_view.buffer.byte_length
                
                if offset + 0 == 0:
                    primitive.attributes['POSITION'].byte_offset = None
                else:
                    primitive.attributes['POSITION'].byte_offset = offset + 0
                primitive.attributes['TANGENT'].byte_offset = offset + 12
                primitive.attributes['NORMAL'].byte_offset = offset + 16
                primitive.attributes['TEXCOORD_0'].byte_offset = offset + 20
                primitive.attributes['TEXCOORD_1'].byte_offset = offset + 24
                primitive.attributes['JOINTS_0'].byte_offset = offset + 28
                primitive.attributes['WEIGHTS_0'].byte_offset = offset + 36
                if is_blend4:
                    primitive.attributes['COLOR_0'].byte_offset = offset + 44
                else:
                    primitive.attributes['COLOR_0'].byte_offset = offset + 40


                # actual_byte_stride = 0
                for vidx in range(primitive.attributes['POSITION'].count):
                
                    start = vidx * expected_byte_stride
                    
                    STRUCT_POSITION.pack_into(the_buffer, start, *primitive.attributes['POSITION'].buffer_view[vidx * 3:vidx * 3 + 3])
                    STRUCT_TANGENT.pack_into(the_buffer, start + 12, *primitive.attributes['TANGENT'].buffer_view[vidx * 4:vidx * 4 + 4])
                    STRUCT_NORMAL.pack_into(the_buffer, start + 16, *primitive.attributes['NORMAL'].buffer_view[vidx * 4:vidx * 4 + 4])
                    STRUCT_UV.pack_into(the_buffer, start + 20, *primitive.attributes['TEXCOORD_0'].buffer_view[vidx * 2:vidx * 2 + 2])
                    STRUCT_UV.pack_into(the_buffer, start + 24, *primitive.attributes['TEXCOORD_1'].buffer_view[vidx * 2:vidx * 2 + 2])
                    STRUCT_JOINT.pack_into(the_buffer, start + 28, *primitive.attributes['JOINTS_0'].buffer_view[vidx * 4:vidx * 4 + 4])
                    if is_blend4:
                        STRUCT_WEIGHT4.pack_into(the_buffer, start + 36, *primitive.attributes['WEIGHTS_0'].buffer_view[vidx * 4:vidx * 4 + 4])
                        STRUCT_COLOR_BLEND.pack_into(the_buffer, start + 44, *primitive.attributes['COLOR_0'].buffer_view[vidx * 4:vidx * 4 + 4])
                    else:
                        STRUCT_WEIGHT1.pack_into(the_buffer, start + 36, *primitive.attributes['WEIGHTS_0'].buffer_view[vidx * 1:vidx * 1 + 1])
                        STRUCT_COLOR_BLEND.pack_into(the_buffer, start + 40, *primitive.attributes['COLOR_0'].buffer_view[vidx * 4:vidx * 4 + 4])


                    # for attr in primitive.attributes:
                    #     attr_accessor = primitive.attributes[attr]

                    #     # elements_to_pull = self.component_nb_dict[attr_accessor.type]
                    #     # data_for_vertex = attr_accessor.buffer_view[vidx:vidx + elements_to_pull]
                    #     # binary_data = gltf2_io_binary_data.BinaryData.from_list(data_for_vertex, attr_accessor.component_type)
                    #     # offset = blend_buffer_view.buffer.append_data(binary_data, False, vidx == 0)


                    #     elements_to_pull = self.component_nb_dict[attr_accessor.type]
                    #     chunk_byte_size = gltf2_io_constants.ComponentType.get_size(attr_accessor.component_type) * elements_to_pull
                    #     start = vidx * chunk_byte_size
                    #     end = start + chunk_byte_size
                    #     data_for_vertex = attr_accessor.buffer_view.data[start:end]
                    #     offset = blend_buffer_view.buffer.append_bytes(data_for_vertex, vidx == 0)



                    #     if vidx == 0:
                    #         attr_accessor.byte_offset = offset
                    #         if attr_accessor.byte_offset == 0:
                    #             attr_accessor.byte_offset = None
                    #         # actual_byte_stride += binary_data.byte_length
                    #         actual_byte_stride += len(data_for_vertex)
                    # if vidx == 0:
                    #     assert actual_byte_stride == expected_byte_stride

                
                blend_buffer_view.buffer.append_bytes(bytes(the_buffer), False)

                for attr in primitive.attributes:
                    primitive.attributes[attr].buffer_view = self.__gltf.buffer_views.index(blend_buffer_view)
                    primitive.attributes[attr].name = f'{mesh.name}_vertices#0_{attr}'
                
                for attr in primitive.attributes:
                    primitive.attributes[attr] = self.__to_reference(primitive.attributes[attr])
                indices_accessor = primitive.indices
                binary_data = gltf2_io_binary_data.BinaryData.from_list(indices_accessor.buffer_view, indices_accessor.component_type)
                offset = self.__asobo_buffer_views['BufferViewIndex'].buffer.append_data(binary_data, True, True)
                indices_accessor.buffer_view = self.__gltf.buffer_views.index(self.__asobo_buffer_views['BufferViewIndex'])
                indices_accessor.byte_offset = offset
                if indices_accessor.byte_offset == 0:
                    indices_accessor.byte_offset = None
                indices_accessor.name = f'{mesh.name}_indices#{i}'
                primitive.indices = self.__to_reference(indices_accessor)
                primitive.material = self.__traverse(primitive.material)
                primitive.attributes = dict(sorted(primitive.attributes.items()))
        else:
            print(f'__handle_mesh unskinned {mesh.name}')
            # Accessors are shared between the primitives
            all_indices = []
            for primitive in mesh.primitives:
                all_indices.extend(primitive.indices.buffer_view)
            first_primitive = mesh.primitives[0]
            indices_accessor = first_primitive.indices
            binary_data = gltf2_io_binary_data.BinaryData.from_list(all_indices, indices_accessor.component_type)
            offset = self.__asobo_buffer_views['BufferViewIndex'].buffer.append_data(binary_data, True, True)
            indices_accessor.buffer_view = self.__gltf.buffer_views.index(self.__asobo_buffer_views['BufferViewIndex'])
            indices_accessor.byte_offset = offset
            if indices_accessor.byte_offset == 0:
                indices_accessor.byte_offset = None
            indices_accessor.count = len(all_indices)
            indices_accessor.name = f'{mesh.name}_indices#{len(mesh.primitives) - 1}'
            vertex_nd_buffer_view = self.__asobo_buffer_views['BufferViewVertexND']
            expected_byte_stride = 36

            the_buffer = ctypes.create_string_buffer(expected_byte_stride * first_primitive.attributes['POSITION'].count)

            # for attr in first_primitive.attributes:
            #     attr_accessor = first_primitive.attributes[attr]
            #     attr_accessor.buffer_view = gltf2_io_binary_data.BinaryData.from_list(attr_accessor.buffer_view, attr_accessor.component_type)
            
            offset = vertex_nd_buffer_view.buffer.byte_length
            
            if offset + 0 == 0:
                first_primitive.attributes['POSITION'].byte_offset = None
            else:
                first_primitive.attributes['POSITION'].byte_offset = offset + 0
            first_primitive.attributes['TANGENT'].byte_offset = offset + 12
            first_primitive.attributes['NORMAL'].byte_offset = offset + 16
            first_primitive.attributes['TEXCOORD_0'].byte_offset = offset + 20
            first_primitive.attributes['TEXCOORD_1'].byte_offset = offset + 24
            first_primitive.attributes['COLOR_0'].byte_offset = offset + 28

            # actual_byte_stride = 0
            for vidx in range(first_primitive.attributes['POSITION'].count):
                
                start = vidx * expected_byte_stride
                
                STRUCT_POSITION.pack_into(the_buffer, start, *first_primitive.attributes['POSITION'].buffer_view[vidx * 3:vidx * 3 + 3])
                STRUCT_TANGENT.pack_into(the_buffer, start + 12, *first_primitive.attributes['TANGENT'].buffer_view[vidx * 4:vidx * 4 + 4])
                STRUCT_NORMAL.pack_into(the_buffer, start + 16, *first_primitive.attributes['NORMAL'].buffer_view[vidx * 4:vidx * 4 + 4])
                STRUCT_UV.pack_into(the_buffer, start + 20, *first_primitive.attributes['TEXCOORD_0'].buffer_view[vidx * 2:vidx * 2 + 2])
                STRUCT_UV.pack_into(the_buffer, start + 24, *first_primitive.attributes['TEXCOORD_1'].buffer_view[vidx * 2:vidx * 2 + 2])
                STRUCT_COLOR_VTX.pack_into(the_buffer, start + 28, *first_primitive.attributes['COLOR_0'].buffer_view[vidx * 4:vidx * 4 + 4])


                # for attr in first_primitive.attributes:
                #     attr_accessor = first_primitive.attributes[attr]

                #     # elements_to_pull = self.component_nb_dict[attr_accessor.type]
                #     data_for_vertex = attr_accessor.buffer_view[vidx:vidx + elements_to_pull]
                #     # binary_data = gltf2_io_binary_data.BinaryData.from_list(data_for_vertex, attr_accessor.component_type)
                #     # offset = vertex_nd_buffer_view.buffer.append_data(binary_data, False, vidx == 0)

                #     elements_to_pull = self.component_nb_dict[attr_accessor.type]
                #     chunk_byte_size = gltf2_io_constants.ComponentType.get_size(attr_accessor.component_type) * elements_to_pull
                #     start = vidx * chunk_byte_size
                    # end = start + chunk_byte_size
                    # data_for_vertex = attr_accessor.buffer_view.data[start:end]
                    # offset = vertex_nd_buffer_view.buffer.append_bytes(data_for_vertex, vidx == 0)

                #     if vidx == 0:
                #         attr_accessor.byte_offset = offset
                #         if attr_accessor.byte_offset == 0:
                #             attr_accessor.byte_offset = None
                #         # actual_byte_stride += binary_data.byte_length
                #         actual_byte_stride += len(data_for_vertex)
                # if vidx == 0:
                #     assert actual_byte_stride == expected_byte_stride
            
            vertex_nd_buffer_view.buffer.append_bytes(bytes(the_buffer), False)

            for attr in first_primitive.attributes:
                first_primitive.attributes[attr].buffer_view = self.__gltf.buffer_views.index(vertex_nd_buffer_view)
                first_primitive.attributes[attr].name = f'{mesh.name}_vertices#0_{attr}'

            total_asobo_primitive_count = 0
            for pidx, primitive in enumerate(mesh.primitives):
                for attr in primitive.attributes:
                    primitive.attributes[attr] = self.__to_reference(first_primitive.attributes[attr])
                primitive.indices = self.__to_reference(indices_accessor)
                primitive.material = self.__traverse(primitive.material)
                if pidx > 0:
                    primitive.extras['ASOBO_primitive']['StartIndex'] = total_asobo_primitive_count * 3
                total_asobo_primitive_count += primitive.extras['ASOBO_primitive']['PrimitiveCount']
                primitive.attributes = dict(sorted(primitive.attributes.items()))
        idx = self.__to_reference(mesh)
        return idx
    
    def __handle_anim_sampler(self, input_or_output):
        if input_or_output.type == 'SCALAR':
            animation_x_buffer_view = self.__asobo_buffer_views['bufferViewAnimationFloatScalar']
        elif input_or_output.type == 'VEC3':
            animation_x_buffer_view = self.__asobo_buffer_views['bufferViewAnimationFloatVec3']
        elif input_or_output.type == 'VEC4':
            animation_x_buffer_view = self.__asobo_buffer_views['bufferViewAnimationFloatVec4']
        else:
            assert False
        if type(input_or_output.buffer_view) != int:
            binary_data = input_or_output.buffer_view
            input_or_output.byte_offset = animation_x_buffer_view.buffer.append_data(binary_data, True, True)
            if input_or_output.byte_offset == 0:
                input_or_output.byte_offset = None
            input_or_output.buffer_view = self.__gltf.buffer_views.index(animation_x_buffer_view)
        return self.__to_reference(input_or_output)

    def __traverse(self, node):
        """
        Recursively traverse a scene graph consisting of gltf compatible elements.

        The tree is traversed downwards until a primitive is reached. Then any ChildOfRoot property
        is stored in the according list in the glTF and replaced with a index reference in the upper level.
        """
        def __traverse_property(node):
            for member_name in [a for a in dir(node) if not a.startswith('__') and not callable(getattr(node, a))]:
                new_value = self.__traverse(getattr(node, member_name))
                setattr(node, member_name, new_value)  # usually this is the same as before

                # # TODO: maybe with extensions hooks we can find a more elegant solution
                # if member_name == "extensions" and new_value is not None:
                #     for extension_name in new_value.keys():
                #         self.__append_unique_and_get_index(self.__gltf.extensions_used, extension_name)
                #         self.__append_unique_and_get_index(self.__gltf.extensions_required, extension_name)
            return node

        if type(node) == gltf2_io.Mesh:
            if type(node.primitives[0].indices) == int:
                return self.__to_reference(node)
            else:
                return self.__handle_mesh(node)

        if type(node) == gltf2_io.Skin:
            float_mat4_buffer_view = self.__asobo_buffer_views['bufferViewFloatMat4']
            if type(node.inverse_bind_matrices) != int:
                if type(node.inverse_bind_matrices.buffer_view) != int: # this seems to work, but may be causing some other issues elsewhere. (issue was some skins had 0 as their buffer view, instead of having data)
                    binary_data = node.inverse_bind_matrices.buffer_view
                    node.inverse_bind_matrices.byte_offset = float_mat4_buffer_view.buffer.append_data(binary_data, True, True)
                    if node.inverse_bind_matrices.byte_offset == 0:
                        node.inverse_bind_matrices.byte_offset = None
                    node.inverse_bind_matrices.buffer_view = self.__gltf.buffer_views.index(float_mat4_buffer_view)
                    node.inverse_bind_matrices = self.__to_reference(node.inverse_bind_matrices)

        if type(node) == gltf2_io.Animation:
            for sampler in node.samplers:
                sampler.input = self.__handle_anim_sampler(sampler.input)
                sampler.output = self.__handle_anim_sampler(sampler.output)

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
                self.__append_unique_and_get_index(self.__gltf.extensions_required, node.name)

            # extensions that lie in the root of the glTF.
            # They need to be converted to a reference at place of occurrence
            if isinstance(node, gltf2_io_extensions.ChildOfRootExtension):
                root_extension_list = self.__get_key_path(self.__gltf.extensions, [node.name] + node.path, [])
                idx = self.__append_unique_and_get_index(root_extension_list, extension)
                return idx

            return extension

        # do nothing for any type that does not match a glTF schema (primitives)
        return node

def _path_to_uri(path):
    path = os.path.normpath(path)
    path = path.replace(os.sep, '/')
    return urllib.parse.quote(path)
