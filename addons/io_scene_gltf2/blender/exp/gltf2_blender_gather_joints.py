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

import mathutils

from . import gltf2_blender_export_keys
from io_scene_gltf2.blender.exp.gltf2_blender_gather_cache import cached
from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.blender.exp import gltf2_blender_extract
from io_scene_gltf2.blender.exp import gltf2_blender_gather_skins
from io_scene_gltf2.io.exp.gltf2_io_user_extensions import export_user_extensions
from ..com.gltf2_blender_extras import generate_extras

@cached
def gather_joint(blender_object, blender_bone, export_settings):
    """
    Generate a glTF2 node from a blender bone, as joints in glTF2 are simply nodes.

    :param blender_bone: a blender PoseBone
    :param export_settings: the settings for this export
    :return: a glTF2 node (acting as a joint)
    """
    translation, rotation, scale = __gather_trans_rot_scale(blender_bone, export_settings)

    # traverse into children
    children = []

    if export_settings["gltf_def_bones"] is False:
        for bone in blender_bone.children:
            children.append(gather_joint(blender_object, bone, export_settings))
    else:
        _, children_, _ = gltf2_blender_gather_skins.get_bone_tree(None, blender_bone.id_data)
        if blender_bone.name in children_.keys():
            for bone in children_[blender_bone.name]:
                children.append(gather_joint(blender_object, blender_bone.id_data.pose.bones[bone], export_settings))

    # finally add to the joints array containing all the joints in the hierarchy
    node = gltf2_io.Node(
        camera=None,
        children=children,
        extensions=None,
        extras=__gather_extras(blender_bone, export_settings),
        matrix=None,
        mesh=None,
        name=blender_bone.name,
        rotation=rotation,
        scale=scale,
        skin=None,
        translation=translation,
        weights=None
    )
    node.__blender_data = ('BONE', blender_object, blender_bone.name)

    export_user_extensions('gather_joint_hook', export_settings, node, blender_bone)

    return node

def __gather_trans_rot_scale(blender_bone, export_settings):
    if blender_bone.parent is None:
        m = blender_bone.matrix
    else:
        m = blender_bone.parent.matrix.inverted() @ blender_bone.matrix
    t, r, s = m.decompose()

    from . import gltf2_blender_gather_nodes
    trans = gltf2_blender_gather_nodes.__convert_swizzle_location(t, export_settings)
    rot = gltf2_blender_gather_nodes.__convert_swizzle_rotation(r, export_settings)
    sca = gltf2_blender_gather_nodes.__convert_swizzle_scale(s, export_settings)

    translation, rotation, scale = (None, None, None)
    if trans[0] != 0.0 or trans[1] != 0.0 or trans[2] != 0.0:
        translation = [trans[0], trans[1], trans[2]]
    if rot[0] != 1.0 or rot[1] != 0.0 or rot[2] != 0.0 or rot[3] != 0.0:
        rotation = [rot[1], rot[2], rot[3], rot[0]]
    if sca[0] != 1.0 or sca[1] != 1.0 or sca[2] != 1.0:
        scale = [sca[0], sca[1], sca[2]]

    return translation, rotation, scale

def __gather_extras(blender_bone, export_settings):
    if export_settings['gltf_extras']:
        return generate_extras(blender_bone.bone)
    return None
