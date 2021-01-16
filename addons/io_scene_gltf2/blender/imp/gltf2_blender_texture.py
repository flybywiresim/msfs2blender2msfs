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

from .gltf2_blender_image import BlenderImage

class Textures:
    
    @staticmethod
    def loadImage(gltf, pytexture, label):
        if pytexture.texture is not None:
            BlenderImage.create(gltf, pytexture.texture.source, label)
            pyimg = gltf.data.images[pytexture.texture.source]
            blender_image_name = pyimg.blender_image_name
            if blender_image_name:
                return bpy.data.images[blender_image_name]

    @staticmethod
    def loadTextures(gltf, pymaterial, blender_material):
        # Something important to note - the comp texture contains different "textures" in each channel, so we reuse the comp texture a few times
        # Red channel = ambient occlusion, green channel = roughness, blue channel = metalness
        if pymaterial.normal_texture:
            Textures.loadNormalTexture(gltf, pymaterial, blender_material)
        if pymaterial.occlusion_texture: # the metallic texture is the occlusion texture
            Textures.loadOcclusionTexture(gltf, pymaterial, blender_material)
        if pymaterial.emissive_texture:
            Textures.loadEmissiveTexture(gltf, pymaterial, blender_material)
        if pymaterial.pbr_metallic_roughness:
            Textures.loadPBRMetallicRoughness(gltf, pymaterial, blender_material)

    @staticmethod
    def loadNormalTexture(gltf, pymaterial, blender_material):
        pytexture = gltf.data.textures[pymaterial.normal_texture.index]
        image = Textures.loadImage(gltf, pytexture, "NORMALMAP")
        blender_material.msfs_normal_texture = image

    @staticmethod
    def loadOcclusionTexture(gltf, pymaterial, blender_material):
        pytexture = gltf.data.textures[pymaterial.occlusion_texture.index]
        image = Textures.loadImage(gltf, pytexture, "OCCLUSION")
        blender_material.msfs_metallic_texture = image

    @staticmethod
    def loadEmissiveTexture(gltf, pymaterial, blender_material):
        if pymaterial.emissive_texture:
            pytexture = gltf.data.textures[pymaterial.emissive_texture.index]
            image = Textures.loadImage(gltf, pytexture, "EMISSIVE")
            blender_material.msfs_emissive_texture = image

    
    @staticmethod
    def loadPBRMetallicRoughness(gltf, pymaterial, blender_material):
        if pymaterial.pbr_metallic_roughness.base_color_texture: # base color texture is albedo
            pytexture = gltf.data.textures[pymaterial.pbr_metallic_roughness.base_color_texture.index]
            image = Textures.loadImage(gltf, pytexture, "BASE COLOR")
            blender_material.msfs_albedo_texture = image
        if pymaterial.pbr_metallic_roughness.metallic_roughness_texture:
            pytexture = gltf.data.textures[pymaterial.pbr_metallic_roughness.metallic_roughness_texture.index]
            image = Textures.loadImage(gltf, pytexture, "METALLIC ROUGHNESS")
            blender_material.msfs_metallic_texture = image

    @staticmethod
    def loadDetailMap(gltf, pymaterial, blender_material):
        detail_map_properties = pymaterial.extensions["ASOBO_material_detail_map"]
        if "UVScale" in detail_map_properties:
            blender_material.msfs_detail_uv_scale = detail_map_properties["UVScale"]
        if "UVOffset" in detail_map_properties:
            blender_material.msfs_detail_uv_offset_x = detail_map_properties["UVOffset"][0]
            blender_material.msfs_detail_uv_offset_y = detail_map_properties["UVOffset"][1]
        if "blendThreshold" in detail_map_properties:
            blender_material.msfs_blend_threshold = detail_map_properties["blendThreshold"]
        if "detailColorTexture" in detail_map_properties:
            pytexture = gltf.data.textures[detail_map_properties["detailColorTexture"]["index"]]
            image = Textures.loadImage(gltf, pytexture, "DETAIL COLOR")
            blender_material.msfs_detail_albedo_texture = image
        if "detailNormalTexture" in detail_map_properties:
            pytexture = gltf.data.textures[detail_map_properties["detailNormalTexture"]["index"]]
            image = Textures.loadImage(gltf, pytexture, "NORMALMAP")
            blender_material.msfs_detail_normal_texture = image
            if "scale" in detail_map_properties["detailNormalTexture"]:
                blender_material.msfs_detail_normal_scale = detail_map_properties["detailNormalTexture"]["scale"]
        if "detailMetalRoughAOTexture" in detail_map_properties:
            pytexture = gltf.data.textures[detail_map_properties["detailMetalRoughAOTexture"]["index"]]
            image = Textures.loadImage(gltf, pytexture, "METALLIC ROUGHNESS")
            blender_material.msfs_detail_metallic_texture = image
        if "blendMaskTexture" in detail_map_properties:
            pytexture = gltf.data.textures[detail_map_properties["blendMaskTexture"]["index"]]
            image = Textures.loadImage(gltf, pytexture, "BLEND MASK")
            blender_material.msfs_blend_mask_texture = image

    @staticmethod
    def loadDecalBlendFactors(gltf, pymaterial, blender_material):
        decal_blend_factors = pymaterial.extensions["ASOBO_material_blend_gbuffer"]
        if "baseColorBlendFactor" in decal_blend_factors:
            if blender_material.msfs_material_type == "msfs_geo_decal":
                blender_material.msfs_geo_decal_blend_factor_color = decal_blend_factors["baseColorBlendFactor"]
            else:
                blender_material.msfs_decal_blend_factor_color = decal_blend_factors["baseColorBlendFactor"]
        if "metallicBlendFactor" in decal_blend_factors:
            if blender_material.msfs_material_type == "msfs_geo_decal":
                blender_material.msfs_geo_decal_blend_factor_metal = decal_blend_factors["metallicBlendFactor"]
            else:
                blender_material.msfs_decal_blend_factor_metal = decal_blend_factors["metallicBlendFactor"]
        if "roughnessBlendFactor" in decal_blend_factors:
            if blender_material.msfs_material_type == "msfs_geo_decal":
                blender_material.msfs_geo_decal_blend_factor_roughness = decal_blend_factors["roughnessBlendFactor"]
            else:
                blender_material.msfs_decal_blend_factor_roughness = decal_blend_factors["roughnessBlendFactor"]
        if "normalBlendFactor" in decal_blend_factors:
            if blender_material.msfs_material_type == "msfs_geo_decal":
                blender_material.msfs_geo_decal_blend_factor_normal = decal_blend_factors["normalBlendFactor"]
            else:
                blender_material.msfs_decal_blend_factor_normal = decal_blend_factors["normalBlendFactor"]
        if "emissiveBlendFactor" in decal_blend_factors:
            if blender_material.msfs_material_type == "msfs_geo_decal":
                blender_material.msfs_geo_decal_blend_factor_melt_sys = decal_blend_factors["emissiveBlendFactor"] # emissive for geo decals is melt sys
            else:
                blender_material.msfs_decal_blend_factor_emissive = decal_blend_factors["emissiveBlendFactor"]
        if "occlusionBlendFactor" in decal_blend_factors:
            if blender_material.msfs_material_type == "msfs_geo_decal":
                blender_material.msfs_geo_decal_blend_factor_blast_sys = decal_blend_factors["occlusionBlendFactor"] # occlusion for geo decals is blast sys
            else:
                blender_material.msfs_decal_blend_factor_occlusion = decal_blend_factors["occlusionBlendFactor"]

    @staticmethod
    def loadClearcoatTexture(gltf, pymaterial, blender_material):
        pytexture = gltf.data.textures[pymaterial.extensions["ASOBO_material_clear_coat"]["dirtTexture"]["index"]]
        image = Textures.loadImage(gltf, pytexture, "DIRT")
        blender_material.msfs_normal_texture = image

    @staticmethod
    def loadBehindWindowMapTexture(gltf, pymaterial, blender_material):
        pytexture = gltf.data.textures[pymaterial.extensions["ASOBO_material_parallax_window"]["behindWindowMapTexture"]["index"]]
        image = Textures.loadImage(gltf, pytexture, "DETAIL COLOR")
        blender_material.msfs_normal_texture = image