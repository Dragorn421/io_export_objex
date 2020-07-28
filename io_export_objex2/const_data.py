import bpy

COLOR_OK = (0,1,0,1) # green
COLOR_BAD = (1,0,0,1) # red
COLOR_RGBA_COLOR = (1,1,0,1) # yellow
COLOR_NONE = (0,0,0,0) # transparent

CYCLE_COLOR = 'C'
CYCLE_ALPHA = 'A'

COMBINER_FLAGS_0 = {
    'C': 'G_CCMUX_0',
    'A': 'G_ACMUX_0',
}

COMBINER_FLAGS_PREFIX = {
    'C': 'G_CCMUX_',
    'A': 'G_ACMUX_',
}

# 421todo *_SHADE* is only vertex colors atm
# supported combiner inputs by cycle (Color, Alpha) and by variable (A,B,C,D)
# source: https://wiki.cloudmodding.com/oot/F3DZEX#Color_Combiner_Settings
COMBINER_FLAGS_SUPPORT = {
    'C': {
        'A': {
            'G_CCMUX_COMBINED','G_CCMUX_TEXEL0','G_CCMUX_TEXEL1','G_CCMUX_PRIMITIVE',
            'G_CCMUX_SHADE',
            'G_CCMUX_ENVIRONMENT','G_CCMUX_1',
            #'G_CCMUX_NOISE',
            'G_CCMUX_0'
        },
        'B': {
            'G_CCMUX_COMBINED','G_CCMUX_TEXEL0','G_CCMUX_TEXEL1','G_CCMUX_PRIMITIVE',
            'G_CCMUX_SHADE',
            'G_CCMUX_ENVIRONMENT',
            #'G_CCMUX_CENTER',
            #'G_CCMUX_K4',
            'G_CCMUX_0'
        },
        'C': {
            'G_CCMUX_COMBINED','G_CCMUX_TEXEL0','G_CCMUX_TEXEL1','G_CCMUX_PRIMITIVE',
            'G_CCMUX_SHADE',
            'G_CCMUX_ENVIRONMENT',
            #'G_CCMUX_SCALE',
            'G_CCMUX_COMBINED_ALPHA',
            'G_CCMUX_TEXEL0_ALPHA',
            'G_CCMUX_TEXEL1_ALPHA',
            'G_CCMUX_PRIMITIVE_ALPHA',
            'G_CCMUX_SHADE_ALPHA',
            'G_CCMUX_ENV_ALPHA',
            #'G_CCMUX_LOD_FRACTION',
            #'G_CCMUX_PRIM_LOD_FRAC',
            #'G_CCMUX_K5',
            'G_CCMUX_0'
        },
        'D': {
            'G_CCMUX_COMBINED','G_CCMUX_TEXEL0','G_CCMUX_TEXEL1','G_CCMUX_PRIMITIVE',
            'G_CCMUX_SHADE',
            'G_CCMUX_ENVIRONMENT','G_CCMUX_1','G_CCMUX_0'
        },
    },
    'A': {
        'A': {
            'G_ACMUX_COMBINED','G_ACMUX_TEXEL0','G_ACMUX_TEXEL1','G_ACMUX_PRIMITIVE',
            'G_ACMUX_SHADE',
            'G_ACMUX_ENVIRONMENT','G_ACMUX_1',
            'G_ACMUX_0'
        },
        'B': {
            'G_ACMUX_COMBINED','G_ACMUX_TEXEL0','G_ACMUX_TEXEL1','G_ACMUX_PRIMITIVE',
            'G_ACMUX_SHADE',
            'G_ACMUX_ENVIRONMENT','G_ACMUX_1',
            'G_ACMUX_0'
        },
        'C': {
            #'G_ACMUX_LOD_FRACTION',
            'G_ACMUX_TEXEL0','G_ACMUX_TEXEL1','G_ACMUX_PRIMITIVE',
            'G_ACMUX_SHADE',
            'G_ACMUX_ENVIRONMENT',
            #'G_ACMUX_PRIM_LOD_FRAC',
            'G_ACMUX_0'
        },
        'D': {
            'G_ACMUX_COMBINED','G_ACMUX_TEXEL0','G_ACMUX_TEXEL1','G_ACMUX_PRIMITIVE',
            'G_ACMUX_SHADE',
            'G_ACMUX_ENVIRONMENT','G_ACMUX_1',
            'G_ACMUX_0'
        },
    },
}

node_setup = {
    'Geometry': {
        'type': 'ShaderNodeGeometry' if hasattr(bpy.types, 'ShaderNodeGeometry') else 'ShaderNodeNewGeometry',
        'location': (-520, -100),
    },
    'OBJEX_TransformUV_Main': {
        # type defaults to ShaderNodeGroup if 'group' is set
        'group': 'OBJEX_UV_pipe_main', # optional
        'label': 'UV transform main', # optional
        'location': (-300, -100),
        'width': 150,
        'inputs': { # optional, input_socket_key: default_value
            'Texgen': False,
            'Texgen Linear': False,
        },
        'hide-inputs': [ # optional, input_socket_key
            'Texgen (0/1)',
            'Texgen Linear (0/1)',
        ],
        'links': { # input_socket_key: (from_node_name, from_socket_key)
            'UV': ('Geometry', 'UV'),
            'Normal': ('Geometry', 'Normal'),
        },
    },
    'OBJEX_TransformUV0': {
        'group': 'OBJEX_UV_pipe',
        'label': 'UV transform 0',
        'location': (-110, 30),
        'width': 180, # optional
        'inputs': {
            'U Scale Exponent': 0,
            'V Scale Exponent': 0,
            'Wrap U': True,
            'Wrap V': True,
            'Mirror U': False,
            'Mirror V': False,
        },
        'hide-inputs': [
            'U Scale Exponent Float',
            'V Scale Exponent Float',
            'Wrap U (0/1)',
            'Wrap V (0/1)',
            'Mirror U (0/1)',
            'Mirror V (0/1)',
            'Pixels along U',
            'Pixels along V',
        ],
        'links': {
            'UV': ('OBJEX_TransformUV_Main', 'UV'),
        },
    },
    'OBJEX_TransformUV1': {
        'group': 'OBJEX_UV_pipe',
        'label': 'UV transform 1',
        'location': (-110, -270),
        'width': 180,
        'inputs': {
            'U Scale Exponent': 0,
            'V Scale Exponent': 0,
            'Wrap U': True,
            'Wrap V': True,
            'Mirror U': False,
            'Mirror V': False,
        },
        'hide-inputs': [
            'U Scale Exponent Float',
            'V Scale Exponent Float',
            'Wrap U (0/1)',
            'Wrap V (0/1)',
            'Mirror U (0/1)',
            'Mirror V (0/1)',
            'Pixels along U',
            'Pixels along V',
        ],
        'links': {
            'UV': ('OBJEX_TransformUV_Main', 'UV'),
        },
    },
    'OBJEX_PrimColorRGB': {
        'type': 'ShaderNodeRGB',
        'label': 'Primitive Color RGB',
        'location': (100, 450),
        'outputs': { # optional, output_socket_key: default_value
            0: (1,1,1,1),
        },
    },
    'OBJEX_EnvColorRGB': {
        'type': 'ShaderNodeRGB',
        'label': 'Environment Color RGB',
        'location': (100, 250),
        'outputs': {
            0: (1,1,1,1),
        },
    },
    'OBJEX_Texel0Texture': {
        'type': 'ShaderNodeTexture' if hasattr(bpy.types, 'ShaderNodeTexture') else 'ShaderNodeTexImage',
        'label': 'Texel 0 Texture',
        'location': (100, 50),
        'links': {
            0: ('OBJEX_TransformUV0', 0),
        },
    },
    'OBJEX_Texel1Texture': {
        'type': 'ShaderNodeTexture' if hasattr(bpy.types, 'ShaderNodeTexture') else 'ShaderNodeTexImage',
        'label': 'Texel 1 Texture',
        'location': (100, -250),
        'links': {
            0: ('OBJEX_TransformUV1', 0),
        },
    },
    'OBJEX_PrimColor': {
        'group': 'OBJEX_rgba_pipe',
        'label': 'Primitive Color',
        'location': (300, 400),
        'outputs-combiner-flags': { # optional, output_socket_key: (colorCycleFlag, alphaCycleFlag)
            0: ('G_CCMUX_PRIMITIVE', None),
            1: ('G_CCMUX_PRIMITIVE_ALPHA', 'G_ACMUX_PRIMITIVE'),
        },
        'links': {
            0: ('OBJEX_PrimColorRGB', 0),
        },
    },
    'OBJEX_EnvColor': {
        'group': 'OBJEX_rgba_pipe',
        'label': 'Environment Color',
        'location': (300, 250),
        'outputs-combiner-flags': {
            0: ('G_CCMUX_ENVIRONMENT', None),
            1: ('G_CCMUX_ENV_ALPHA', 'G_ACMUX_ENVIRONMENT'),
        },
        'links': {
            0: ('OBJEX_EnvColorRGB', 0),
        },
    },
    'OBJEX_Texel0': {
        'group': 'OBJEX_rgba_pipe',
        'label': 'Texel 0',
        'location': (300, 100),
        'outputs-combiner-flags': {
            0: ('G_CCMUX_TEXEL0', None),
            1: ('G_CCMUX_TEXEL0_ALPHA', 'G_ACMUX_TEXEL0'),
        },
        'links': {
            0: ('OBJEX_Texel0Texture', 1),
            1: ('OBJEX_Texel0Texture', 0),
        },
    },
    'OBJEX_Texel1': {
        'group': 'OBJEX_rgba_pipe',
        'label': 'Texel 1',
        'location': (300, -50),
        'outputs-combiner-flags': {
            0: ('G_CCMUX_TEXEL1', None),
            1: ('G_CCMUX_TEXEL1_ALPHA', 'G_ACMUX_TEXEL1'),
        },
        'links': {
            0: ('OBJEX_Texel1Texture', 1),
            1: ('OBJEX_Texel1Texture', 0),
        },
    },
    'OBJEX_Shade': {
        'group': 'OBJEX_rgba_pipe',
        'label': 'Shade',
        'location': (300, -200),
        'outputs-combiner-flags': {
            0: ('G_CCMUX_SHADE', None),
            1: ('G_CCMUX_SHADE_ALPHA', 'G_ACMUX_SHADE'),
        },
    },
    'OBJEX_Color0': {
        'group': 'OBJEX_Color0',
        'label': 'Color 0',
        'location': (300, -350),
        'outputs-combiner-flags': {
            0: ('G_CCMUX_0', 'G_ACMUX_0'),
        },
    },
    'OBJEX_Color1': {
        'group': 'OBJEX_Color1',
        'label': 'Color 1',
        'location': (300, -430),
        'outputs-combiner-flags': {
            0: ('G_CCMUX_1', 'G_ACMUX_1'),
        },
    },
    'OBJEX_ColorCycle0': {
        'group': 'OBJEX_Cycle',
        'label': 'Color Cycle 0',
        'location': (500, 250),
        'width': 160,
        'outputs-combiner-flags': {
            0: ('G_CCMUX_COMBINED', None),
        },
        'properties-dict': { # optional, key: value -> node[key] = value
            'cycle': CYCLE_COLOR,
        },
    },
    'OBJEX_ColorCycle1': {
        'group': 'OBJEX_Cycle',
        'label': 'Color Cycle 1',
        'location': (750, 250),
        'width': 160,
        'properties-dict': {
            'cycle': CYCLE_COLOR,
        },
    },
    'OBJEX_AlphaCycle0': {
        'group': 'OBJEX_Cycle',
        'label': 'Alpha Cycle 0',
        'location': (500, -50),
        'width': 160,
        'outputs-combiner-flags': {
            0: ('G_CCMUX_COMBINED_ALPHA', 'G_ACMUX_COMBINED'),
        },
        'properties-dict': {
            'cycle': CYCLE_ALPHA,
        },
    },
    'OBJEX_AlphaCycle1': {
        'group': 'OBJEX_Cycle',
        'label': 'Alpha Cycle 1',
        'location': (750, -50),
        'width': 160,
        'properties-dict': {
            'cycle': CYCLE_ALPHA,
        },
    },
    'Output': {
        'type': 'ShaderNodeOutput' if hasattr(bpy.types, 'ShaderNodeOutput') else 'ShaderNodeOutputMaterial',
        'location': (1000, 100),
    },
    # frames
    'OBJEX_Frame_CombinerInputs': {
        'type': 'NodeFrame',
        'label': 'Combiner Inputs',
        'children': ('OBJEX_PrimColor', 'OBJEX_EnvColor', 'OBJEX_Texel0', 'OBJEX_Texel1', 'OBJEX_Shade', 'OBJEX_Color0', 'OBJEX_Color1'),
    },
}

if hasattr(bpy.types, 'ShaderNodeUVMap'): # 2.80+
    node_setup['UV Map'] = {
        'type': 'ShaderNodeUVMap',
        'location': (-520, 50),
    }
    node_setup['OBJEX_TransformUV_Main']['links']['UV'] = ('UV Map', 'UV')

if not hasattr(bpy.types, 'ShaderNodeTexture'): # 2.80+
    # ShaderNodeTexImage sockets are Color then Alpha, not Alpha ("Value") then Color like on old ShaderNodeTexture
    for node_texel_texture, node_texel in (
        ('OBJEX_Texel0Texture', 'OBJEX_Texel0'),
        ('OBJEX_Texel1Texture', 'OBJEX_Texel1'),
    ):
        for i in (0,1,):
            node_setup[node_texel]['links'][i] = (node_texel_texture, i)
    # ShaderNodeTexImage is larger
    for node_name in (
        'UV Map', 'Geometry',
        'OBJEX_TransformUV_Main',
        'OBJEX_TransformUV0', 'OBJEX_TransformUV1',
        'OBJEX_Texel0Texture', 'OBJEX_Texel1Texture',
    ):
        if node_name in node_setup:
            x, y = node_setup[node_name]['location']
            node_setup[node_name]['location'] = x - 100, y

if not hasattr(bpy.types, 'ShaderNodeOutput'): # 2.80+
    # add principled bsdf shader before ShaderNodeOutputMaterial
    node_setup['Principled BSDF'] = {
        'type': 'ShaderNodeBsdfPrincipled',
        'location': (1000,300),
    }
    x, y = node_setup['Output']['location']
    node_setup['Output']['location'] = x + 300, y
    node_setup['Output']['links'] = {'Surface': ('Principled BSDF', 0)}
