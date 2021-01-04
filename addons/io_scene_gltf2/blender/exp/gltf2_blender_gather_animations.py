# Copyright 2020 The glTF-Blender-IO authors.
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

import array
import math
import typing

import bpy
from mathutils import Matrix, Vector, Quaternion

from io_scene_gltf2.io.com import gltf2_io
from io_scene_gltf2.io.com import gltf2_io_constants
from io_scene_gltf2.io.exp import gltf2_io_binary_data
from io_scene_gltf2.blender.exp import gltf2_blender_export_keys
from io_scene_gltf2.io.com.gltf2_io_debug import print_console
from ..com.gltf2_blender_extras import generate_extras


def gather_animations(scene, export_settings):
    nodes = __get_blender_nodes(scene)
    pre_anims = __gather_pre_anims(nodes)
    if not pre_anims:
        return []

    animations = []

    orig_frame = None
    orig_subframe = None
    try:
        orig_frame = bpy.context.scene.frame_current
        orig_subframe = bpy.context.scene.frame_subframe

        __prepare_nla_tracks(nodes)

        for pre_anim in pre_anims:
            anim = __gather_animation(pre_anim, nodes, export_settings)
            animations.append(anim)

    finally:
        # Put things back to how they were
        __restore_original_nla_track_state(nodes)
        if orig_subframe is not None:
            bpy.context.scene.frame_set(orig_frame, subframe=orig_subframe)

    return animations


def __gather_animation(pre_anim, nodes, export_settings):
    anim_name, (frame_start, frame_end) = pre_anim
    print(f'exporting animation track {anim_name}')

    # Star all the tracks named anim_name. Objects without an anim_name
    # track are considered unanimated. Star the empty temp track for those.
    anim_nodes = []
    for node in nodes:
        if node.__blender_data[0] != 'OBJECT' and node.__blender_data[0] != 'BONE':
            continue
        ob = node.__blender_data[1]
        if not ob.animation_data:
            continue
        for track in ob.animation_data.nla_tracks:
            if track.name == anim_name:
                track.is_solo = True
                if ob.type == 'ARMATURE' and node.__blender_data[0] == 'BONE':
                    # only append bones that are animated in current anim
                    actions = __get_blender_actions(ob)
                    for action in actions:
                        if action[1] == anim_name:
                            for fcurve in action[0].fcurves:
                                bone_path = fcurve.data_path.rpartition('.')[0]
                                bone = ob.path_resolve(bone_path)
                                if node.name == bone.name:
                                    if node not in anim_nodes:
                                        anim_nodes.append(node)
                else:
                    anim_nodes.append(node)
                break
        else:
            if node.__blender_data[0] == 'OBJECT':
                node.__temp_nla_track.is_solo = True

    f_start = math.floor(frame_start)
    f_end = math.ceil(frame_end) + 1
    f_step = export_settings['gltf_frame_step']

    # Stores TRS values for each node at each frame
    data = {}
    data['translation'] = [[] for _node in nodes]
    data['rotation'] = [[] for _node in nodes]
    data['scale'] = [[] for _node in nodes]

    for f in range(f_start, f_end, f_step):
        bpy.context.scene.frame_set(f)
        for i, node in enumerate(anim_nodes):
            if node.__blender_data[0] == 'OBJECT':
                t, r, s = __get_gltf_trs_from_object(node.__blender_data[1], export_settings)
            elif node.__blender_data[0] == 'BONE':
                arma_ob = node.__blender_data[1]
                pbone = arma_ob.pose.bones[node.__blender_data[2]]
                t, r, s = __get_gltf_trs_from_bone(pbone, export_settings)
            else:
                assert False
            data['translation'][i].append(t)
            data['rotation'][i].append(r)
            data['scale'][i].append(s)

    # Put it all together to get the glTF animation

    channels = []
    samplers = []

    input_accessor = __get_keyframe_accessor(f_start, f_end, f_step)

    for i, node in enumerate(anim_nodes):
        # Get paths used in the NLA track
        actions = __get_blender_actions(node.__blender_data[1])
        paths = []

        pathTypes = {
            'delta_location': 'translation',
            'delta_rotation_euler': 'rotation',
            'location': 'translation',
            'rotation_axis_angle': 'rotation',
            'rotation_euler': 'rotation',
            'rotation_quaternion': 'rotation',
            'scale': 'scale'
        }

        for action in actions:
            if action[1] == anim_name:
                for fcurve in action[0].fcurves:
                    data_path = fcurve.data_path
                    if node.__blender_data[0] == 'OBJECT':
                        paths.append(pathTypes.get(data_path))
                    else: # for armatures
                        paths.append(pathTypes.get(data_path.rpartition('.')[2]))
                        
        for path in ['translation', 'rotation', 'scale']:
            if path in paths:
                sampler = gltf2_io.AnimationSampler(
                    input=input_accessor,
                    output=__encode_output_accessor(data[path][i]),
                    interpolation=None,  # LINEAR
                    extensions=None,
                    extras=None,
                )
                samplers.append(sampler)
                channel = gltf2_io.AnimationChannel(
                    sampler=len(samplers) - 1,
                    target=gltf2_io.AnimationChannelTarget(
                        node=node,
                        path=path,
                        extensions=None,
                        extras=None,
                    ),
                    extensions=None,
                    extras=None,
                )
                channels.append(channel)

    animation = gltf2_io.Animation(
        name=anim_name,
        channels=channels,
        samplers=samplers,
        extensions=None,
        extras=None,
    )

    return animation


def __get_gltf_trs_from_object(ob, export_settings):
    from io_scene_gltf2.blender.exp import gltf2_blender_gather_nodes
    t, r, s = gltf2_blender_gather_nodes.__gather_trans_rot_scale(ob, export_settings)
    if t is None: t = [0, 0, 0]
    if r is None: r = [0, 0, 0, 1]
    if s is None: s = [1, 1, 1]
    return t, r, s


def __get_gltf_trs_from_bone(pbone, export_settings):
    if pbone.parent is None:
        m = pbone.matrix
    else:
        m = pbone.parent.matrix.inverted() @ pbone.matrix
    t, r, s = m.decompose()

    from . import gltf2_blender_gather_nodes
    trans = gltf2_blender_gather_nodes.__convert_swizzle_location(t, export_settings)
    rot = gltf2_blender_gather_nodes.__convert_swizzle_rotation(r, export_settings)
    sca = gltf2_blender_gather_nodes.__convert_swizzle_scale(s, export_settings)

    t, r, s = (None, None, None)
    if trans[0] != 0.0 or trans[1] != 0.0 or trans[2] != 0.0:
        t = [trans[0], trans[1], trans[2]]
    if rot[0] != 1.0 or rot[1] != 0.0 or rot[2] != 0.0 or rot[3] != 0.0:
        r = [rot[1], rot[2], rot[3], rot[0]]
    if sca[0] != 1.0 or sca[1] != 1.0 or sca[2] != 1.0:
        s = [sca[0], sca[1], sca[2]]

    if t is None: t = [0, 0, 0]
    if r is None: r = [0, 0, 0, 1]
    if s is None: s = [1, 1, 1]
    return t, r, s


def __get_blender_nodes(scene):
    # Get a list of all nodes that came from Blender objects or bones. These
    # have a __blender_data field that records what they came from.
    nodes = []

    def visit(node):
        nonlocal nodes
        if hasattr(node, '__blender_data'):
            nodes.append(node)
        for child in node.children:
            visit(child)

    for node in scene.nodes:
        visit(node)

    return nodes


def __gather_pre_anims(nodes):
    # Scan over all nodes looking for NLA tracks and gathering
    # pre-animations. A pre-animation is the data we need to gather an
    # animation. It a pair that tells us the animation name (NLA track
    # name), and the frame range.
    pre_anims = {}

    for node in nodes:
        if node.__blender_data[0] != 'OBJECT' and node.__blender_data[0] != 'BONE':
            continue
        ob = node.__blender_data[1]
        if not ob.animation_data:
            continue
        for track in ob.animation_data.nla_tracks:
            frame_start, frame_end = __get_frame_range_for_nla_track(track)
            if track.name not in pre_anims:
                pre_anims[track.name] = (frame_start, frame_end)
            else:
                f1, f2 = pre_anims[track.name]
                pre_anims[track.name] = (min(f1, frame_start), max(f2, frame_end))

    return list(pre_anims.items())


def __prepare_nla_tracks(nodes):
    # Preliminary pass to get ready for gathering animations. Records the
    # original starred track so it can be restored after we're done. Also
    # create empty temp tracks (we star these to make an object
    # "unanimated").
    for node in nodes:
        if node.__blender_data[0] != 'OBJECT' and node.__blender_data[0] != 'BONE':
            continue
        ob = node.__blender_data[1]
        if not ob.animation_data:
            continue

        node.__original_use_nla = ob.animation_data.use_nla
        ob.animation_data.use_nla = True

        node.__temp_nla_track = ob.animation_data.nla_tracks.new()

        for track in ob.animation_data.nla_tracks:
            if track.is_solo:
                node.__original_solo_track = track
                break
        else:
            node.__original_solo_track = None


def __restore_original_nla_track_state(nodes):
    # Undoes the NLA track changes __prepare_nodes did.
    for node in nodes:
        if node.__blender_data[0] != 'OBJECT' and node.__blender_data[0] != 'BONE':
            continue
        ob = node.__blender_data[1]
        if not ob.animation_data:
            continue

        # Restore original use_nla
        if hasattr(node, '__original_use_nla'):
            ob.animation_data.use_nla = node.__original_use_nla

        # Restore original starred track
        if hasattr(node, '__original_solo_track'):
            if node.__original_solo_track is None:
                # Unstar tracks
                ob.animation_data.nla_tracks[0].is_solo = True
                ob.animation_data.nla_tracks[0].is_solo = False
            else:
                node.__original_solo_track.is_solo = True

        # Delete the temp track
        if hasattr(node, '__temp_nla_track'):
            ob.animation_data.nla_tracks.remove(node.__temp_nla_track)


def __get_frame_range_for_nla_track(track):
    frame_start = min(strip.frame_start for strip in track.strips)
    frame_end = max(strip.frame_end for strip in track.strips)
    return frame_start, frame_end


def __get_keyframe_accessor(frame_start, frame_end, frame_step):
    # Gets an accessor for a range of keyframes. Used for sampler.input.
    fps = bpy.context.scene.render.fps
    keyframes = [frame / fps for frame in range(frame_start, frame_end, frame_step)]
    keyframe_data = array.array('f', keyframes).tobytes()
    return gltf2_io.Accessor(
        buffer_view=gltf2_io_binary_data.BinaryData(keyframe_data),
        component_type=gltf2_io_constants.ComponentType.Float,
        type=gltf2_io_constants.DataType.Scalar,
        count=len(keyframes),
        min=[keyframes[0]],
        max=[keyframes[-1]],
        byte_offset=None,
        extensions=None,
        extras=None,
        name=None,
        normalized=None,
        sparse=None,
    )


def __encode_output_accessor(values):
    # Encodes a list of T, R, or S (Vector/Quaternion) values to an accessor.
    vals = [x for val in values for x in val]
    vals_data = array.array('f', vals).tobytes()
    return gltf2_io.Accessor(
        buffer_view=gltf2_io_binary_data.BinaryData(vals_data),
        component_type=gltf2_io_constants.ComponentType.Float,
        type=gltf2_io_constants.DataType.vec_type_from_num(len(values[0])),
        count=len(values),
        min=None,
        max=None,
        byte_offset=None,
        extensions=None,
        extras=None,
        name=None,
        normalized=None,
        sparse=None,
    )

def __get_blender_actions(blender_object: bpy.types.Object,
                          ) -> typing.List[typing.Tuple[bpy.types.Action, str, str]]:
    # Gets bones/objects used in a certain action. Useful for filtering out bones in an animation that aren't needed
    blender_actions = []
    blender_tracks = {}
    action_on_type = {}

    if blender_object.animation_data is not None:
        # Collect active action.
        if blender_object.animation_data.action is not None:
            blender_actions.append(blender_object.animation_data.action)
            blender_tracks[blender_object.animation_data.action.name] = None
            action_on_type[blender_object.animation_data.action.name] = 'OBJECT'

        # Collect associated strips from NLA tracks.
        for track in blender_object.animation_data.nla_tracks:
            # Multi-strip tracks do not export correctly yet (they need to be baked),
            # so skip them for now and only write single-strip tracks.
            non_muted_strips = [strip for strip in track.strips if strip.action is not None and strip.mute is False]
            if track.strips is None or len(non_muted_strips) != 1:
                continue
            for strip in non_muted_strips:
                blender_actions.append(strip.action)
                blender_tracks[strip.action.name] = track.name # Always set after possible active action -> None will be overwrite
                action_on_type[strip.action.name] = 'OBJECT'

    # Remove duplicate actions.
    blender_actions = list(set(blender_actions))
    # sort animations alphabetically (case insensitive) so they have a defined order and match Blender's Action list
    blender_actions.sort(key = lambda a: a.name.lower())

    return [(blender_action, blender_tracks[blender_action.name], action_on_type[blender_action.name]) for blender_action in blender_actions]