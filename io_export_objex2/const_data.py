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
