import bpy
from . import properties

MATERIAL_TEMPLATES = {
    "OPAQUE": {
        "geometrymode_G_FOG": True,
        "rendermode_blender_flag_CVG_X_ALPHA": False,
        "rendermode_forceblending": False,
        "rendermode_zmode": "OPA",

        "rendermode_blending_cycle0": "FOG_SHADE",
        "rendermode_blending_cycle1": "OPA",
    },
    "CLIP": {
        "geometrymode_G_FOG": False,
        "rendermode_blender_flag_CVG_X_ALPHA": True,
        "rendermode_forceblending": False,
        "rendermode_zmode": "OPA",

        "rendermode_blending_cycle0": "PASS",
        "rendermode_blending_cycle1": "XLU",
    },
    "BLEND": {
        "geometrymode_G_FOG": False,
        "rendermode_blender_flag_CVG_X_ALPHA": True,
        "rendermode_forceblending": True,
        "rendermode_zmode": "XLU",

        "rendermode_blending_cycle0": "XLU",
        "rendermode_blending_cycle1": "XLU",
    },
}

def material_apply_template(self, context:bpy.types.Context):
    material:bpy.types.Material = self.id_data
    objex:properties.ObjexMaterialProperties = material.objex_bonus

    material.blend_method = objex.alpha_mode
    
    for key, value in MATERIAL_TEMPLATES[objex.alpha_mode].items():
        setattr(objex, key, value)

    