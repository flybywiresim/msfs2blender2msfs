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
import json

from ..com.gltf2_blender_extras import set_extras
from .gltf2_blender_texture import Textures


class BlenderMaterial():
    """Blender Material."""
    def __new__(cls, *args, **kwargs):
        raise RuntimeError("%s should not be instantiated" % cls)

    @staticmethod
    def createPlaceholder(gltf, material_idx, vertex_color):
        pymaterial = gltf.data.materials[material_idx]

        name = pymaterial.name
        if name is None:
            name = "Material_" + str(material_idx)

        mat = bpy.data.materials.new(name)
        pymaterial.blender_material[vertex_color] = mat.name

    @staticmethod
    def loadMaterials(gltf, mesh_idx):
        pymesh = gltf.data.meshes[mesh_idx]
        materials = []
        for prim in pymesh.primitives:
            if prim.material is not None:
                if prim.material not in materials: # sometimes the same material can be referenced multiple times in the same mesh
                    pymaterial = gltf.data.materials[prim.material]
                    BlenderMaterial.create(gltf, prim.material, None)
                    materials.append(prim.material)

    @staticmethod
    def setMaterialType(pymaterial, blender_material):
        extras = pymaterial.extras
        extensions = pymaterial.extensions
        material_type = None # possibly set default value to msfs_standard?
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
        if extensions is not None and material_type is None:
            if "ASOBO_material_anisotropic" in extensions:
                material_type = "msfs_anisotropic"
            elif "ASOBO_material_SSS" in extensions:
                material_type = "msfs_sss"
            elif "ASOBO_material_glass" in extensions or "ASOBO_material_kitty_glass" in extensions: # glass has two material types - separate these eventually
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
            else:
                material_type = "msfs_standard"
        elif material_type is None:
            material_type = "msfs_standard"
        blender_material.msfs_material_type = material_type


    @staticmethod
    def create(gltf, material_idx, vertex_color):
        """Material creation."""
        pymaterial = gltf.data.materials[material_idx]

        blender_material = bpy.data.materials[pymaterial.name]
        if blender_material.msfs_material_type == "NONE": # sometimes the same material can be referenced multiple times by different nodes, so we want to prevent unnecessary material creation if the material has already been made. checking msfs_material_type works for now as that's only set on final material creation
            # Set active material
            original_active = bpy.context.view_layer.objects.active.active_material
            bpy.context.view_layer.objects.active.active_material = blender_material

            blender_material.use_nodes = True

            BlenderMaterial.setMaterialType(pymaterial, blender_material)
            material_type = blender_material.msfs_material_type
            
            # Start with normal glTF material properties
            if pymaterial.alpha_cutoff is not None:
                blender_material.msfs_alpha_cutoff = pymaterial.alpha_cutoff
                
            if pymaterial.alpha_mode is not None:
                # aliases
                if pymaterial.alpha_mode == "MASK":
                    blender_material.msfs_blend_mode = "MASKED"
                else:
                    blender_material.msfs_blend_mode = pymaterial.alpha_mode

            if pymaterial.double_sided is not None:
                blender_material.msfs_double_sided = pymaterial.double_sided

            # Textures
            if pymaterial.normal_texture is not None:
                Textures.loadNormalTexture(gltf, pymaterial, blender_material)
                if pymaterial.normal_texture.scale is not None:
                    blender_material.msfs_normal_scale = pymaterial.normal_texture.scale

            if pymaterial.occlusion_texture is not None: # the metallic texture is the occlusion texture
                Textures.loadOcclusionTexture(gltf, pymaterial, blender_material)

            if pymaterial.emissive_texture is not None:
                Textures.loadEmissiveTexture(gltf, pymaterial, blender_material)

            if pymaterial.pbr_metallic_roughness is not None:
                Textures.loadPBRMetallicRoughness(gltf, pymaterial, blender_material)

                # load the base color factor
                if pymaterial.pbr_metallic_roughness.base_color_factor is not None:
                    blender_material.msfs_color_albedo_mix = pymaterial.pbr_metallic_roughness.base_color_factor[:-1] # remove alpha value (this is for the albedo color viewer in the ui)
                    blender_material.msfs_color_albedo_mix[0] = pymaterial.pbr_metallic_roughness.base_color_factor[0]
                    blender_material.msfs_color_albedo_mix[1] = pymaterial.pbr_metallic_roughness.base_color_factor[1]
                    blender_material.msfs_color_albedo_mix[2] = pymaterial.pbr_metallic_roughness.base_color_factor[2]
                    blender_material.msfs_color_alpha_mix = pymaterial.pbr_metallic_roughness.base_color_factor[3]
                if pymaterial.pbr_metallic_roughness.roughness_factor is not None:
                    blender_material.msfs_roughness_scale = pymaterial.pbr_metallic_roughness.roughness_factor
                if pymaterial.pbr_metallic_roughness.metallic_factor is not None:
                    blender_material.msfs_metallic_scale = pymaterial.pbr_metallic_roughness.metallic_factor

            # load the emissive factor
            if pymaterial.emissive_factor is not None:
                    blender_material.msfs_color_emissive_mix = pymaterial.emissive_factor # this is for the emissive color viewer in the ui
                    blender_material.msfs_color_emissive_mix[0] = pymaterial.emissive_factor[0]
                    blender_material.msfs_color_emissive_mix[1] = pymaterial.emissive_factor[1]
                    blender_material.msfs_color_emissive_mix[2] = pymaterial.emissive_factor[2]

            # Extensions
            if pymaterial.extensions is not None:
                if "ASOBO_material_alphamode_dither" in pymaterial.extensions: # not sure if this ever has an enabled property, but it doesn't seem like it does
                        blender_material.msfs_blend_mode = "DITHER"

                if "ASOBO_tags" in pymaterial.extensions:
                    if "Collision" in pymaterial.extensions["ASOBO_tags"]["tags"]:
                        blender_material.msfs_collision_material = True

                if "ASOBO_material_day_night_switch" in pymaterial.extensions:
                    blender_material.msfs_day_night_cycle = True

                if "ASOBO_material_draw_order" in pymaterial.extensions:
                    blender_material.msfs_draw_order = pymaterial.extensions["ASOBO_material_draw_order"]["drawOrderOffset"]

                if "ASOBO_material_shadow_options" in pymaterial.extensions:
                    blender_material.msfs_no_cast_shadow = pymaterial.extensions["ASOBO_material_shadow_options"]["noCastShadow"]

                if "ASOBO_material_UV_options" in pymaterial.extensions:
                    if "AOUseUV2" in pymaterial.extensions["ASOBO_material_UV_options"]:
                        blender_material.msfs_ao_use_uv2 = pymaterial.extensions["ASOBO_material_UV_options"]["AOUseUV2"]
                    if "clampUVX" in pymaterial.extensions["ASOBO_material_UV_options"]:
                        blender_material.msfs_uv_clamp_x = pymaterial.extensions["ASOBO_material_UV_options"]["clampUVX"]
                    if "clampUVY" in pymaterial.extensions["ASOBO_material_UV_options"]:
                        blender_material.msfs_uv_clamp_y = pymaterial.extensions["ASOBO_material_UV_options"]["clampUVY"]
                    # there is also a clamp UV Z which is quite pointless so it's not used here (and possibly not in the sim)
                
                if "ASOBO_material_detail_map" in pymaterial.extensions:
                    Textures.loadDetailMap(gltf, pymaterial, blender_material)
                    
                if "ASOBO_material_blend_gbuffer" in pymaterial.extensions:
                    Textures.loadDecalBlendFactors(gltf, pymaterial, blender_material)

                if "ASOBO_tags" in pymaterial.extensions:
                    if "Collision" in pymaterial.extensions["ASOBO_tags"]["tags"]:
                        blender_material.msfs_collision_material = True
                    if "Road" in pymaterial.extensions["ASOBO_tags"]["tags"]: # this will probably never be used, but it's still good to have it just in case
                        blender_material.msfs_road_material = True

                if pymaterial.double_sided is not None:
                    blender_material.msfs_double_sided = pymaterial.double_sided

                if pymaterial.alpha_mode is not None:
                    blender_material.msfs_blend_mode = pymaterial.alpha_mode
                    
                if pymaterial.alpha_cutoff is not None:
                    blender_material.msfs_alpha_cutoff = pymaterial.alpha_cutoff

                if material_type == "msfs_sss":
                    if "SSSColor" in pymaterial.extensions["ASOBO_material_SSS"]:
                        blender_material.msfs_color_sss[0] = pymaterial.extensions["ASOBO_material_SSS"]["SSSColor"][0]
                        blender_material.msfs_color_sss[1] = pymaterial.extensions["ASOBO_material_SSS"]["SSSColor"][1]
                        blender_material.msfs_color_sss[2] = pymaterial.extensions["ASOBO_material_SSS"]["SSSColor"][2]

                if material_type == "msfs_glass": # this seems to be only for kitty_glass
                    if "ASOBO_material_kitty_glass" in pymaterial.extensions:
                        if "glassReflectionMaskFactor" in pymaterial.extensions["ASOBO_material_kitty_glass"]:
                            blender_material.msfs_glass_reflection_mask_factor = pymaterial.extensions["ASOBO_material_kitty_glass"]["glassReflectionMaskFactor"]
                        if "glassDeformationFactor" in pymaterial.extensions["ASOBO_material_kitty_glass"]:
                            blender_material.msfs_glass_deformation_factor = pymaterial.extensions["ASOBO_material_kitty_glass"]["glassDeformationFactor"]
                
                if material_type == "msfs_clearcoat": # this won't work for hair materials, but since that isn't supported it's not an issue. also don't know if this is fully supported
                    if "dirtTexture" in pymaterial.extensions["ASOBO_material_clear_coat"]:
                        Textues.loadClearcoatTexture(gltf, pymaterial, blender_material)
                
                if material_type == "msfs_fresnel":
                    if "fresnelFactor" in pymaterial.extensions["ASOBO_material_fresnel_fade"]:
                        blender_material.msfs_fresnel_factor = pymaterial.extensions["ASOBO_material_fresnel_fade"]["fresnelFactor"]
                    if "fresnelOpacityOffset" in pymaterial.extensions["ASOBO_material_fresnel_fade"]:
                        blender_material.msfs_fresnel_opacity_bias = pymaterial.extensions["ASOBO_material_fresnel_fade"]["fresnelOpacityOffset"]
                
                if material_type == "msfs_parallax":
                    if "parallaxScale" in pymaterial.extensions["ASOBO_material_parallax_window"]:
                        blender_material.parallax_scale = pymaterial.extensions["ASOBO_material_parallax_window"]["parallaxScale"]
                    if "roomSizeXScale" in pymaterial.extensions["ASOBO_material_parallax_window"]:
                        blender_material.parallax_room_size_x = pymaterial.extensions["ASOBO_material_parallax_window"]["roomSizeXScale"]
                    if "roomSizeYScale" in pymaterial.extensions["ASOBO_material_parallax_window"]:
                        blender_material.parallax_room_size_y = pymaterial.extensions["ASOBO_material_parallax_window"]["roomSizeYScale"]
                    if "roomNumberXY" in pymaterial.extensions["ASOBO_material_parallax_window"]:
                        blender_material.parallax_room_number = pymaterial.extensions["ASOBO_material_parallax_window"]["roomNumberXY"]
                    if "corridor" in pymaterial.extensions["ASOBO_material_parallax_window"]:
                        blender_material.parallax_room_corridor = pymaterial.extensions["ASOBO_material_parallax_window"]["corridor"]
                    if "behindWindowMapTexture" in pymaterial.extensions["ASOBO_material_parallax_window"]:
                        Textures.loadBehindWindowMapTexture(gltf, pymaterial, blender_material)

            # Restore original active material
            bpy.context.view_layer.objects.active.active_material = original_active
