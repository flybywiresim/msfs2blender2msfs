# Copyright 2021 FlyByWire Simulations.
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

import base64
import struct
import numpy as np
from copy import deepcopy

from io_scene_gltf2_msfs.io.com import gltf2_io
from io_scene_gltf2_msfs.io.com import gltf2_io_constants
from io_scene_gltf2_msfs.io.exp import gltf2_io_binary_data

STRUCT_POSITION = struct.Struct('fff')
STRUCT_TANGENT = struct.Struct('bbbb')
STRUCT_NORMAL = struct.Struct('bbbb')
STRUCT_UV = struct.Struct('ee')
STRUCT_JOINT = struct.Struct('HHHH')
STRUCT_WEIGHT1 = struct.Struct('f')
STRUCT_WEIGHT4 = struct.Struct('HHHH')
STRUCT_COLOR_VTX = struct.Struct('HHHH')
STRUCT_COLOR_BLEND = struct.Struct('bbbb')

SPLIT_INDEX = 65530 # Must be a multiple of 3, and not be greater than 65535.  We use 65530 instead of 65535 as that seems to be the max index the sim uses

class AsoboBuffer:
    def __init__(self, buffer_index=0):
        self.__data = b''
        self.__buffer_index = buffer_index

    def append_data(self, binary_data: gltf2_io_binary_data.BinaryData, check_padding=False, calculate_offset=False) -> gltf2_io.BufferView:
        """Add binary data to the buffer. Return a glTF BufferView."""
        offset = None
        if calculate_offset:
            offset = len(self.__data)

        self.__data += binary_data.data

        # offsets should be a multiple of 4 --> therefore add padding if necessary
        if check_padding:
            padding = (4 - (binary_data.byte_length % 4)) % 4
            if padding != 0:
                self.__data += b'\x00' * padding

        return offset

    def append_bytes(self, binary_data: bytes, calculate_offset=False) -> gltf2_io.BufferView:
        """Add binary data to the buffer. Return a glTF BufferView."""
        offset = None
        if calculate_offset:
            offset = len(self.__data)

        self.__data += binary_data

        return offset

    @property
    def byte_length(self):
        return len(self.__data)

    def to_bytes(self):
        return self.__data

    def to_embed_string(self):
        return 'data:application/octet-stream;base64,' + base64.b64encode(self.__data).decode('ascii')

    def clear(self):
        self.__data = b''

class AsoboBufferViews():

    def __init__(self):
        # These are the 8 buffer views that Asobo optimized meshes use
        self.bufferViewFloatMat4 = gltf2_io.BufferView(
            buffer=AsoboBuffer(),
            byte_length=0,
            byte_offset=None,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='bufferViewFloatMat4',
            target=None
        )

        self.bufferViewAnimationFloatScalar = gltf2_io.BufferView(
            buffer=AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='bufferViewAnimationFloatScalar',
            target=None
        )

        self.bufferViewAnimationFloatVec3 = gltf2_io.BufferView(
            buffer=AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='bufferViewAnimationFloatVec3',
            target=None
        )

        self.bufferViewAnimationFloatVec4 = gltf2_io.BufferView(
            buffer=AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='bufferViewAnimationFloatVec4',
            target=None
        )

        self.BufferViewVertexND = gltf2_io.BufferView(
            buffer=AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=36,
            extensions=None,
            extras=None,
            name='BufferViewVertexND',
            target=34962
        )

        self.BufferViewIndex = gltf2_io.BufferView(
            buffer=AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=None,
            extensions=None,
            extras=None,
            name='BufferViewIndex',
            target=34963
        )

        self.BufferViewVertex4Blend = gltf2_io.BufferView(
            buffer=AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=48,
            extensions=None,
            extras=None,
            name='BufferViewVertex4Blend',
            target=34962
        )

        self.BufferViewVertex1Blend = gltf2_io.BufferView(
            buffer=AsoboBuffer(),
            byte_length=0,
            byte_offset=0,
            byte_stride=44,
            extensions=None,
            extras=None,
            name='BufferViewVertex1Blend',
            target=34962
        )

        self.BufferViews = []

        self.Meshes = [] # Keep track of the meshes we have already handled (we need this since meshes can be shared across objects, and we don't want to handle a mesh twice)

    def traverse_scenes(self, scenes):
        for scene in scenes:
            for node in scene.nodes:
                self.__traverse_node(node, lambda node: self.__handle_node(node))

    
    def __traverse_node(self, node, f):
        f(node)
        if not (node.children is None):
            for child in node.children:
                self.__traverse_node(child, f)

    def __handle_node(self, node):
        if node.mesh is not None:
            if node.mesh not in self.Meshes:
                self.Meshes.append(node.mesh)
                is_skinned_mesh = any('BLEND' in primitive.extras['ASOBO_primitive']['VertexType'] for primitive in node.mesh.primitives)
                self.__handle_mesh(node.mesh, is_skinned_mesh)

    @staticmethod
    def get_primitive_attributes_count(primitive):
        attributes_count = [primitive.attributes[attribute].count for attribute in primitive.attributes] # Get a list of all attribute's count
        if all(x==attributes_count[0] for x in attributes_count): # Make sure they are all the same
            return attributes_count[0]
        else:
            raise RuntimeError('Not all attributes of primitive have the same count')

    @staticmethod
    def split_indices(indices, base_vertex_index):
        """
        Splits an array of indices so that no value is greater than SPLIT_INDEX. To do this, we group indices that are close to each other and calculate
        a base_vertex_index.

        :param indices: a numpy array
        :param base_vertex_index: an int or None
        :return (split_indices, base_vertex_index): split_indices is a list of dictionaries in the following format: ['indices': [], 'base_vertex_index': int or None]. base_vertex_index is
        our final base vertex index, and is the greatest out of those in split_indices.
        """
        # Group the indices into groups of 3
        indices_groups = indices.reshape(-1, 3)

        split_indices = []
        while len(indices_groups) > 0: # This continues until every index group is properly split
            # Subtract min_index from indices_groups
            min_indices_groups = np.amin(indices_groups)

            indices_groups -= min_indices_groups

            # Add min index to base_vertex_index
            if base_vertex_index is None:
                if min_indices_groups != 0:
                    base_vertex_index = min_indices_groups
            else:
                base_vertex_index += min_indices_groups

            # Check if we need to duplicate any indices
            mask = np.amax(indices_groups, axis=1) - np.amin(indices_groups, axis=1) > SPLIT_INDEX
            overflow_indices = indices_groups[mask]
            if len(overflow_indices) > 0:
                if np.amin(overflow_indices) == 0:
                    raise RuntimeError('Index group cannot be split. You can try dividing the mesh into multiple meshes. This will be fixed in a future version of the exporter.')
            
            # Create a boolean mask to select indices that can fit into our current "chunk"
            mask = np.amax(indices_groups, axis=1) <= SPLIT_INDEX
            indices_chunk = indices_groups[mask].flatten() # We want to flatten this since we paired the indices into groups of 3

            # Remove the indices that we used by setting indices_groups to the opposite of our boolean mask
            indices_groups = indices_groups[~mask]

            if len(indices_chunk) > 0:
                split_indices.append({'indices': indices_chunk, 'base_vertex_index': base_vertex_index})

        return split_indices, base_vertex_index


    @staticmethod
    def split_primitive(primitive, is_skinned):
        """
        Takes a primitive and splits it into multiple primitives. This is required if our primitive has an index that is greater than SPLIT_INDEX. This is needed
        as Microsoft Flight Simulator only supports 16-bit ints for indices.

        :param primitive: a glTF primitive
        :param is_skinned: if the mesh is skinned
        :return (split_primitives, base_vertex_index): split_primitives is a list of glTF primitives, and base_vertex_index is our greatest base vertex index out of
        all the split primitives.
        """
        # The first step in splitting the primitive is arranging the indices in numerical order, as they are gathered in an arbitrary order
        indices = primitive.indices.buffer_view

        split_indices, base_vertex_index = AsoboBufferViews.split_indices(indices, primitive.extras['ASOBO_primitive']['BaseVertexIndex'])

        # Now we split this new primitive that we've made
        split_primitives = []

        for i, v in enumerate(split_indices):
            # v is a dictionary with 2 keys - indices and base_vertex_index

            if max(v['indices']) > SPLIT_INDEX: # There is a chance that our indices may not have been completely split. If that's the case, raise an error
               raise RuntimeError("Couldn't split indices for primitive")

            # Create the indices accessor and the primitive
            indices_accessor = gltf2_io.Accessor(
                buffer_view=np.array(v['indices'], dtype=np.uint16), # Use a uint16 array, as that is what the sim supports. None of our indices are greater than 65535, so we are safe doing this
                byte_offset=None,
                component_type=gltf2_io_constants.ComponentType.UnsignedShort,
                count=len(v['indices']),
                extensions=None,
                extras=None,
                max=None,
                min=None,
                name=None,
                normalized=None,
                sparse=None,
                type=gltf2_io_constants.DataType.Scalar
            )

            # Create a new primitive using our indices_accessor. We need to create a deepcopy of the attributes and extras since we will change some of the values. If we don't create a deepcopy, our changes will reflect across EVERY new primitive.
            split_primitive = gltf2_io.MeshPrimitive(
                attributes=deepcopy(primitive.attributes),
                extensions=None,
                extras=deepcopy(primitive.extras),
                indices=indices_accessor,
                material=primitive.material,
                mode=primitive.mode,
                targets=primitive.targets
            )

            # On unskinned meshes, the accessors are shared between all primitives. Since every primitive contains the same data, we only need to use the first primitive's data. If we don't remove the data from the other primitives, we will get indices in the wrong places.
            if i > 0 and not is_skinned:
                for attribute in split_primitive.attributes:
                    split_primitive.attributes[attribute].buffer_view = None
                    split_primitive.attributes[attribute].count = None

            if v['base_vertex_index'] is not None: # It is important to note that v['base_vertex_index'] is different from the variable base_vertex_index. v['base_vertex_index'] is the base vertex index at our current split, while base_vertex_index is for the final split.
                split_primitive.extras['ASOBO_primitive']['BaseVertexIndex'] = int(v['base_vertex_index'])

            split_primitive.extras['ASOBO_primitive']['PrimitiveCount'] = indices_accessor.count // 3

            split_primitives.append(split_primitive)

        return split_primitives, base_vertex_index

    def __handle_mesh(self, mesh, is_skinned):
        # Before processing the mesh data, we check if we need to split any primitives
        max_index = 0
        base_vertex_index = None
        new_primitives = []
        for primitive in mesh.primitives:
            # The first thing we do is add the previous primitive's max index to our indices. This is necessary for unskinned meshes since the indices accessor is shared.
            primitive.indices.buffer_view = primitive.indices.buffer_view.astype(int) # Convert the buffer view dtype to a python int. This prevents overflow. While we could use something like np.uint64, it's probably safer to use a python int. We later convert this to uint16
            if not is_skinned:
                primitive.indices.buffer_view += max_index
                max_index = max(primitive.indices.buffer_view) + 1

            # Subtract base vertex index from our indices
            if base_vertex_index is not None:
                primitive.indices.buffer_view -= base_vertex_index
                primitive.extras['ASOBO_primitive']['BaseVertexIndex'] = int(base_vertex_index)
                
            # Only split primitive if needed
            if max(primitive.indices.buffer_view) > SPLIT_INDEX:
                split_primitives, base_vertex_index = AsoboBufferViews.split_primitive(primitive, is_skinned)
                new_primitives.extend(split_primitives)
            else:
                new_primitives.append(primitive)

        # Finally, overwrite the mesh primitives to our new ones.
        mesh.primitives = new_primitives

        if is_skinned:
            for i, primitive in enumerate(mesh.primitives):

                #
                # Gather indices
                #
                
                indices = [] # Use a regular python list as appending is faster than using numpy

                # Reverse indices (this makes the faces render in the correct direction)
                for i in range(0, len(primitive.indices.buffer_view), 3):
                    indices.append(primitive.indices.buffer_view[i + 2])
                    indices.append(primitive.indices.buffer_view[i + 1])
                    indices.append(primitive.indices.buffer_view[i + 0])

                indices_accessor = primitive.indices

                # Set data type
                dtype = gltf2_io_constants.ComponentType.to_numpy_dtype_asobo(indices_accessor.component_type)
                indices = np.array(indices, dtype=dtype)

                binary_data = gltf2_io_binary_data.BinaryData(indices.tobytes())
                offset = self.BufferViewIndex.buffer.append_data(binary_data, check_padding=True, calculate_offset=True)
                if self.BufferViewIndex not in self.BufferViews:
                    self.BufferViews.append(self.BufferViewIndex)


                indices_accessor.buffer_view = self.BufferViews.index(self.BufferViewIndex)
                if offset != 0:
                    indices_accessor.byte_offset = offset
                indices_accessor.name = f'{mesh.name}_indices#{i}'

                #
                # Set mesh data
                #
                
                is_blend4 = primitive.extras['ASOBO_primitive']['VertexType'] == 'BLEND4'
                blend_buffer_view = self.BufferViewVertex4Blend if is_blend4 else self.BufferViewVertex1Blend
                expected_byte_stride = 48 if is_blend4 else 44

                # Get amount of elements we want to add into the buffer
                count = AsoboBufferViews.get_primitive_attributes_count(primitive)

                buffer = bytearray(expected_byte_stride * count) # could possibly cause an error? might need to multiply by 3

                # Assign offsets
                offset = blend_buffer_view.buffer.byte_length
                
                if 'POSITION' in primitive.attributes:
                    if offset != 0:
                        primitive.attributes['POSITION'].byte_offset = offset
                if 'TANGENT' in primitive.attributes:
                    primitive.attributes['TANGENT'].byte_offset = offset + 12
                if 'NORMAL' in primitive.attributes:
                    primitive.attributes['NORMAL'].byte_offset = offset + 16
                if 'TEXCOORD_0' in primitive.attributes:
                    primitive.attributes['TEXCOORD_0'].byte_offset = offset + 20
                if 'TEXCOORD_1' in primitive.attributes:
                    primitive.attributes['TEXCOORD_1'].byte_offset = offset + 24
                if 'JOINTS_0' in primitive.attributes:
                    primitive.attributes['JOINTS_0'].byte_offset = offset + 28
                if 'WEIGHTS_0' in primitive.attributes:
                    primitive.attributes['WEIGHTS_0'].byte_offset = offset + 36
                if 'COLOR_0' in primitive.attributes:
                    if is_blend4:
                        primitive.attributes['COLOR_0'].byte_offset = offset + 44
                    else:
                        primitive.attributes['COLOR_0'].byte_offset = offset + 40

                for vidx in range(count):
                    start = vidx * expected_byte_stride

                    # Pack data into buffer

                    if 'POSITION' in primitive.attributes:
                        STRUCT_POSITION.pack_into(buffer, start, *primitive.attributes['POSITION'].buffer_view[vidx])
                    if 'TANGENT' in primitive.attributes:
                        STRUCT_TANGENT.pack_into(buffer, start + 12, *primitive.attributes['TANGENT'].buffer_view[vidx])
                    if 'NORMAL' in primitive.attributes:
                        STRUCT_NORMAL.pack_into(buffer, start + 16, *primitive.attributes['NORMAL'].buffer_view[vidx])
                    if 'TEXCOORD_0' in primitive.attributes:
                        STRUCT_UV.pack_into(buffer, start + 20, *primitive.attributes['TEXCOORD_0'].buffer_view[vidx])
                    if 'TEXCOORD_1' in primitive.attributes:
                        STRUCT_UV.pack_into(buffer, start + 24, *primitive.attributes['TEXCOORD_1'].buffer_view[vidx])
                    if 'JOINTS_0' in primitive.attributes:
                        STRUCT_JOINT.pack_into(buffer, start + 28, *primitive.attributes['JOINTS_0'].buffer_view[vidx])
                    if 'WEIGHTS_0' in primitive.attributes:
                        if is_blend4:
                            STRUCT_WEIGHT4.pack_into(buffer, start + 36, *primitive.attributes['WEIGHTS_0'].buffer_view[vidx])
                        else:
                            STRUCT_WEIGHT1.pack_into(buffer, start + 36, *primitive.attributes['WEIGHTS_0'].buffer_view[vidx])
                    if 'COLOR_0' in primitive.attributes:
                        if is_blend4:
                            STRUCT_COLOR_BLEND.pack_into(buffer, start + 44, *primitive.attributes['COLOR_0'].buffer_view[vidx])
                        else:
                            STRUCT_COLOR_BLEND.pack_into(buffer, start + 40, *primitive.attributes['COLOR_0'].buffer_view[vidx])

                blend_buffer_view.buffer.append_bytes(bytes(buffer), calculate_offset=False)
                if blend_buffer_view not in self.BufferViews:
                    self.BufferViews.append(blend_buffer_view)

                # Set attribute names and  buffer view indexes
                for attribute in primitive.attributes:
                    primitive.attributes[attribute].buffer_view = self.BufferViews.index(blend_buffer_view)
                    primitive.attributes[attribute].name = f'{mesh.name}_vertices#0_{attribute}'

        else: # Mesh is not skinned

            #
            # Gather indices
            #

            all_indices = [] # Use a regular python list as appending is faster than using numpy

            # Reverse indices (this makes the faces render in the correct direction)
            for primitive in mesh.primitives:
                indices = primitive.indices.buffer_view

                for i in range(0, len(indices), 3):
                    all_indices.append(indices[i + 2])
                    all_indices.append(indices[i + 1])
                    all_indices.append(indices[i + 0])

            primitive = mesh.primitives[0] # use first primitive
            indices_accessor = primitive.indices

            # Convert to numpy array
            dtype = gltf2_io_constants.ComponentType.to_numpy_dtype_asobo(indices_accessor.component_type)
            all_indices = np.array(all_indices, dtype=dtype)

            # Set binary data and append to buffer view
            binary_data = gltf2_io_binary_data.BinaryData(all_indices.tobytes())
            offset = self.BufferViewIndex.buffer.append_data(binary_data, check_padding=True, calculate_offset=True)
            if self.BufferViewIndex not in self.BufferViews:
                self.BufferViews.append(self.BufferViewIndex)

            indices_accessor.buffer_view = self.BufferViews.index(self.BufferViewIndex)
            if offset != 0:
                indices_accessor.byte_offset = offset
            indices_accessor.count = len(all_indices)
            indices_accessor.name = f'{mesh.name}_indices#{len(mesh.primitives) - 1}'

            #
            # Share accessors between the primitives
            #

            for attribute in mesh.primitives[0].attributes:
                # Put all data into one accessor per attribute, and share across primitives
                accessor = mesh.primitives[0].attributes[attribute] # Share the first primitive's accessors
                buffer_views = []
                for primitive in mesh.primitives:
                    if attribute in primitive.attributes:
                        if primitive.attributes[attribute].buffer_view is not None:
                            buffer_views.extend(primitive.attributes[attribute].buffer_view) # Add other primitive's data into the accessor
                accessor.buffer_view = buffer_views
                accessor.count = len(buffer_views) # Recalculate the count

                if attribute == 'POSITION': # Since we've put all the data into a shared accessor, we need to also recalculate the position accessor's min and max values
                    accessor.min = list(map(float, np.amin(buffer_views, axis=0).tolist()))
                    accessor.max = list(map(float, np.amax(buffer_views, axis=0).tolist()))

                for primitive in mesh.primitives: # Set all primitives to use the shared accessor
                    primitive.attributes[attribute] = accessor
            
            #
            # Set mesh data
            #

            vertex_nd_buffer_view = self.BufferViewVertexND
            expected_byte_stride = 36

            # Get amount of elements we want to add into the buffer
            count = AsoboBufferViews.get_primitive_attributes_count(primitive)

            # Create an empty buffer with the expected size
            buffer = bytearray(expected_byte_stride * count) # could possibly cause an error? might need to multiply by 3

            # Assign offsets
            offset = vertex_nd_buffer_view.buffer.byte_length

            if 'POSITION' in primitive.attributes:
                if offset != 0:
                    primitive.attributes['POSITION'].byte_offset = offset
            if 'TANGENT' in primitive.attributes:
                primitive.attributes['TANGENT'].byte_offset = offset + 12
            if 'NORMAL' in primitive.attributes:
                primitive.attributes['NORMAL'].byte_offset = offset + 16
            if 'TEXCOORD_0' in primitive.attributes:
                primitive.attributes['TEXCOORD_0'].byte_offset = offset + 20
            if 'TEXCOORD_1' in primitive.attributes:
                primitive.attributes['TEXCOORD_1'].byte_offset = offset + 24
            if 'COLOR_0' in primitive.attributes:
                primitive.attributes['COLOR_0'].byte_offset = offset + 28

            for vidx in range(count):
                start = vidx * expected_byte_stride

                # Pack data into buffer

                if 'POSITION' in primitive.attributes:
                    STRUCT_POSITION.pack_into(buffer, start, *primitive.attributes['POSITION'].buffer_view[vidx])
                if 'TANGENT' in primitive.attributes:
                    STRUCT_TANGENT.pack_into(buffer, start + 12, *primitive.attributes['TANGENT'].buffer_view[vidx])
                if 'NORMAL' in primitive.attributes:
                    STRUCT_NORMAL.pack_into(buffer, start + 16, *primitive.attributes['NORMAL'].buffer_view[vidx])
                if 'TEXCOORD_0' in primitive.attributes:
                    STRUCT_UV.pack_into(buffer, start + 20, *primitive.attributes['TEXCOORD_0'].buffer_view[vidx])
                if 'TEXCOORD_1' in primitive.attributes:
                    STRUCT_UV.pack_into(buffer, start + 24, *primitive.attributes['TEXCOORD_1'].buffer_view[vidx])
                if 'COLOR_0' in primitive.attributes:
                    STRUCT_COLOR_VTX.pack_into(buffer, start + 28, *primitive.attributes['COLOR_0'].buffer_view[vidx])

            # Add data to the buffer view
            vertex_nd_buffer_view.buffer.append_bytes(bytes(buffer), calculate_offset=False)
            if vertex_nd_buffer_view not in self.BufferViews:
                    self.BufferViews.append(vertex_nd_buffer_view)

            # Set attribute buffer view index
            for attribute in primitive.attributes:
                primitive.attributes[attribute].buffer_view = self.BufferViews.index(vertex_nd_buffer_view)
                primitive.attributes[attribute].name = f'{mesh.name}_vertices#0_{attribute}'

            #
            # Distribute the shared accessors between all the primitives
            #

            total_asobo_primitive_count = 0
            for pidx, mesh_primitive in enumerate(mesh.primitives):
                for attribute in mesh_primitive.attributes:
                    mesh_primitive.attributes[attribute] = primitive.attributes[attribute]
                mesh_primitive.indices = indices_accessor

                # Set StartIndex
                if pidx > 0:
                    mesh_primitive.extras['ASOBO_primitive']['StartIndex'] = total_asobo_primitive_count * 3
                total_asobo_primitive_count += mesh_primitive.extras['ASOBO_primitive']['PrimitiveCount']
