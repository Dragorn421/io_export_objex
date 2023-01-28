import bpy

COMBINER_TEMPLATES = {
    'DEFAULT': {
        'input_flags_C_A_0': ( 'OBJEX_ColorCycle0', 'A', 'G_CCMUX_TEXEL0' ),
        'input_flags_C_B_0': ( 'OBJEX_ColorCycle0', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_0': ( 'OBJEX_ColorCycle0', 'C', 'G_CCMUX_PRIMITIVE' ),
        'input_flags_C_D_0': ( 'OBJEX_ColorCycle0', 'D', 'G_CCMUX_0' ),

        'input_flags_C_A_1': ( 'OBJEX_ColorCycle1', 'A', 'G_CCMUX_COMBINED' ),
        'input_flags_C_B_1': ( 'OBJEX_ColorCycle1', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_1': ( 'OBJEX_ColorCycle1', 'C', 'G_CCMUX_SHADE' ),
        'input_flags_C_D_1': ( 'OBJEX_ColorCycle1', 'D', 'G_CCMUX_0' ),

        'input_flags_A_A_0': ( 'OBJEX_AlphaCycle0', 'A', 'G_ACMUX_TEXEL0' ),
        'input_flags_A_B_0': ( 'OBJEX_AlphaCycle0', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_0': ( 'OBJEX_AlphaCycle0', 'C', 'G_ACMUX_PRIMITIVE' ),
        'input_flags_A_D_0': ( 'OBJEX_AlphaCycle0', 'D', 'G_ACMUX_0' ),

        'input_flags_A_A_1': ( 'OBJEX_AlphaCycle1', 'A', 'G_ACMUX_COMBINED' ),
        'input_flags_A_B_1': ( 'OBJEX_AlphaCycle1', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_1': ( 'OBJEX_AlphaCycle1', 'C', 'G_ACMUX_SHADE' ),
        'input_flags_A_D_1': ( 'OBJEX_AlphaCycle1', 'D', 'G_ACMUX_0' ),
    },
    'DEFAULT_ENV': {
        'input_flags_C_A_0': ( 'OBJEX_ColorCycle0', 'A', 'G_CCMUX_TEXEL0' ),
        'input_flags_C_B_0': ( 'OBJEX_ColorCycle0', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_0': ( 'OBJEX_ColorCycle0', 'C', 'G_CCMUX_ENVIRONMENT' ),
        'input_flags_C_D_0': ( 'OBJEX_ColorCycle0', 'D', 'G_CCMUX_0' ),

        'input_flags_C_A_1': ( 'OBJEX_ColorCycle1', 'A', 'G_CCMUX_COMBINED' ),
        'input_flags_C_B_1': ( 'OBJEX_ColorCycle1', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_1': ( 'OBJEX_ColorCycle1', 'C', 'G_CCMUX_SHADE' ),
        'input_flags_C_D_1': ( 'OBJEX_ColorCycle1', 'D', 'G_CCMUX_0' ),

        'input_flags_A_A_0': ( 'OBJEX_AlphaCycle0', 'A', 'G_ACMUX_TEXEL0' ),
        'input_flags_A_B_0': ( 'OBJEX_AlphaCycle0', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_0': ( 'OBJEX_AlphaCycle0', 'C', 'G_ACMUX_ENVIRONMENT' ),
        'input_flags_A_D_0': ( 'OBJEX_AlphaCycle0', 'D', 'G_ACMUX_0' ),

        'input_flags_A_A_1': ( 'OBJEX_AlphaCycle1', 'A', 'G_ACMUX_COMBINED' ),
        'input_flags_A_B_1': ( 'OBJEX_AlphaCycle1', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_1': ( 'OBJEX_AlphaCycle1', 'C', 'G_ACMUX_SHADE' ),
        'input_flags_A_D_1': ( 'OBJEX_AlphaCycle1', 'D', 'G_ACMUX_0' ),
    },
    'MIX': {
        'input_flags_C_A_0': ( 'OBJEX_ColorCycle0', 'A', 'G_CCMUX_TEXEL0' ),
        'input_flags_C_B_0': ( 'OBJEX_ColorCycle0', 'B', 'G_CCMUX_TEXEL1' ),
        'input_flags_C_C_0': ( 'OBJEX_ColorCycle0', 'C', 'G_CCMUX_PRIMITIVE_ALPHA' ),
        'input_flags_C_D_0': ( 'OBJEX_ColorCycle0', 'D', 'G_CCMUX_TEXEL1' ),

        'input_flags_C_A_1': ( 'OBJEX_ColorCycle1', 'A', 'G_CCMUX_COMBINED' ),
        'input_flags_C_B_1': ( 'OBJEX_ColorCycle1', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_1': ( 'OBJEX_ColorCycle1', 'C', 'G_CCMUX_SHADE' ),
        'input_flags_C_D_1': ( 'OBJEX_ColorCycle1', 'D', 'G_CCMUX_0' ),

        'input_flags_A_A_0': ( 'OBJEX_AlphaCycle0', 'A', 'G_ACMUX_TEXEL0' ),
        'input_flags_A_B_0': ( 'OBJEX_AlphaCycle0', 'B', 'G_ACMUX_TEXEL1' ),
        'input_flags_A_C_0': ( 'OBJEX_AlphaCycle0', 'C', 'G_ACMUX_PRIMITIVE' ),
        'input_flags_A_D_0': ( 'OBJEX_AlphaCycle0', 'D', 'G_ACMUX_TEXEL1' ),

        'input_flags_A_A_1': ( 'OBJEX_AlphaCycle1', 'A', 'G_ACMUX_COMBINED' ),
        'input_flags_A_B_1': ( 'OBJEX_AlphaCycle1', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_1': ( 'OBJEX_AlphaCycle1', 'C', 'G_ACMUX_SHADE' ),
        'input_flags_A_D_1': ( 'OBJEX_AlphaCycle1', 'D', 'G_ACMUX_0' ),
    },
    'MIX_ENV': {
        'input_flags_C_A_0': ( 'OBJEX_ColorCycle0', 'A', 'G_CCMUX_TEXEL0' ),
        'input_flags_C_B_0': ( 'OBJEX_ColorCycle0', 'B', 'G_CCMUX_TEXEL1' ),
        'input_flags_C_C_0': ( 'OBJEX_ColorCycle0', 'C', 'G_CCMUX_ENV_ALPHA' ),
        'input_flags_C_D_0': ( 'OBJEX_ColorCycle0', 'D', 'G_CCMUX_TEXEL1' ),

        'input_flags_C_A_1': ( 'OBJEX_ColorCycle1', 'A', 'G_CCMUX_COMBINED' ),
        'input_flags_C_B_1': ( 'OBJEX_ColorCycle1', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_1': ( 'OBJEX_ColorCycle1', 'C', 'G_CCMUX_SHADE' ),
        'input_flags_C_D_1': ( 'OBJEX_ColorCycle1', 'D', 'G_CCMUX_0' ),

        'input_flags_A_A_0': ( 'OBJEX_AlphaCycle0', 'A', 'G_ACMUX_TEXEL0' ),
        'input_flags_A_B_0': ( 'OBJEX_AlphaCycle0', 'B', 'G_ACMUX_TEXEL1' ),
        'input_flags_A_C_0': ( 'OBJEX_AlphaCycle0', 'C', 'G_ACMUX_ENVIRONMENT' ),
        'input_flags_A_D_0': ( 'OBJEX_AlphaCycle0', 'D', 'G_ACMUX_TEXEL1' ),

        'input_flags_A_A_1': ( 'OBJEX_AlphaCycle1', 'A', 'G_ACMUX_COMBINED' ),
        'input_flags_A_B_1': ( 'OBJEX_AlphaCycle1', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_1': ( 'OBJEX_AlphaCycle1', 'C', 'G_ACMUX_SHADE' ),
        'input_flags_A_D_1': ( 'OBJEX_AlphaCycle1', 'D', 'G_ACMUX_0' ),
    },
    'MULT': {
        'input_flags_C_A_0': ( 'OBJEX_ColorCycle0', 'A', 'G_CCMUX_TEXEL0' ),
        'input_flags_C_B_0': ( 'OBJEX_ColorCycle0', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_0': ( 'OBJEX_ColorCycle0', 'C', 'G_CCMUX_TEXEL1' ),
        'input_flags_C_D_0': ( 'OBJEX_ColorCycle0', 'D', 'G_CCMUX_0' ),

        'input_flags_C_A_1': ( 'OBJEX_ColorCycle1', 'A', 'G_CCMUX_COMBINED' ),
        'input_flags_C_B_1': ( 'OBJEX_ColorCycle1', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_1': ( 'OBJEX_ColorCycle1', 'C', 'G_CCMUX_SHADE' ),
        'input_flags_C_D_1': ( 'OBJEX_ColorCycle1', 'D', 'G_CCMUX_0' ),

        'input_flags_A_A_0': ( 'OBJEX_AlphaCycle0', 'A', 'G_ACMUX_TEXEL0' ),
        'input_flags_A_B_0': ( 'OBJEX_AlphaCycle0', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_0': ( 'OBJEX_AlphaCycle0', 'C', 'G_ACMUX_TEXEL1' ),
        'input_flags_A_D_0': ( 'OBJEX_AlphaCycle0', 'D', 'G_ACMUX_0' ),

        'input_flags_A_A_1': ( 'OBJEX_AlphaCycle1', 'A', 'G_ACMUX_COMBINED' ),
        'input_flags_A_B_1': ( 'OBJEX_AlphaCycle1', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_1': ( 'OBJEX_AlphaCycle1', 'C', 'G_ACMUX_SHADE' ),
        'input_flags_A_D_1': ( 'OBJEX_AlphaCycle1', 'D', 'G_ACMUX_0' ),
    },
    'LIGHTED': {
        'input_flags_C_A_0': ( 'OBJEX_ColorCycle0', 'A', 'G_CCMUX_TEXEL0' ),
        'input_flags_C_B_0': ( 'OBJEX_ColorCycle0', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_0': ( 'OBJEX_ColorCycle0', 'C', 'G_CCMUX_PRIMITIVE' ),
        'input_flags_C_D_0': ( 'OBJEX_ColorCycle0', 'D', 'G_CCMUX_0' ),

        'input_flags_C_A_1': ( 'OBJEX_ColorCycle1', 'A', 'G_CCMUX_COMBINED' ),
        'input_flags_C_B_1': ( 'OBJEX_ColorCycle1', 'B', 'G_CCMUX_0' ),
        'input_flags_C_C_1': ( 'OBJEX_ColorCycle1', 'C', 'G_CCMUX_SHADE' ),
        'input_flags_C_D_1': ( 'OBJEX_ColorCycle1', 'D', 'G_CCMUX_0' ),

        'input_flags_A_A_0': ( 'OBJEX_AlphaCycle0', 'A', 'G_ACMUX_TEXEL0' ),
        'input_flags_A_B_0': ( 'OBJEX_AlphaCycle0', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_0': ( 'OBJEX_AlphaCycle0', 'C', 'G_ACMUX_PRIMITIVE' ),
        'input_flags_A_D_0': ( 'OBJEX_AlphaCycle0', 'D', 'G_ACMUX_0' ),

        'input_flags_A_A_1': ( 'OBJEX_AlphaCycle1', 'A', 'G_ACMUX_0' ),
        'input_flags_A_B_1': ( 'OBJEX_AlphaCycle1', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_1': ( 'OBJEX_AlphaCycle1', 'C', 'G_ACMUX_0' ),
        'input_flags_A_D_1': ( 'OBJEX_AlphaCycle1', 'D', 'G_ACMUX_COMBINED' ),
    },
    'FLAME_TEXEL': {
        'input_flags_C_A_0': ( 'OBJEX_ColorCycle0', 'A', 'G_CCMUX_TEXEL1' ),
        'input_flags_C_B_0': ( 'OBJEX_ColorCycle0', 'B', 'G_CCMUX_PRIMITIVE' ),
        'input_flags_C_C_0': ( 'OBJEX_ColorCycle0', 'C', 'G_CCMUX_PRIM_LOD_FRAC' ),
        'input_flags_C_D_0': ( 'OBJEX_ColorCycle0', 'D', 'G_CCMUX_TEXEL1' ),

        'input_flags_C_A_1': ( 'OBJEX_ColorCycle1', 'A', 'G_CCMUX_PRIMITIVE' ),
        'input_flags_C_B_1': ( 'OBJEX_ColorCycle1', 'B', 'G_CCMUX_ENVIRONMENT' ),
        'input_flags_C_C_1': ( 'OBJEX_ColorCycle1', 'C', 'G_CCMUX_COMBINED' ),
        'input_flags_C_D_1': ( 'OBJEX_ColorCycle1', 'D', 'G_CCMUX_ENVIRONMENT' ),

        'input_flags_A_A_0': ( 'OBJEX_AlphaCycle0', 'A', 'G_ACMUX_TEXEL1' ),
        'input_flags_A_B_0': ( 'OBJEX_AlphaCycle0', 'B', 'G_ACMUX_1' ),
        'input_flags_A_C_0': ( 'OBJEX_AlphaCycle0', 'C', 'G_ACMUX_PRIM_LOD_FRAC' ),
        'input_flags_A_D_0': ( 'OBJEX_AlphaCycle0', 'D', 'G_ACMUX_TEXEL0' ),

        'input_flags_A_A_1': ( 'OBJEX_AlphaCycle1', 'A', 'G_ACMUX_COMBINED' ),
        'input_flags_A_B_1': ( 'OBJEX_AlphaCycle1', 'B', 'G_ACMUX_0' ),
        'input_flags_A_C_1': ( 'OBJEX_AlphaCycle1', 'C', 'G_ACMUX_ENVIRONMENT' ),
        'input_flags_A_D_1': ( 'OBJEX_AlphaCycle1', 'D', 'G_ACMUX_0' ),
    },
}

MATERIAL_TEMPLATES = {
    'OPAQUE': {
        'geometrymode_G_FOG': True,
        'rendermode_forceblending': False,
        'rendermode_blender_flag_CVG_X_ALPHA': False,
        'rendermode_blender_flag_CLR_ON_CVG': False,
        'rendermode_blender_flag_ALPHA_CVG_SEL': True,
        'rendermode_blender_flag_CVG_DST_': 'CVG_DST_CLAMP',
        'rendermode_zmode': 'OPA',

        'rendermode_blending_cycle0': 'FOG_SHADE',
        'rendermode_blending_cycle1': 'OPA',
    },
    'CLIP': {
        'geometrymode_G_FOG': True,
        'rendermode_forceblending': False,
        'rendermode_blender_flag_CVG_X_ALPHA': True,
        'rendermode_blender_flag_CLR_ON_CVG': False,
        'rendermode_blender_flag_ALPHA_CVG_SEL': True,
        'rendermode_blender_flag_CVG_DST_': 'CVG_DST_CLAMP',
        'rendermode_zmode': 'OPA',

        'rendermode_blending_cycle0': 'FOG_SHADE',
        'rendermode_blending_cycle1': 'OPA',
    },
    'BLEND': {
        'geometrymode_G_FOG': False,
        'rendermode_forceblending': True,
        'rendermode_blender_flag_CVG_X_ALPHA': True,
        'rendermode_blender_flag_CLR_ON_CVG': False,
        'rendermode_blender_flag_ALPHA_CVG_SEL': False,
        'rendermode_blender_flag_CVG_DST_': 'CVG_DST_WRAP',
        'rendermode_zmode': 'XLU',

        'rendermode_blending_cycle0': 'XLU',
        'rendermode_blending_cycle1': 'XLU',
    },

    'OPAQUE_XLU': {
        'geometrymode_G_FOG': True,
        'rendermode_forceblending': True,
        'rendermode_blender_flag_CVG_X_ALPHA': False,
        'rendermode_blender_flag_CLR_ON_CVG': True,
        'rendermode_blender_flag_ALPHA_CVG_SEL': False,
        'rendermode_blender_flag_CVG_DST_': 'CVG_DST_CLAMP',
        'rendermode_zmode': 'OPA',

        'rendermode_blending_cycle0': 'FOG_SHADE',
        'rendermode_blending_cycle1': 'XLU',
    },
}

def material_apply_template(template:str, material:bpy.types.Material):
    objex = material.objex_bonus
    
    for key, value in MATERIAL_TEMPLATES[template].items():
        setattr(objex, key, value)

def combiner_apply_template(template:str, material:bpy.types.Material):
    node_tree = material.node_tree

    for input_flag, (node_target, alpha, value) in COMBINER_TEMPLATES[template].items():
        node = node_tree.nodes[node_target]

        setattr(node.inputs[alpha], input_flag, value)
