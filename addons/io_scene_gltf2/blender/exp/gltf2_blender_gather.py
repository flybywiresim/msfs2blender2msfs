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

from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.io.com.gltf2_io_debug import print_console
from io_scene_gltf2.blender.exp import gltf2_blender_gather_joints
from io_scene_gltf2.blender.exp import gltf2_blender_gather_nodes
from io_scene_gltf2.blender.exp import gltf2_blender_gather_animations
from io_scene_gltf2.blender.exp.gltf2_blender_gather_cache import cached
from ..com.gltf2_blender_extras import generate_extras
from io_scene_gltf2.blender.exp import gltf2_blender_export_keys
from io_scene_gltf2.io.exp.gltf2_io_user_extensions import export_user_extensions


def gather_gltf2(export_settings):
    """
    Gather glTF properties from the current state of blender.

    :return: list of scene graphs to be added to the glTF export
    """
    scenes = []
    animations = []  # unfortunately animations in gltf2 are just as 'root' as scenes.
    active_scene = None
    for blender_scene in bpy.data.scenes:
        scenes.append(__gather_scene(blender_scene, export_settings))
        if export_settings[gltf2_blender_export_keys.ANIMATIONS]:
            #animations += __gather_animations(blender_scene, export_settings)
            animations += __gather_animations(blender_scene, scenes[-1], export_settings)
        if bpy.context.scene.name == blender_scene.name:
            active_scene = len(scenes) -1
    return active_scene, scenes, animations


@cached
def __gather_scene(blender_scene, export_settings):
    scene = gltf2_io.Scene(
        extensions=None,
        extras=__gather_extras(blender_scene, export_settings),
        name=None,
        nodes=[]
    )
    armature = None
    for _blender_object in [obj for obj in blender_scene.objects if obj.proxy is None]:
        # set root armature - possibly could refactor
        if _blender_object.type == "ARMATURE": # set the armature as well as extract the root bone from the skeleton
            armature = _blender_object
            blender_object = _blender_object.proxy if _blender_object.proxy else _blender_object
            for bone in blender_object.pose.bones: # sometimes there can be more than one bone at root level
                if bone.parent is None:
                    scene.nodes.append(gltf2_blender_gather_joints.gather_joint(blender_object, bone, export_settings))
            continue
        if _blender_object.parent is None or armature is None: # skip if the object is not a child or if the armature isn't set
            continue
        if _blender_object.parent.parent is None and _blender_object.type == "MESH": # add skinned meshes and meshes with a parent bone to the scene
            blender_object = _blender_object.proxy if _blender_object.proxy else _blender_object
            modifiers = {m.type: m for m in blender_object.modifiers}
            if ("ARMATURE" not in modifiers or modifiers["ARMATURE"].object is None) and not blender_object.parent_bone == "": # for some reason the value for no parent bone is an empty string instead of None
                continue
            node = gltf2_blender_gather_nodes.gather_node(
                blender_object,
                blender_object.library.name if blender_object.library else None,
                blender_scene, None, export_settings)
            if node is not None:
                scene.nodes.append(node)

    export_user_extensions('gather_scene_hook', export_settings, scene, blender_scene)

    return scene


def __gather_animations(blender_scene, anim_scene, export_settings):
    for _blender_object in blender_scene.objects:

        blender_object = _blender_object.proxy if _blender_object.proxy else _blender_object

        # First check if this object is exported or not. Do not export animation of not exported object
        obj_node = gltf2_blender_gather_nodes.gather_node(blender_object,
            blender_object.library.name if blender_object.library else None,
            blender_scene, None, export_settings)

    animations = gltf2_blender_gather_animations.gather_animations(anim_scene, export_settings)
    return animations


def __gather_extras(blender_object, export_settings):
    if export_settings[gltf2_blender_export_keys.EXTRAS]:
        return generate_extras(blender_object)
    return None
