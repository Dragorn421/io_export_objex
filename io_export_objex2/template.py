import bpy
from . import properties

MATERIAL_TEMPLATES = {
    "OPAQUE": {
        "geometrymode_G_FOG": True,
        "rendermode_forceblending": False,
        "rendermode_blender_flag_CVG_X_ALPHA": False,
        "rendermode_blender_flag_CLR_ON_CVG": False,
        "rendermode_blender_flag_ALPHA_CVG_SEL": True,
        "rendermode_blender_flag_CVG_DST_": "CVG_DST_CLAMP",
        "rendermode_zmode": "OPA",

        "rendermode_blending_cycle0": "FOG_SHADE",
        "rendermode_blending_cycle1": "OPA",
    },
    "CLIP": {
        "geometrymode_G_FOG": False,
        "rendermode_forceblending": False,
        "rendermode_blender_flag_CVG_X_ALPHA": True,
        "rendermode_blender_flag_CLR_ON_CVG": False,
        "rendermode_blender_flag_ALPHA_CVG_SEL": True,
        "rendermode_blender_flag_CVG_DST_": "CVG_DST_CLAMP",
        "rendermode_zmode": "OPA",

        "rendermode_blending_cycle0": "PASS",
        "rendermode_blending_cycle1": "XLU",
    },
    "BLEND": {
        "geometrymode_G_FOG": False,
        "rendermode_forceblending": True,
        "rendermode_blender_flag_CVG_X_ALPHA": True,
        "rendermode_blender_flag_CLR_ON_CVG": False,
        "rendermode_blender_flag_ALPHA_CVG_SEL": False,
        "rendermode_blender_flag_CVG_DST_": "CVG_DST_WRAP",
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
    
    if material.blend_method == 'CLIP':
        material.alpha_threshold = 0.120

    