import bpy

bl_info = {
    "name": "Microsoft Flight Simulator glTF Importer/Exporter Extension",
    "description": "Extension to the built-in glTF Importer/Exporter that adds support for Microsoft Flight Simulator's glTF format",
    "author": "pepperoni505",
    "version": (0, 0, 1),
    "blender": (3, 0, 0),
    "location": "File > Import-Export",
    "warning": "This addon is still in development. Expect things to not work properly",
    "tracker_url": "https://github.com/flybywiresim/msfs2blender2msfs",
    "support": "COMMUNITY",
    "category": "Import-Export",
}

class MSFSImporterExtensionProperties(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(
        name=bl_info["name"],
        description='Run this extension while importing the glTF file.',
        default=True
    )

class MSFSExporterExtensionProperties(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(
        name=bl_info["name"],
        description='Run this extension while exporting the glTF file.',
        default=True
    )

class glTF2ImportUserExtension: # Importer
    def __init__(self):
        self.properties = bpy.context.scene.MSFSImporterExtensionProperties

    def gather_import_node_before_hook(self, vnode, gltf_node):
        if self.properties.enabled:
            print("gather_import_node_before_hook")

    def gather_import_node_after_hook(self, vnode, gltf_node, blender_object):
        if self.properties.enabled:
            print("gather_import_node_after_hook")

class glTF2ExportUserExtension: # Exporter
    def __init__(self):
        self.properties = bpy.context.scene.MSFSExporterExtensionProperties

    def gather_node_hook(self, gltf2_object, blender_object, export_settings):
        if self.properties.enabled:
            print("gather_node_hook")

classes = (
    MSFSImporterExtensionProperties,
    MSFSExporterExtensionProperties
)

def register():
    for c in classes:
        bpy.utils.register_class(c)
        getattr(bpy.types.Scene, c) = bpy.props.PointerProperty(type=c)

def unregister():
    for c in classes:
        bpy.utils.unregister_class(c)
        del getattr(bpy.types.Scene, c)
