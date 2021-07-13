#  Copyright 2020-2021 Dragorn421, Rankaisija
#
#  This objex2 addon is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This objex2 addon is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this objex2 addon.  If not, see <https://www.gnu.org/licenses/>.

from . import blender_version_compatibility

import bpy

from . import interface
from .logging_util import getLogger

# scene

class SavedPoseBone(bpy.types.PropertyGroup):
    bone_name = bpy.props.StringProperty()
    location = bpy.props.FloatVectorProperty(size=3)
    rotation_quaternion = bpy.props.FloatVectorProperty(size=4)

class SavedPose(bpy.types.PropertyGroup):
    name = bpy.props.StringProperty()
    type = bpy.props.EnumProperty(
            items=[
                ('UNFOLDEDpose_foldedRest','','',1),
                ('foldedPose_UNFOLDEDrest','','',2),
            ],
            default='UNFOLDEDpose_foldedRest'
        )
    bones = bpy.props.CollectionProperty(type=SavedPoseBone)

class ObjexSceneProperties(bpy.types.PropertyGroup):
    is_objex_scene = bpy.props.BoolProperty()

    colorspace_strategy = bpy.props.EnumProperty(
        # if modifying these items, also edit __init__.OBJEX_AddonPreferences.colorspace_default_strategy
        items=[
            ('QUIET','Do nothing + silence',
                'Do nothing and do not warn about using a non-linear color space.',1),
            ('WARN','Warn non-linear',
                'Warn on export about using a non-linear color space.',2),
        ],
        name='Color Space Strategy',
        description='How to handle color spaces in the scene',
    )

    sync_backface_culling = bpy.props.EnumProperty(
        items=[
            ('BLENDER_TO_OBJEX','Blender -> Objex',
                'Change backface culling property of an objex material when '
                'its Blender backface culling material property changes.',1 << 0),
            ('OBJEX_TO_BLENDER','Objex -> Blender',
                'Change Blender backface culling material property of a '
                'material when its objex backface culling property changes.',1 << 1),
        ],
        name='Sync Backface Culling',
        description='How to sync the two backface culling properties, the one in vanilla Blender and the objex one',
        options={'ENUM_FLAG'},
        default={'BLENDER_TO_OBJEX','OBJEX_TO_BLENDER'},
    )

    write_primitive_color = bpy.props.BoolProperty(
            name='Set prim color (global)',
            description='Scene property, shared by materials',
            default=True
        )
    write_environment_color = bpy.props.BoolProperty(
            name='Set env color (global)',
            description='Scene property, shared by materials',
            default=True
        )

    saved_poses = bpy.props.CollectionProperty(type=SavedPose)


# mesh

class ObjexMeshProperties(bpy.types.PropertyGroup):
    priority = bpy.props.IntProperty(
            name='Priority',
            description='Meshs with higher priority are written first',
            default=0
        )
    write_origin = bpy.props.EnumProperty(
            items=[
                ('YES','Yes','Write origin',1),
                ('NO','No','Do not write origin',2),
                ('AUTO','Auto','Write origin if mesh uses billboarding, do not otherwise',3)
            ],
            name='Origin',
            description='Export object location in world space.\n'
                        'Used by zzconvert to translate the mesh coordinates back, as if object had its location at world origin.',
            default='AUTO'
        )
    attrib_billboard = bpy.props.EnumProperty(
            items=[
                ('BBMTXS','Spherical','include spherical billboard matrix in Dlist',1),
                ('BBMTXC','Cylindrical','include cylindrical billboard matrix in Dlist',2),
                ('NONE','None','No billboarding',3)
            ],
            name='Billboard',
            description='Billboard type',
            default='NONE'
        )

# 421todo copied straight from specs, may want to improve wording / properties names
for attrib, desc in (
    ('LIMBMTX', 'include explicit limb matrix at start of Dlist'),
    ('POSMTX', 'include world positioning matrix at start of Dlist'),
    ('NOSPLIT', 'do not divide mesh by bones (and do not write skeleton)'),
    ('NOSKEL', 'do not write a skeleton to the generated zobj'),
    ('PROXY', 'write a proxy Dlist (will have _PROXY suffix)\n'
        'in the case of a divided mesh, a proxy is written for each Dlist, and a C array is generated\n'
        'if NOSKEL is not present (if a skeleton is written), that C array data is also written to zobj at PROXY_ offset and the skeleton points to that table\n'
        'in play-as data, display list pointers point to the proxy for each instead of the real display list'),
):
    setattr(ObjexMeshProperties, 'attrib_%s' % attrib,
        bpy.props.BoolProperty(
            name=attrib,
            description=desc,
            default=False
    ))


# armature

class ObjexArmatureExportActionsItem(bpy.types.PropertyGroup):
    action = bpy.props.PointerProperty(
            type=bpy.types.Action,
            name='Action',
            description='',
            update=interface.armature_export_actions_change
        )

class ObjexArmatureProperties(bpy.types.PropertyGroup):
    export_all_actions = bpy.props.BoolProperty(
            name='Export all actions',
            description='',
            default=True,
            update=interface.armature_export_actions_change
        )
    export_actions_active = bpy.props.IntProperty()
    export_actions = bpy.props.CollectionProperty(
            type=ObjexArmatureExportActionsItem,
            name='Actions',
            description=''
        )
    
    type = bpy.props.EnumProperty(
            items=[
                ('z64player','z64player','',1),
                ('z64npc','z64npc','',2),
                ('z64dummy','z64dummy','',3),
                ('NONE','','',4)
            ],
            name='Type',
            description='',
            default='NONE'
        )
    
    pbody = bpy.props.BoolProperty(
            name='Physics Body',
            description='',
            default=False
        )
    pbody_parent_object = bpy.props.PointerProperty(
            type=bpy.types.Object,
            name='Parent Object',
            description='Optional'
        )
    pbody_parent_bone = bpy.props.StringProperty(
            name='Parent Bone',
            description=''
        )
    
    segment = bpy.props.StringProperty(
            name='Segment',
            description='Hexadecimal'
        )
    segment_local = bpy.props.BoolProperty(
            name='Local',
            description='',
            default=False
        )

    fold_unfold_saved_pose_index = bpy.props.IntProperty()

# material

class ObjexMaterialCollisionProperties(bpy.types.PropertyGroup):
    WATERBOX = bpy.props.BoolProperty()
    # 421todo WATERBOX properties
    ignore_camera = bpy.props.BoolProperty(
            name='Ignore Camera',
            description='Camera can pass through',
            default=False
        )
    ignore_entity = bpy.props.BoolProperty(
            name='Ignore Entities',
            description='Player, enemies... can pass through',
            default=False
        )
    ignore_ammo = bpy.props.BoolProperty(
            name='Ignore Ammos',
            description='Deku seeds, arrows, bombchus... can pass through',
            default=False
        )
    sound = bpy.props.EnumProperty(
            items=[
                ('UNSET',             '',                                         '',  0),
                ('SOUND_DIRT',        'Earth/Dirt',                               '',  1),
                ('SOUND_DIRT_LOOSE',  'Loose Earth/Dirt',                         '',  2),
                ('SOUND_GRASS',       'Underbrush/Grass',                         '',  3),
                ('SOUND_SAND',        'Sand',                                     '',  4),
                ('SOUND_WOOD',        'Wooden',                                   '',  5),
                ('SOUND_WOOD_STRUCK', 'Packed Earth/Wood (struck: wooden sound)', '',  6),
                ('SOUND_STONE',       'Stone',                                    '',  7),
                ('SOUND_STONE_WET',   'Stone (wet)',                              '',  8),
                ('SOUND_CERAMIC',     'Ceramic',                                  '',  9),
                ('SOUND_SPLASH',      'Shallow water',                            '', 10),
                ('SOUND_SPLASH_1',    'Shallow water (lower-pitched)',            '', 11),
                ('SOUND_LAVA',        'Lava/Goo',                                 '', 12),
                ('SOUND_DIRT_1',      'Earth/Dirt (duplicate 1)',                 '', 13),
                ('SOUND_DIRT_2',      'Earth/Dirt (duplicate 2)',                 '', 14),
                ('SOUND_DIRT_3',      'Earth/Dirt (duplicate 3)',                 '', 15),
                ('SOUND_DIRT_4',      'Earth/Dirt (duplicate 4)',                 '', 16),
            ],
            name='Sound',
            description='Sound used when walking on or hitting the collision.\n'
                        'Unless otherwise stated, the sound made when struck with a sword is the default metallic one',
            default='UNSET'
        )
    floor = bpy.props.EnumProperty(
            items=[
                ('UNSET',            '',              '',                                                             0),
                ('FLOOR_VOID_SCENE', 'Void to Scene', 'Void out to the last scene entered',                           1),
                ('FLOOR_VOID_ROOM',  'Void to Room',  'Void out to the last room entered',                            2),
                ('FLOOR_JUMP_VINE',  'Climb (vines)', 'Instead of jumping, climb down',                               3),
                ('FLOOR_JUMP_HANG',  'Grab ledge',    'Instead of jumping, hang from ledge',                          4),
                ('FLOOR_JUMP_FALL',  'Step off',      'Instead of jumping, step off the platform into falling state', 5),
                ('FLOOR_JUMP_DIVE',  'Dive',          'Instead of jumping, activate diving animation/state',          6),
            ],
            name='Floor',
            default='UNSET'
        )
    wall = bpy.props.EnumProperty(
            items=[
                ('UNSET',           '',            '',                                                       0),
                ('WALL_BARRIER',    'No Grab',     'Link will not jump over or attempt to climb the wall,\n'
                                                   'even if the wall is short enough for these actions',     1),
                ('WALL_LADDER',     'Ladder',      '',                                                       2),
                ('WALL_LADDER_TOP', 'Ladder Top',  'Makes Link climb down onto a ladder',                    3),
                ('WALL_VINES',      'Vines',       'Climbable vine wall',                                    4),
                ('WALL_CRAWL',      'Crawl',       'Wall used to activate/deactivate crawling',              5),
                ('WALL_CRAWL_1',    'Crawl 1',     'Difference from Crawl unknown',                          6),
                ('WALL_PUSHBLOCK',  'Pushblock',   '',                                                       7),
            ],
            name='Wall',
            default='UNSET'
        )
    special = bpy.props.EnumProperty(
            items=[
                ('UNSET', '', '', 0),
                # floor
                ('FLOOR_LAVA',       'Lava',                '',                                                    1),
                ('FLOOR_LAVA_1',     'Lava 1',              'Difference from Lava unknown',                        2),
                ('FLOOR_SAND',       'Sand',                '',                                                    3),
                ('FLOOR_ICE',        'Ice',                 '',                                                    4),
                ('FLOOR_NOFALLDMG',  'No Fall Damage',      '',                                                    5),
                ('FLOOR_QUICKHORSE', 'Quicksand (horse)',   'Quicksand, passable on horseback',                    6),
                ('FLOOR_QUICKSAND',  'Quicksand (no horse)','Quicksand, NOT passable on horseback',                7),
                ('SPECIAL_LOOKUP',   'Look Up',             'Makes the player look upwards when standing on it',   8),
                # wall
                ('SPECIAL_BLEEDWALL','Bleed Wall',          'Spawns "blood" particles when struck, special sound'
                                                            'when struck with sword (used in Jabu-Jabu\'s Belly)', 9),
                # other
                ('SPECIAL_INSTAVOID','Instavoid',           'Instantly void out on contact',                       10),
            ],
            name='Special',
            default='UNSET'
        )
    horse = bpy.props.BoolProperty(
            name='Horse',
            description='Epona can walk on the polygon',
            default=True
        )
    one_lower = bpy.props.BoolProperty(
            name='1 Lower',
            description='Sink 1 unit into the ground',
            default=False
        )
    wall_damage = bpy.props.BoolProperty(
            name='Wall Damage',
            default=False
        )
    hookshot = bpy.props.BoolProperty(
            name='Hookshot',
            default=False
        )
    steep = bpy.props.BoolProperty(
            name='Steep',
            description='Steep Surface (makes the player slide)',
            default=False
        )
    warp_enabled = bpy.props.BoolProperty(
            name='Exit',
            description='Scene exit to warp somewhere',
            default=False
        )
    warp_exit_index = bpy.props.IntProperty(
            name='Exit Index',
            description='0-indexes into the scene exit table',
            default=0
        )
    camera_enabled = bpy.props.BoolProperty(
            name='Camera',
            description='Use a specific camera',
            default=False
        )
    camera_index = bpy.props.IntProperty(
            name='Camera Index',
            default=False
        )
    echo_enabled = bpy.props.BoolProperty(
            name='Echo',
            default=False
        )
    echo_index = bpy.props.IntProperty(
            name='Echo Index',
            default=False
        )
    lighting_enabled = bpy.props.BoolProperty(
            name='Lighting',
            default=False
        )
    lighting_index = bpy.props.IntProperty(
            name='Lighting Index',
            default=False
        )
    conveyor_enabled = bpy.props.BoolProperty(
            name='Conveyor Surface',
            description='',
            default=False
        )
    # 421todo conveyor_outside_water
    conveyor_direction = bpy.props.IntProperty(
            name='Direction',
            description='Conveyor direction in degrees',
            min=0, max=360,
            default=0
        )
    conveyor_speed = bpy.props.EnumProperty(
            items=[
                ('NONE',    'None',     '', 0),
                ('SLOW',    'Slow',     '', 1),
                ('MEDIUM',  'Medium',   '', 2),
                ('FAST',    'Fast',     '', 3),
            ],
            name='Speed',
            default='NONE'
        )
    conveyor_inherit = bpy.props.BoolProperty(
            name='Inherit',
            description='Inherit speed from previously stepped-on conveyor surface',
            default=False
        )

class ObjexMaterialProperties(bpy.types.PropertyGroup):
    is_objex_material = bpy.props.BoolProperty(default=False)
    objex_version = bpy.props.IntProperty(default=0) # see data_updater.py

    # Use this material as display properties
    use_display = bpy.props.BoolProperty(
            default=True
        )
    # Use this material as collision properties
    use_collision = bpy.props.BoolProperty(
            default=False
        )

    collision = bpy.props.PointerProperty(
            type=ObjexMaterialCollisionProperties
        )

    backface_culling = bpy.props.BoolProperty(
            name='Cull backfaces',
            description='Culls the back face of geometry',
            update=interface.objex_backface_culling_update,
            default=True
        )
    frontface_culling = bpy.props.BoolProperty(
            name='Cull frontfaces',
            description='Culls the front face of geometry',
            default=False
        )
    write_primitive_color = bpy.props.EnumProperty(
            items=[
                ('YES','Yes','Set the color',1),
                ('NO','No','Do not set the color',2),
                ('GLOBAL','Follow global','Default to the global (per-scene) setting, shared by all materials',3),
            ],
            name='Set prim color',
            description='Set the primitive color in the generated display list (macro gsDPSetPrimColor).\n'
                        'Disabling this can for example allow to set a dynamic primitive color from code or from another display list',
            default='GLOBAL'
        )
    write_environment_color = bpy.props.EnumProperty(
            items=[
                ('YES','Yes','Set the color',1),
                ('NO','No','Do not set the color',2),
                ('GLOBAL','Follow global','Default to the global (per-scene) setting, shared by all materials',3),
            ],
            name='Set env color',
            description='Same as "Set prim color" for the environment color (macro gsDPSetEnvColor)',
            default='GLOBAL'
        )

    rendermode_blender_flag_AA_EN = bpy.props.BoolProperty(
            name='AA_EN',
            description='AA_EN\n' 'Enable anti-aliasing?',
            default=True
        )
    rendermode_blender_flag_Z_CMP = bpy.props.BoolProperty(
            name='Z_CMP',
            description='Z_CMP\n' 'Use Z buffer',
            default=True
        )
    rendermode_blender_flag_Z_UPD = bpy.props.BoolProperty(
            name='Z_UPD',
            description='Z_UPD\n' 'Update Z buffer',
            default=True
        )
    rendermode_blender_flag_IM_RD = bpy.props.BoolProperty(
            name='IM_RD',
            description='IM_RD\n' '? see CloudModding wiki',
            default=True
        )
    rendermode_blender_flag_CLR_ON_CVG = bpy.props.BoolProperty(
            name='CLR_ON_CVG',
            description='CLR_ON_CVG\n' '? see CloudModding wiki',
            default=False
        )
    rendermode_blender_flag_CVG_DST_ = bpy.props.EnumProperty(
            items=[
                ('CVG_DST_CLAMP','CLAMP','CVG_DST_CLAMP',1),
                ('CVG_DST_WRAP','WRAP','CVG_DST_WRAP',2),
                ('CVG_DST_FULL','FULL','CVG_DST_FULL',3),
                ('CVG_DST_SAVE','SAVE','CVG_DST_SAVE',4),
                ('AUTO','Auto','Defaults to CVG_DST_CLAMP (for now)',5),
            ],
            name='CVG_DST_',
            description='? see CloudModding wiki',
            default='AUTO'
        )
    rendermode_zmode = bpy.props.EnumProperty(
            items=[
                ('OPA','Opaque','Opaque surfaces (OPA)',1),
                ('INTER','Interpenetrating','Interpenetrating surfaces',2),
                ('XLU','Translucent','Translucent surfaces (XLU)',3),
                ('DEC','Decal','Decal surfaces (eg paths)',4),
                ('AUTO','Auto','Default to Translucent (XLU) if material uses transparency, or Opaque (OPA) otherwise',5),
            ],
            name='zmode',
            description='Not well understood, has to do with rendering order',
            default='AUTO'
        )
    rendermode_blender_flag_CVG_X_ALPHA = bpy.props.EnumProperty(
            items=[
                ('YES','Set','Set CVG_X_ALPHA',1),
                ('NO','Clear','Clear CVG_X_ALPHA',2),
                ('AUTO','Auto','Set if the material uses transparency, clear otherwise',3), # 421fixme research this
            ],
            name='CVG_X_ALPHA',
            description='CVG_X_ALPHA\n' '? see CloudModding wiki',
            default='AUTO'
        )
    rendermode_blender_flag_ALPHA_CVG_SEL = bpy.props.BoolProperty(
            name='ALPHA_CVG_SEL',
            description='ALPHA_CVG_SEL\n' '? see CloudModding wiki',
            default=True # 421fixme does enabling this kill alpha?
        )
    rendermode_forceblending = bpy.props.EnumProperty(
            items=[
                ('YES','Always','Force blending',1),
                ('NO','Never','Do not force blending',2),
                ('AUTO','Auto','Force blending if the material uses Alpha Blend transparency',3),
            ],
            name='Force blending',
            description='Not well understood, related to transparency and rendering order',
            default='AUTO'
        )
    rendermode_blending_cycle0 = bpy.props.EnumProperty(
            items=[
                ('FOG_PRIM','Fog RGBA','Blend with fog color and alpha (G_RM_FOG_PRIM_A)',1),  # G_BL_CLR_FOG   G_BL_A_FOG     G_BL_CLR_IN    G_BL_1MA
                ('FOG_SHADE','Fog RGB, shade A','Blend with fog color and shade alpha (shade from combiner cycles) (G_RM_FOG_SHADE_A)',2),  # G_BL_CLR_FOG   G_BL_A_SHADE   G_BL_CLR_IN    G_BL_1MA
                ('PASS','Pass','Let the input pixel color through unaltered (G_RM_PASS...)',3), # G_BL_CLR_IN    G_BL_0         G_BL_CLR_IN    G_BL_1
                ('OPA','OPA-like','Blend with the buffer\nCycle settings mainly used with OPA',4), # G_BL_CLR_IN    G_BL_A_IN      G_BL_CLR_MEM   G_BL_A_MEM
                ('XLU','XLU-like','Blend with the buffer\nCycle settings mainly used with XLU',5), # G_BL_CLR_IN    G_BL_A_IN      G_BL_CLR_MEM   G_BL_1MA
                ('AUTO','Auto', 'Use "Pass" if material uses Alpha Clip transparency,\n'
                                '"XLU-like" if material uses Alpha Blend transparency,\n'
                                'and "Fog RGB, shade A" otherwise.',6),
                ('CUSTOM','Custom','Define a custom blending cycle',7),
            ],
            name='First blending cycle',
            description='First cycle\nHow to blend the pixels being rendered with the frame buffer\nResponsible for at least transparency effects and fog',
            default='AUTO'
        )
    rendermode_blending_cycle1 = bpy.props.EnumProperty(
            items=[
                ('OPA','OPA-like','Blend with the buffer\nCycle settings mainly used with OPA',1), # G_BL_CLR_IN    G_BL_A_IN      G_BL_CLR_MEM   G_BL_A_MEM
                ('XLU','XLU-like','Blend with the buffer\nCycle settings mainly used with XLU',2), # G_BL_CLR_IN    G_BL_A_IN      G_BL_CLR_MEM   G_BL_1MA
                ('AUTO','Auto','XLU-like if material uses transparency, OPA-like otherwise',3),
                ('CUSTOM','Custom','Define a custom blending cycle',4),
            ],
            name='Second blending cycle',
            description='Second cycle\nHow to blend the pixels being rendered with the frame buffer\nResponsible for at least transparency effects and fog',
            default='AUTO'
        )

    standalone = bpy.props.BoolProperty(
            name='Standalone',
            description='Write the display list for this material once, and use 0xDE G_DL commands to branch to it every use',
            default=False
        )
    empty = bpy.props.BoolProperty(
            name='Empty',
            description='Do not write any geometry using this material',
            default=False
        )
    branch_to_object = bpy.props.PointerProperty(
            type=bpy.types.Object,
            name='Branch to',
            description='Jump to the display list of another object',
            poll=lambda self, object: object.type == 'MESH'
        )
    branch_to_object_bone = bpy.props.StringProperty(
            name='Branch to bone',
            description='Jump to the display list for a bone'
        )
    vertex_shading = bpy.props.EnumProperty(
            items=[
                ('AUTO','Auto','Colors only or normals only, depending on the node setup',1),
                ('DYNAMIC','Dynamic','Use normals where vertex colors are opaque white (1,1,1,1), and vertex colors otherwise',2),
            ],
            name='Shading',
            description='What shade data should be written for each vertex',
            default='AUTO'
        )
    external_material_segment = bpy.props.StringProperty(
    		name='Pointer',
    		description='Branch material to segment'
    	)
    force_write = bpy.props.BoolProperty(
            name='Force write',
            description='Write this material even if it is not used',
            default=False
        )
    priority = bpy.props.IntProperty(
            name='Priority',
            description='Geometry using materials with higher priority is written first',
            default=0
        )
    geometrymode_G_FOG = bpy.props.EnumProperty(
            items=[
                ('YES','Set','Set G_FOG',1),
                ('NO','Clear','Clear G_FOG',2),
                ('AUTO','Auto','Set if blending uses G_BL_CLR_FOG or G_BL_A_FOG, clear otherwise',3), # I am only assuming this is good practice
            ],
            name='G_FOG',
            description='G_FOG\n' '? see CloudModding wiki, has to do with computing fog values\n' 'THIS DOES NOT DISABLE FOG, use the blending cycle settings for that purpose',
            default='AUTO'
        )
    geometrymode_G_ZBUFFER = bpy.props.BoolProperty(
            name='Z buffer',
            description='G_ZBUFFER\n' 'Enable Z buffer calculations',
            default=True
        )
    geometrymode_G_SHADING_SMOOTH = bpy.props.BoolProperty(
            name='Smooth Shading',
            description='G_SHADING_SMOOTH\n' 'Enable smooth shading (vertex colors, lighting)',
            default=True
        )

# add rendermode_blending_cycle%d_custom_%s properties to ObjexMaterialProperties for each cycle 0,1 and each variable P,A,M,B
for c in (0,1):
    for v,choices,d in (
    # variable   choices                                                     default
        ('P', ('G_BL_CLR_IN','G_BL_CLR_MEM','G_BL_CLR_BL','G_BL_CLR_FOG'), 'G_BL_CLR_IN'),
        ('A', ('G_BL_A_IN','G_BL_A_FOG','G_BL_A_SHADE','G_BL_0'),          'G_BL_A_IN'),
        ('M', ('G_BL_CLR_IN','G_BL_CLR_MEM','G_BL_CLR_BL','G_BL_CLR_FOG'), 'G_BL_CLR_MEM'),
        ('B', ('G_BL_1MA','G_BL_A_MEM','G_BL_1','G_BL_0'),                 'G_BL_1MA')
    ):
        setattr(ObjexMaterialProperties, 'rendermode_blending_cycle%d_custom_%s' % (c,v), bpy.props.EnumProperty(
            items=[(choices[i],choices[i],'',i+1) for i in range(4)],
            name='%s' % v,
            default=d
        ))

# images

class ObjexImageProperties(bpy.types.PropertyGroup):
    format = bpy.props.EnumProperty(
            items=[
                # number identifiers are 0xFS with F~G_IM_FMT_ and S~G_IM_SIZ_
                ('I4','I4','Greyscale shared with alpha, 16 values (AAAA)',0x40),
                ('I8','I8','Greyscale shared with alpha, 256 values (AAAA AAAA)',0x41),
                ('IA4','IA4','Greyscale 8 values and alpha on/off (CCCA)',0x30),
                ('IA8','IA8','Distinct greyscale and alpha, 16 values each (CCCC AAAA)',0x31),
                ('IA16','IA16','Distinct greyscale and alpha, 256 values each (CCCC CCCC AAAA AAAA)',0x32),
                ('RGBA16','RGBA16','32 values per color red/green/blue, and alpha on/off (RRRR RGGG GGBB BBBA)',0x02),
                ('RGBA32','RGBA32','256 values per color red/green/blue and alpha (RRRR RRRR GGGG GGGG BBBB BBBB AAAA AAAA)',0x03),
                ('CI4','CI4','Paletted in 16 colors',0x20),
                ('CI8','CI8','Paletted in 256 colors',0x21),
                ('AUTO','Auto','Do not specify a format',0xFF),
            ],
            name='Format',
            description='What format to use when writing the texture',
            default='AUTO'
        )
    palette = bpy.props.IntProperty(
            name='Palette',
            description='Palette slot to use (0 for automatic)\nSeveral paletted textures (CI format) may use the same palette slot to save space',
            min=0,
            soft_max=255, # todo ?
            default=0
        )
    alphamode = bpy.props.EnumProperty(
            items=[
                ('AUTO','Auto','Defaults to edge if format is not I (greyscale shared with alpha)',0),
                ('edge','Edge','Color is taken from visible edges',1),
                ('average','Average','Use average of all visible colors',2),
                ('white','White','Use white',3),
                ('black','Black','Use black',4),
                ('image','Image','Use colors as they are in the input image.\n'
                                '(falls back to Edge on CI formats (paletted) if there are more than four unique invisible colors)',5),
            ],
            name='Alpha',
            description='What color to write for fully transparent pixels.\n'
                        '(color of such pixels can indeed still show due to not-nearest-neighbour texture filtering)',
            default='AUTO'
        )
    pointer = bpy.props.StringProperty(
            name='Pointer',
            description='The address that should be used when referencing this texture',
            default=''
        )
    priority = bpy.props.IntProperty(
            name='Priority',
            description='Textures with higher priority are written first',
            default=0
        )
    force_write = bpy.props.EnumProperty(
            items=[
                ('FORCE_WRITE','Always','Force the texture to be written',1),
                ('DO_NOT_WRITE','Never','Force the texture to NOT be written',2),
                ('UNSPECIFIED','If used','Texture will be written if it is used',3),
            ],
            name='Write',
            description='Explicitly state to write or to not write the image',
            default='UNSPECIFIED'
        )
    texture_bank = bpy.props.PointerProperty(
            type=bpy.types.Image,
            name='Bank',
            description='Image data to write instead of this texture, useful for dynamic textures (eyes, windows)'
        )


classes = (
    SavedPoseBone,
    SavedPose,

    ObjexSceneProperties,

    ObjexMeshProperties,

    ObjexArmatureExportActionsItem,
    ObjexArmatureProperties,

    ObjexMaterialCollisionProperties,
    ObjexMaterialProperties,

    ObjexImageProperties,
)

def register_properties():
    log = getLogger('properties')
    for clazz in classes:
        try:
            blender_version_compatibility.adapt_ID_PointerProperty(clazz)
            blender_version_compatibility.make_annotations(clazz)
            bpy.utils.register_class(clazz)
        except:
            log.exception('Failed to register {!r}', clazz)
            raise
    bpy.types.Scene.objex_bonus = bpy.props.PointerProperty(type=ObjexSceneProperties)
    bpy.types.Mesh.objex_bonus = bpy.props.PointerProperty(type=ObjexMeshProperties)
    bpy.types.Armature.objex_bonus = bpy.props.PointerProperty(type=ObjexArmatureProperties)
    bpy.types.Material.objex_bonus = bpy.props.PointerProperty(type=ObjexMaterialProperties)
    bpy.types.Image.objex_bonus = bpy.props.PointerProperty(type=ObjexImageProperties)

def unregister_properties():
    del bpy.types.Scene.objex_bonus
    del bpy.types.Mesh.objex_bonus
    del bpy.types.Armature.objex_bonus
    del bpy.types.Material.objex_bonus
    del bpy.types.Image.objex_bonus
    for clazz in reversed(classes):
        try:
            bpy.utils.unregister_class(clazz)
        except:
            log.exception('Failed to unregister {!r}', clazz)
