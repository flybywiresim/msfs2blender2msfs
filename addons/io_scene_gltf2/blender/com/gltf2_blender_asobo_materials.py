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


# Based off https://github.com/AsoboStudio/FlightSim-glTF-exporter

from typing import Optional, Dict, List, Type
from mathutils import Vector


class ASOBO_TextureInfo():

    def __init__(self, index : int, texCoord : Optional[int] = None):
        self.index = index
        self.texCoord = texCoord

class ASOBO_Property():

    def __init__(self, extensions : Optional[Dict[str, object]] = None, extras : Optional[Dict[str, object]] = None):
        self.extensions = extensions
        self.extras = extras

class ASOBO_NormalTextureInfo(ASOBO_TextureInfo):

    def __init__(self, index, scale : Optional[float] = None, texCoord = None):
        super().__init__(index, texCoord)
        self.scale = scale

class ASOBO_OcclusionTextureInfo(ASOBO_TextureInfo):

    def __init__(self, index, strength : Optional[float] = None, texCoord = None):
        super().__init__(index, texCoord)
        self.strength = None

class ASOBO_EXTENSION_MaterialGeometryDecal(ASOBO_Property):

    serializedName = "ASOBO_material_blend_gbuffer"
    
    def __init__(self, extensions = None, extras = None, enabled : bool = True, baseColorBlendFactor : Optional[float] = None, metallicBlendFactor : Optional[float] = None, \
                 roughnessBlendFactor : Optional[float] = None, normalBlendFactor : Optional[float] = None, emissiveBlendFactor : Optional[float] = None, occlusionBlendFactor : Optional[float] = None):
        super().__init__(extensions, extras)
        self.enabled = enabled
        self.baseColorBlendFactor = baseColorBlendFactor
        self.metallicBlendFactor = metallicBlendFactor
        self.roughnessBlendFactor = roughnessBlendFactor
        self.normalBlendFactor = normalBlendFactor
        self.emissiveBlendFactor = emissiveBlendFactor
        self.occlusionBlendFactor = occlusionBlendFactor
        
class ASOBO_EXTENSION_MaterialDrawOrder(ASOBO_Property):

    serializedName = "ASOBO_material_draw_order"

    def __init__(self, extensions = None, extras = None, drawOrderOffset : Optional[int] = None):
        super().__init__(extensions, extras)
        self.drawOrderOffset = drawOrderOffset
    
    class Defaults:
            drawOrderOffset : int = 0

class ASOBO_EXTENSION_DayNightCycle(ASOBO_Property): # This probably won't be used

    serializedName = "ASOBO_material_day_night_switch"

    def init(self, extensions = None, extras = None):
        super().__init__(extensions, extras)

class ASOBO_EXTENSION_PearlPearlescent(ASOBO_Property): # This also probably won't be used

    serializedName = "ASOBO_material_pearlescent"

    def init(self, extension = None, extras = None, pearlShift : Optional[float] = None, pearlRange : Optional[float] = None, pearlBrightness : Optional[float] = None):
        super().__init__(extensions, extras)
        self.pearlShift = pearlShift
        self.pearlRange = pearlRange
        self.pearlBrightness = pearlBrightness

    class Defaults:
        pearlShift : float = 0.0
        pearlRange : float = 0.0
        pearlBrightness : float = 0.0

class ASOBO_EXTENSION_AlphaModeDither(ASOBO_Property):
    
    serializedName = "ASOBO_material_alphamode_dither"

    def __init__(self, extensions = None, extras = None, enabled : bool = True):
        super().__init__(extensions, extras)
        self.enabled = enabled

class ASOBO_EXTENSION_MaterialInvisible(ASOBO_Property):

    serializedName = "ASOBO_material_invisible"

    def __init__(self, extensions = None, extras = None, enabled : bool = True):
        super().__init(extensions, extras)
        self.enabled = enabled

class ASOBO_EXTENSION_MaterialEnvironmentOccluder(ASOBO_Property):

    serializedName = "ASOBO_material_environment_occluder"

    def __init__(self, extensions = None, extras = None, enabled : bool = True):
        super().__init__(extensions, extras)
        self.enabled = enabled

class ASOBO_EXTENSION_MaterialUVOptions(ASOBO_Property):

    serializedName = "ASOBO_material_UV_options"

    def __init__(self, extensions = None, extras = None, AOUseUV2 : Optional[bool] = None, clampUVX : Optional[bool] = None, clampUVY : Optional[bool] = None, \
                 clampUVZ : Optional[bool] = None):
        super().__init__(extensions, extras)
        self.AOUseUV2 = AOUseUV2
        self.clampUVX = clampUVX
        self.clampUVY = clampUVY
        self.clampUVZ = clampUVZ

    class Defaults:
        AOUseUV2 : bool = False
        clampUVX : bool = False
        clampUVY : bool = False
        clampUVZ : bool = False

class ASOBO_EXTENSION_MaterialShadowOptions(ASOBO_Property):

    serializedName = "ASOBO_material_shadow_options"

    def __init__(self, extensions = None, extras = None, noCastShadow : Optional[bool] = None):
        super().__init__(extensions, extras)
        self.noCastShadow = noCastShadow

    class Defaults:
        noCastShadow : bool = False

class ASOBO_EXTENSION_MaterialResponsiveAAOptions(ASOBO_Property):
    
    serializedName = "ASOBO_material_antialiasing_options"

    def __init__(self, extensions = None, extras = None, responsiveAA : Optional[bool] = None):
        super().__init__(extensions, extras)
        self.responsiveAA = responsiveAA

    class Defaults:
        responsiveAA : bool = False

class ASOBO_EXTENSION_MaterialFakeTerrain(ASOBO_Property): # Again, probably won't use this

    serializedName = "ASOBO_material_fake_terrain"
    
    def __init__(self, extensions = None, extras = None, enabled : bool = True):
        super().__init__(extensions, extras)
        self.enabled = enabled

class ASOBO_EXTENSION_MaterialFresnelFade(ASOBO_Property):

    serializedName = "ASOBO_material_fresnel_fade"

    def __init__(self, extensions = None, extras = None, fresnelFactor : Optional[float] = None, fresnelOpacityOffset : Optional[float] = None):
        super().__init__(extensions, extras)
        self.fresnelFactor = fresnelFactor
        self.fresnelOpacityOffset = fresnelOpacityOffset

    class Defaults:
        fresnelFactor : float = 1
        fresnelOpacityOffset : float = 1

class ASOBO_EXTENSION_Material_Detail:
    
    serializedName = "ASOBO_material_detail_map"

    def __init__(self, UVScale : Optional[float] = None, UVOffset : Optional[Vector] = None, blendThreshold : Optional[float] = None, detailColorTexture : Optional[Type[ASOBO_TextureInfo]] = None, \
                 detailNormalTexture : Optional[Type[ASOBO_NormalTextureInfo]] = None, detailMetalRoughAOTexture : Optional[Type[ASOBO_TextureInfo]] = None, blendMaskTexture : Optional[Type[ASOBO_TextureInfo]] = None):
        self.UVScale = UVScale
        self.UVOffset = UVOffset
        self.blendThreshold = blendThreshold
        self.detailColorTexture = detailColorTexture
        self.detailNormalTexture = detailNormalTexture
        self.detailMetalRoughAOTexture = detailMetalRoughAOTexture
        self.blendMaskTexture = blendMaskTexture

    class Defaults:
        UVScale : float = 1
        UVOffset : Vector = Vector((0, 0))
        blendThreshold : float = 0.1
        NormalScale : float = 1

class ASOBO_EXTENSION_SSS(ASOBO_Property):
    
    serializedName = "ASOBO_material_SSS"

    def __init__(self, extensions = None, extras = None, SSSColor : Optional[Vector] = None, opacityTexture : Optional[Type[ASOBO_TextureInfo]] = None):
        super().__init__(extensions, extras)
        self.SSSColor = SSSColor
        self.opacityTexture = opacityTexture

    class Defaults:
        SSSColor : Vector = Vector((1, 1, 1, 1))

class ASOBO_EXTENSION_Anisotropic(ASOBO_Property):
    
    serializedName = "ASOBO_material_anisotropic"

    def __init__(self, extensions = None, extras = None, anisotropicTexture : Optional[Type[ASOBO_TextureInfo]] = None):
        super().__init__(extensions, extras)
        self.anisotropicTexture = anisotropicTexture

class ASOBO_Extension_Windshield(ASOBO_Property):

    serializedName = "ASOBO_material_windshield"

    def __init__(self, extensions = None, extras = None, rainDropScale : Optional[float] = None, wiperMaskTexture : Optional[Type[ASOBO_TextureInfo]] = None):
        super().__init__(extensions, extras)
        self.rainDropScale = rainDropScale
        self.wiperMaskTexture = wiperMaskTexture

    class Defaults:
        rainDropScale : float = 1

class ASOBO_EXTENSION_ClearCoat(ASOBO_Property):

    serializedName = "ASOBO_material_clear_coat"

    def __init__(self, extensions = None, extras = None, dirtTexture : Optional[Type[ASOBO_TextureInfo]] = None):
        super().__init__(extensions, extras)
        self.dirtTexture = dirtTexture

class ASOBO_EXTENSION_ParallaxWindow(ASOBO_Property):

    serializedName = "ASOBO_material_parallax_window"

    def __init__(self, extensions = None, extras = None, parallaxScale : Optional[float] = None, roomSizeXScale : Optional[float] = None, roomSizeYScale : Optional[float] = None, \
                 roomNumberXY : Optional[float] = None, corridor : Optional[bool] = None, behindWindowMapTexture : Optional[Type[ASOBO_TextureInfo]] = None):
        super().__init__(extensions, extras)
        self.parallaxScale = parallaxScale
        self.roomSizeXScale = roomSizeXScale
        self.roomSizeYScale = roomSizeYScale
        self.roomNumberXY = roomNumberXY
        self.corridor = corridor
        self.behindWindowMapTexture = behindWindowMapTexture

    class Defaults:
        parallaxScale : float = 0
        roomSizeXScale : float = 1
        roomSizeYScale : float= 1
        roomNumberXY : float = 1
        corridor : bool = False

class ASOBO_EXTENSION_FlightSimGlass(ASOBO_Property): # I'm pretty sure this material is deprecated but this will remain here

    serializedName = "ASOBO_material_glass"

    def __init__(self, extensions = None, extras = None, glassReflectionMaskFactor : Optional[float] = None, glassDeformationFactor : Optional[float] = None):
        super().__init__(extensions, extras)
        self.glassReflectionMaskFactor = glassReflectionMaskFactor
        self.glassDeformationFactor

    class Defaults:
        glassReflectionMaskFactor : float = 0
        glassDeformationFactor : float = 0

class ASOBO_EXTENSION_Helper:
    
    Name_MSFT_texture_dds = "MSFT_texture_dds"

