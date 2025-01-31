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

import bpy

from ..com.gltf2_blender_extras import set_extras
from .gltf2_blender_pbrMetallicRoughness import MaterialHelper, pbr_metallic_roughness
from .gltf2_blender_KHR_materials_pbrSpecularGlossiness import pbr_specular_glossiness
from .gltf2_blender_KHR_materials_unlit import unlit


class BlenderMaterial:
    """Blender Material."""

    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def create(gltf, material_idx, vertex_color):
        """Material creation."""
        pymaterial = gltf.data.materials[material_idx]

        name = pymaterial.name
        if name is None:
            name = "Material_" + str(material_idx)

        mat = bpy.data.materials.new(name)
        pymaterial.blender_material[vertex_color] = mat.name
        mat.is_import = True  # this prevents the property callbacks from running during import, since that would be pointless
        mat.msfs_material_type = BlenderMaterial.determine_msfs_material_type(
            pymaterial
        )

        set_extras(mat, pymaterial.extras)
        BlenderMaterial.set_double_sided(pymaterial, mat)
        BlenderMaterial.set_alpha_mode(pymaterial, mat)
        BlenderMaterial.set_viewport_color(pymaterial, mat, vertex_color)

        mat.use_nodes = True
        while mat.node_tree.nodes:  # clear all nodes
            mat.node_tree.nodes.remove(mat.node_tree.nodes[0])

        mh = MaterialHelper(gltf, pymaterial, mat, vertex_color)

        exts = pymaterial.extensions or {}
        if "KHR_materials_unlit" in exts:
            unlit(mh)
        elif "KHR_materials_pbrSpecularGlossiness" in exts:
            pbr_specular_glossiness(mh)
        else:
            pbr_metallic_roughness(mh)

        mat.is_import = False  # once we're done setting things we can treat this as a normal material

    @staticmethod
    def set_double_sided(pymaterial, mat):
        mat.use_backface_culling = pymaterial.double_sided != True
        if pymaterial.double_sided is not None:
            mat.msfs_double_sided = pymaterial.double_sided

    @staticmethod
    def set_alpha_mode(pymaterial, mat):
        alpha_mode = pymaterial.alpha_mode
        if alpha_mode == "BLEND":
            mat.blend_method = "BLEND"
        elif alpha_mode == "MASK":
            mat.blend_method = "CLIP"
            alpha_cutoff = pymaterial.alpha_cutoff
            alpha_cutoff = alpha_cutoff if alpha_cutoff is not None else 0.5
            mat.alpha_threshold = alpha_cutoff

        if alpha_mode is not None:
            mat.msfs_alpha_mode = alpha_mode

    @staticmethod
    def set_viewport_color(pymaterial, mat, vertex_color):
        # If there is no texture and no vertex color, use the base color as
        # the color for the Solid view.
        if vertex_color:
            return

        exts = pymaterial.extensions or {}
        if "KHR_materials_pbrSpecularGlossiness" in exts:
            # TODO
            return
        else:
            pbr = pymaterial.pbr_metallic_roughness
            if pbr is None or pbr.base_color_texture is not None:
                return
            color = pbr.base_color_factor or [1, 1, 1, 1]

        mat.diffuse_color = color
        mat.msfs_base_color_factor = color

    @staticmethod
    def determine_msfs_material_type(
        pymaterial,
    ):  # It appears that sometimes a material can have multiple material extensions. This shouldn't be an issue, but should be investigated in the future
        extras = pymaterial.extras
        extensions = pymaterial.extensions
        material_type = "msfs_standard"
        if extras is not None:
            if "ASOBO_material_code" in extras:
                material_code = pymaterial.extras["ASOBO_material_code"]
                if material_code == "Windshield":
                    material_type = "msfs_windshield"
                elif material_code == "Porthole":
                    material_type = "msfs_porthole"
                elif material_code == "GeoDecalFrosted":
                    material_type = "msfs_geo_decal"
                else:
                    raise Exception("Unknown ASOBO_material_code")
        if extensions is not None:
            if "ASOBO_material_anisotropic" in extensions:
                material_type = "msfs_anisotropic"
            elif "ASOBO_material_SSS" in extensions:
                material_type = "msfs_sss"
            elif (
                "ASOBO_material_glass" in extensions
                or "ASOBO_material_kitty_glass" in extensions
            ):  # glass has two material types
                material_type = "msfs_glass"
            elif "ASOBO_material_blend_gbuffer" in extensions:
                material_type = "msfs_decal"
            elif "ASOBO_material_clear_coat" in extensions:
                material_type = "msfs_clearcoat"
            elif "ASOBO_material_environment_occluder" in extensions:
                material_type = "msfs_env_occluder"
            elif "ASOBO_material_fake_terrain" in extensions:
                material_type = "msfs_fake_terrain"
            elif "ASOBO_material_fresnel_fade" in extensions:
                material_type = "msfs_fresnel"
            elif "ASOBO_material_parallax_window" in extensions:
                material_type = "msfs_parallax"
            elif "ASOBO_material_invisible" in extensions:
                material_type = "msfs_invisible"

        return material_type
