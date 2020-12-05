# Copyright 2018 The glTF-Blender-IO authors.
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

from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.io.exp import gltf2_io_binary_data


class AsoboBuffer:
    def __init__(self, buffer_index=0):
        self.__data = b""
        self.__buffer_index = buffer_index

    def append_data(self, binary_data: gltf2_io_binary_data.BinaryData, check_padding, calculate_offset) -> gltf2_io.BufferView:
        """Add binary data to the buffer. Return a glTF BufferView."""
        offset = None
        if calculate_offset:
            offset = len(self.__data)

        self.__data += binary_data.data

        # offsets should be a multiple of 4 --> therefore add padding if necessary
        if check_padding:
            padding = (4 - (binary_data.byte_length % 4)) % 4
            if padding != 0:
                self.__data += b"\x00" * padding

        return offset

    def append_bytes(self, binary_data: bytes, calculate_offset) -> gltf2_io.BufferView:
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
        self.__data = b""
