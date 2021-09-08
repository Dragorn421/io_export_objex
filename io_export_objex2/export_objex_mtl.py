#  Copyright 2020 Campbell Barton, Bastien Montagne
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

import os

import bpy
import bpy_extras.io_utils
try:
    # 2.80+
    import bpy_extras.node_shader_utils
except ImportError: # < 2.80
    pass

from . import const_data as CST
from . import data_updater
from . import util
from .logging_util import getLogger

def write_mtl(scene, filepath, append_header, options, copy_set, collected_materials, face_image_materials):
    log = getLogger('export_objex_mtl')

    source_dir = os.path.dirname(bpy.data.filepath)
    dest_dir = os.path.dirname(filepath)
    path_mode = options['PATH_MODE']
    export_packed_images = options['EXPORT_PACKED_IMAGES']
    export_packed_images_dir = options['EXPORT_PACKED_IMAGES_DIR']

    warned_about_image_color_space = set()

    with open(filepath, "w", encoding="utf8", newline="\n") as f:
        fw = f.write

        fw('# Blender MTL File: {!r}\n'.format(os.path.basename(bpy.data.filepath) or "None"))
        fw('# Material Count: {}\n'.format(len(collected_materials) + len(face_image_materials)))

        # used for writing exportid
        append_header(fw)

        # maps an image to (texture_name, texture_name_q),
        # to avoid duplicate newtex declarations
        # does not prevent duplicate file paths because different images
        # (with same file path) may have different properties set
        declared_textures = {}

        def getImagePath(image, filename=None):
            image_filepath = image.filepath
            if image.packed_files:
                if export_packed_images:
                    if not filename:
                        filename = '%s_%d' % (os.path.basename(image_filepath), len(declared_textures))
                    # save externally a packed image
                    image_filepath = '%s/%s' % (export_packed_images_dir, filename)
                    image_filepath = bpy.path.abspath(image_filepath)
                    log.info('Saving packed image {!r} to {}', image, image_filepath)
                    image.save_render(image_filepath)
                else:
                    log.warning('Image {!r} is packed, assuming it exists at {}', image, image_filepath)
            return bpy_extras.io_utils.path_reference(image_filepath, source_dir, dest_dir,
                                                      path_mode, '', copy_set, image.library)

        def writeTexture(image):
            data = declared_textures.get(image)
            if data:
                texture_name, texture_name_q = data
                log.trace('Skipped writing texture {} {}', texture_name, image)
            else:
                texture_name = image.name
                # make sure texture_name is not already used
                i = 0
                while texture_name in (_texture_name for _texture_name, _texture_name_q in declared_textures.values()):
                    i += 1
                    texture_name = '%s_%d' % (name, i)
                if i != 0:
                    log.debug('Texture name {} was already used, using {} instead', name, texture_name)
                texture_name_q = util.quote(texture_name)
                declared_textures[image] = (texture_name, texture_name_q)
                fw('newtex %s\n' % texture_name_q)
                filepath = getImagePath(image, texture_name)
                fw('map %s\n' % filepath)
                # texture objex data
                tod = image.objex_bonus
                if tod.pointer:
                    fw('pointer %s%s\n' % (
                        '' if tod.pointer.startswith('0x') else '0x',
                        tod.pointer
                    ))
                if tod.format != 'AUTO':
                    # zzconvert requires lower case format name
                    fw('format %s\n' % tod.format.lower())
                    if tod.format[:2] == 'CI' and tod.palette != 0:
                        fw('palette %d\n' % tod.palette)
                if tod.alphamode != 'AUTO':
                    fw('alphamode %s\n' % tod.alphamode)
                if tod.priority != 0:
                    fw('priority %d\n' % tod.priority)
                if tod.force_write == 'FORCE_WRITE':
                    fw('forcewrite\n')
                elif tod.force_write == 'DO_NOT_WRITE':
                    fw('forcenowrite\n')
                if tod.texture_bank:
                    if blender_version_compatibility.no_ID_PointerProperty:
                        texture_bank = bpy.data.images[tod.texture_bank]
                    else:
                        texture_bank = tod.texture_bank
                    texturebank_filepath = getImagePath(texture_bank)
                    fw('texturebank %s\n' % texturebank_filepath)
            # texture_name_q is input name if new texture, or
            # the name used for writing the image path (quoted)
            return texture_name_q

        # mind the continue used in this loop to skip writing most stuff for collision / empty materials
        for bl_material, cd_material in collected_materials.items():
            name = cd_material.name
            name_q = cd_material.name_q
            log.trace('Writing name={!r} name_q={!r} bl_material={!r} cd_material={!r}', name, name_q, bl_material, cd_material)
            util.detect_zztag(log, name)
            objex_data = bl_material.objex_bonus
            #if objex_data and objex_data.is_objex_material: # all collected_materials are display objex materials
            # FIXME move collision export call to write_object or smth
            """
            # checking if the prefix "collision." on the object name is consistent with
            # objex_data.use_collision is done in ObjexWriter#write_object in export_objex.py
            if objex_data.use_collision:
                fw('newmtl %s\n' % name_q)
                write_collision_material(fw, objex_data.collision)
                continue
            """
            # raises ObjexExportAbort if the material version doesn't match the current addon material version
            data_updater.assert_material_at_current_version(bl_material, util.ObjexExportAbort)
            # zzconvert detects "empty." on its own, making it explicit here doesn't hurt
            if objex_data.empty or name.startswith('empty.'):
                fw('newmtl %s\n' % name_q)
                fw('empty\n')
                if objex_data.branch_to_object: # branch_to_object is a MESH object
                    if blender_version_compatibility.no_ID_PointerProperty:
                        branch_to_object = bpy.data.objects[objex_data.branch_to_object]
                    else:
                        branch_to_object = objex_data.branch_to_object
                    # use .bone in branched-to _group if mesh is rigged and split
                    if branch_to_object.find_armature() and not branch_to_object.data.objex_bonus.attrib_NOSPLIT:
                        if not objex_data.branch_to_object_bone:
                            log.warning('No branch-to bone set for empty material {}, '
                                'but mesh object {} is rigged to {} and does not set NOSPLIT',
                                name, branch_to_object.name, branch_to_object.find_armature().name)
                        branch_to_group_path = '%s.%s' % (branch_to_object.name, objex_data.branch_to_object_bone)
                    else:
                        branch_to_group_path = branch_to_object.name
                    fw('gbi gsSPDisplayList(_group=%s)\n' % util.quote(branch_to_group_path))
                continue # empty materials do not need anything else written
            if len(cd_material.combinerFlags) != 16:
                log.error('Unexpected combiner flags amount {:d} (are both cycles used?), flags: {!r}', len(cd_material.combinerFlags), cd_material.combinerFlags)
            for texelAttr in ('texel0', 'texel1'):
                texel = getattr(cd_material, texelAttr)
                if texel is not None:
                    image = texel.image
                    if image is None:
                        raise util.ObjexExportAbort(('Material {} uses {} without a texture/image '
                            '(make sure texel0 and texel1 have a texture/image set if they are used in the combiner)'
                            ).format(name, texelAttr))
                    if (scene.objex_bonus.colorspace_strategy != 'QUIET'
                        and scene.display_settings.display_device == 'None'
                        and image.colorspace_settings.name != 'Linear'
                        and image not in warned_about_image_color_space
                    ):
                        warned_about_image_color_space.add(image)
                        log.warning(
                            'Image {} uses Color Space {!r},\n'
                            'but the scene uses display_device={!r}. This makes the preview less accurate.\n'
                            'The Color Space property can be found in{}.\n'
                            'Recommended value: Linear',
                            image.name, image.colorspace_settings.name, scene.display_settings.display_device,
                            ' the Image Editor' if bpy.app.version < (2,80,0)
                                else ':\nImage Editor, UV Editor, or on the Image Texture node'
                        )
                    texel.texture_name_q = writeTexture(image)
            # write newmtl after any newtex block
            fw('newmtl %s\n' % name_q)
            if objex_data.vertex_shading == 'DYNAMIC':
                fw('vertexshading dynamic\n')
            else: # vertex_shading == 'AUTO'
                if cd_material.shadeSource is None:
                    fw('vertexshading none\n')
                elif cd_material.shadeSource == 'NORMALS':
                    fw('vertexshading normal\n')
                elif cd_material.shadeSource == 'VERTEX_COLORS':
                    fw('vertexshading color\n')
                else:
                    raise util.ObjexExportAbort(
                        'Unknown shadeSource={} from material {}'.format(cd_material.shadeSource, name)
                    )
            if objex_data.standalone:
                fw('standalone\n')
            if objex_data.force_write:
                fw('forcewrite\n')
            if objex_data.priority != 0:
                fw('priority {}\n'.format(objex_data.priority))
            if cd_material.texel0:
                fw('texel0 {}\n'.format(cd_material.texel0.texture_name_q))
            if cd_material.texel1:
                fw('texel1 {}\n'.format(cd_material.texel1.texture_name_q))
            uvScaleMain = [cd_material.uScaleMain, cd_material.vScaleMain]
            if any(scale is not None for scale in uvScaleMain):
                for i,uv in enumerate(('U','V')):
                    scale = uvScaleMain[i]
                    if scale is None:
                        scale = 1
                    if scale < 0 or scale > 1:
                        log.warning('In material {}, UV scale {} (the one next to texgen settings) {}\n'
                            'is not in the range (0;1) and will be clamped to that range.\n'
                            'Use per-texel scales for larger scale values.',
                            name, uv, scale)
                        scale = max(0, min(0xFFFF/0x10000, scale))
                    uvScaleMain[i] = scale
                # FIXME does this even work? (called before _loadtexels, idk)
                fw('gbi gsSPTexture(qu016({}), qu016({}), 0, G_TX_RENDERTILE, G_ON)\n'.format(*uvScaleMain))
            fw('gbi gsDPPipeSync()\n')
            # blender settings flags
            otherModeLowerHalfFlags = []
            if objex_data.rendermode_blender_flag_AA_EN:
                otherModeLowerHalfFlags.append('AA_EN')
            if objex_data.rendermode_blender_flag_Z_CMP:
                otherModeLowerHalfFlags.append('Z_CMP')
            if objex_data.rendermode_blender_flag_Z_UPD:
                otherModeLowerHalfFlags.append('Z_UPD')
            if objex_data.rendermode_blender_flag_IM_RD:
                otherModeLowerHalfFlags.append('IM_RD')
            if objex_data.rendermode_blender_flag_CLR_ON_CVG:
                otherModeLowerHalfFlags.append('CLR_ON_CVG')
            if objex_data.rendermode_blender_flag_CVG_DST_ == 'AUTO':
                otherModeLowerHalfFlags.append('CVG_DST_CLAMP')
            else:
                otherModeLowerHalfFlags.append(objex_data.rendermode_blender_flag_CVG_DST_)
            if hasattr(bl_material, 'use_transparency'): # < 2.80
                use_alpha_transparency = 'BLEND' if bl_material.use_transparency else 'NONE'
            else: # 2.80+
                if bl_material.blend_method == 'OPAQUE':
                    use_alpha_transparency = 'NONE'
                elif bl_material.blend_method in ('BLEND', 'HASHED'):
                    use_alpha_transparency = 'BLEND'
                elif bl_material.blend_method == 'CLIP':
                    use_alpha_transparency = 'CLIP'
                else:
                    log.warning('Material {} uses unknown Blend Mode blend_method={!r}, assuming no transparency', name, bl_material.blend_method)
                    use_alpha_transparency = 'NONE'
            if objex_data.rendermode_zmode == 'AUTO':
                otherModeLowerHalfFlags.append('ZMODE_XLU' if use_alpha_transparency != 'NONE' else 'ZMODE_OPA')
            else:
                otherModeLowerHalfFlags.append('ZMODE_%s' % objex_data.rendermode_zmode)
            if (objex_data.rendermode_blender_flag_CVG_X_ALPHA == 'YES'
                or (objex_data.rendermode_blender_flag_CVG_X_ALPHA == 'AUTO'
                    and use_alpha_transparency != 'NONE')
            ):
                otherModeLowerHalfFlags.append('CVG_X_ALPHA')
            if objex_data.rendermode_blender_flag_ALPHA_CVG_SEL:
                otherModeLowerHalfFlags.append('ALPHA_CVG_SEL')
            if (objex_data.rendermode_forceblending == 'YES'
                or (objex_data.rendermode_forceblending == 'AUTO'
                    and use_alpha_transparency == 'BLEND')
            ):
                otherModeLowerHalfFlags.append('FORCE_BL')
            # blender cycles
            """
from gbi.h :
count  P              A              M              B            comment
2      0              0              0              0            "NOOP"
1      G_BL_CLR_FOG   G_BL_A_FOG     G_BL_CLR_IN    G_BL_1MA     only defined for cycle 1 in G_RM_FOG_PRIM_A
1      G_BL_CLR_FOG   G_BL_A_SHADE   G_BL_CLR_IN    G_BL_1MA     only defined for cycle 1 in G_RM_FOG_SHADE_A
11     G_BL_CLR_IN    G_BL_0         G_BL_CLR_IN    G_BL_1       defined for cycle 1 by G_RM_PASS, used for both cycles
2      G_BL_CLR_IN    G_BL_0         G_BL_CLR_BL    G_BL_A_MEM   by G_RM_VISCVG, G_RM_VISCVG2
2      G_BL_CLR_IN    G_BL_A_FOG     G_BL_CLR_MEM   G_BL_1       by G_RM_ADD, G_RM_ADD2
46     G_BL_CLR_IN    G_BL_A_IN      G_BL_CLR_MEM   G_BL_1MA     all XLU use this
30     G_BL_CLR_IN    G_BL_A_IN      G_BL_CLR_MEM   G_BL_A_MEM   most OPA use this
            """
            rm_bl_c0 = objex_data.rendermode_blending_cycle0
            rm_bl_c1 = objex_data.rendermode_blending_cycle1
            if rm_bl_c0 == 'AUTO':
                if use_alpha_transparency == 'NONE':
                    rm_bl_c0 = 'FOG_SHADE'
                elif use_alpha_transparency == 'CLIP':
                    rm_bl_c0 = 'PASS'
                elif use_alpha_transparency == 'BLEND':
                    rm_bl_c0 = 'XLU'
            if rm_bl_c1 == 'AUTO':
                rm_bl_c1 = 'XLU' if use_alpha_transparency != 'NONE' else 'OPA'
            presets = {
                'FOG_PRIM': ('G_BL_CLR_FOG','G_BL_A_FOG',  'G_BL_CLR_IN', 'G_BL_1MA'),
                'FOG_SHADE':('G_BL_CLR_FOG','G_BL_A_SHADE','G_BL_CLR_IN', 'G_BL_1MA'),
                'PASS':     ('G_BL_CLR_IN', 'G_BL_0',      'G_BL_CLR_IN', 'G_BL_1'),
                'OPA':      ('G_BL_CLR_IN', 'G_BL_A_IN',   'G_BL_CLR_MEM','G_BL_A_MEM'),
                'XLU':      ('G_BL_CLR_IN', 'G_BL_A_IN',   'G_BL_CLR_MEM','G_BL_1MA'),
            }
            if rm_bl_c0 == 'CUSTOM':
                blendCycle0flags = (getattr(objex_data, 'rendermode_blending_cycle0_custom_%s' % v) for v in ('P','A','M','B'))
            else:
                blendCycle0flags = presets[rm_bl_c0]
            if rm_bl_c1 == 'CUSTOM':
                blendCycle1flags = (getattr(objex_data, 'rendermode_blending_cycle1_custom_%s' % v) for v in ('P','A','M','B'))
            else:
                blendCycle1flags = presets[rm_bl_c1]
            fw('gbi gsSPSetOtherModeLo(G_MDSFT_RENDERMODE, G_MDSIZ_RENDERMODE, %s | GBL_c1(%s) | GBL_c2(%s))\n' % (
                # ' | ' instead of '|' is required by zzconvert because "Just laziness on my part. :skawoUHHUH:"
                ' | '.join(otherModeLowerHalfFlags),
                ', '.join(blendCycle0flags),
                ', '.join(blendCycle1flags),
            ))
            """
            (P * A + M - B) / (A + B)
            
            GBL_c1(G_BL_CLR_FOG, G_BL_A_SHADE, G_BL_CLR_IN, G_BL_1MA) :
            (G_BL_CLR_FOG * G_BL_A_SHADE + G_BL_CLR_IN - G_BL_1MA) / (G_BL_A_SHADE + G_BL_1MA)
            (fogColor * shadeAlpha + pixelColor - (1-pixelAlpha)) / (shadeAlpha + (1-pixelAlpha))
            ???
            
            GBL_c2(G_BL_CLR_IN,G_BL_A_IN,G_BL_CLR_MEM,G_BL_A_MEM) :
            (G_BL_CLR_IN * G_BL_A_IN + G_BL_CLR_MEM - G_BL_A_MEM) / (G_BL_A_IN + G_BL_A_MEM)
            (firstCycleNumerator * pixelAlpha + frameBufferColor - frameBufferAlpha) / (pixelAlpha + frameBufferAlpha)
            
            and G_RM_AA_ZB_OPA_SURF2 is a preset for the same kind of stuff
            
            
            according to angrylion:
            
            (P * (A / 8) + M * (B / 8 + 1)) / 32 (0-255 integer range)
            for simplicity, assume P * A + M * B (0-1 range)
            G_BL_CLR_FOG * G_BL_A_SHADE + G_BL_CLR_IN * G_BL_1MA
            fogColor * shadeAlpha + pixelColor * (1 - pixelAlpha)
            
            G_BL_CLR_IN * G_BL_A_IN + G_BL_CLR_MEM * G_BL_A_MEM
            firstCycle * pixelAlpha + frameBufferColor * frameBufferAlpha
            
            (fogColor * shadeAlpha + pixelColor * (1 - pixelAlpha)) * pixelAlpha + frameBufferColor * frameBufferAlpha
            """
            for i in range(16):
                flag = cd_material.combinerFlags[i]
                cycle = 'CACA'[i // 4]
                param = 'ABCD'[i % 4]
                supported_flags = CST.COMBINER_FLAGS_SUPPORT[cycle][param]
                if flag not in supported_flags:
                    raise util.ObjexExportAbort(
                        'Unsupported flag for cycle {} param {}: {} (supported: {})'
                        .format(cycle, param, flag, ', '.join(supported_flags)))
            del flag, cycle, param, supported_flags
            # todo better G_?CMUX_ prefix stripping
            fw('gbi gsDPSetCombineLERP(%s)\n' % (', '.join(flag[len('G_?CMUX_'):] for flag in cd_material.combinerFlags)))
            def rgba32(rgba):
                display_device = scene.display_settings.display_device
                if display_device == 'None':
                    pass # no conversion needed
                elif display_device == 'sRGB':
                    # convert (from ?) to sRGB
                    # https://en.wikipedia.org/wiki/SRGB#Specification_of_the_transformation
                    rgb = [(323*u/25) if u <= 0.0031308 else ((211*(u**(5/12))-11)/200) for u in (rgba[i] for i in range(3))]
                    rgba = rgb + [rgba[3]]
                else:
                    log.warning('Unimplemented display_device = {}, colors in-game may differ from the Blender preview', display_device)
                return tuple(int(c*255) for c in rgba)
            if (
                (cd_material.primColor is not None or cd_material.primLodFrac is not None)
                and (
                    objex_data.write_primitive_color == 'YES'
                    or (objex_data.write_primitive_color == 'GLOBAL' and scene.objex_bonus.write_primitive_color)
                )
            ):
                rgbaPrimColor = rgba32(cd_material.primColor) if cd_material.primColor is not None else (255,255,255,255)
                primLodFrac = cd_material.primLodFrac if cd_material.primLodFrac is not None else 0
                primLodFracClamped = min(1, max(0, primLodFrac))
                if primLodFrac != primLodFracClamped:
                    log.error('Material {} has Prim Lod Frac value {} not in 0-1 range, clamping to {}',
                                name, primLodFrac, primLodFracClamped)
                    primLodFrac = primLodFracClamped
                primLodFrac = min(primLodFrac, 0xFF/0x100)
                fw('gbi gsDPSetPrimColor(0, qu08({4}), {0}, {1}, {2}, {3})\n'.format(
                    rgbaPrimColor[0], rgbaPrimColor[1], rgbaPrimColor[2], rgbaPrimColor[3],
                    primLodFrac)
                ) # 421fixme minlevel
            if cd_material.envColor is not None and (objex_data.write_environment_color == 'YES'
                or (objex_data.write_environment_color == 'GLOBAL' and scene.objex_bonus.write_environment_color)
            ):
                fw('gbi gsDPSetEnvColor({}, {}, {}, {})\n'.format(*cd_material.envColor))
            if hasattr(bl_material, 'use_backface_culling') and bl_material.use_backface_culling != objex_data.backface_culling: # 2.80+
                log.warning('Material {} has backface culling {} in objex properties (used for exporting) '
                            'but {} in the Blender material settings (used for viewport rendering)',
                            name, 'ON' if objex_data.backface_culling else 'OFF',
                            'ON' if bl_material.use_backface_culling else 'OFF')
            geometryModeFlagsClear = []
            geometryModeFlagsSet = []
            for flag, set_flag in (
                ('G_SHADE', cd_material.shadeSource is not None),
                ('G_SHADING_SMOOTH', objex_data.geometrymode_G_SHADING_SMOOTH),
                ('G_CULL_FRONT', objex_data.frontface_culling),
                ('G_CULL_BACK', objex_data.backface_culling),
                ('G_ZBUFFER', objex_data.geometrymode_G_ZBUFFER),
                ('G_TEXTURE_GEN', cd_material.texgen in ('TEXGEN', 'TEXGEN_LINEAR')),
                ('G_TEXTURE_GEN_LINEAR', cd_material.texgen == 'TEXGEN_LINEAR'),
                ('G_FOG', objex_data.geometrymode_G_FOG == 'YES' or (
                    objex_data.geometrymode_G_FOG == 'AUTO' and (
                        ('G_BL_CLR_FOG' in blendCycle0flags)
                        or ('G_BL_CLR_FOG' in blendCycle1flags)
                        or ('G_BL_A_FOG' in blendCycle0flags)
                        or ('G_BL_A_FOG' in blendCycle1flags)
                    )
                )),
            ):
                if set_flag:
                    geometryModeFlagsSet.append(flag)
                else:
                    geometryModeFlagsClear.append(flag)
            if cd_material.shadeSource is not None:
                (geometryModeFlagsSet
                    if cd_material.shadeSource == 'NORMALS'
                    else geometryModeFlagsClear
                ).append('G_LIGHTING')
            if len(geometryModeFlagsClear) == 0:
                geometryModeFlagsClear = ('0',)
            if len(geometryModeFlagsSet) == 0:
                geometryModeFlagsSet = ('0',)
            # todo make sure setting geometry mode in one call is not an issue
            fw('gbi gsSPGeometryMode(%s, %s)\n' % (' | '.join(geometryModeFlagsClear),' | '.join(geometryModeFlagsSet)))
            def getUVflags(wrap, mirror):
                return ('G_TX_WRAP' if wrap else 'G_TX_CLAMP', 'G_TX_MIRROR' if mirror else 'G_TX_NOMIRROR')
            for i,texel in (('0',cd_material.texel0),('1',cd_material.texel1)):
                if texel is not None:
                    fw('gbivar cms{} "{}"\n'.format(i, ' | '.join(getUVflags(texel.uWrap, texel.uMirror))))
                    fw('gbivar cmt{} "{}"\n'.format(i, ' | '.join(getUVflags(texel.vWrap, texel.vMirror))))
                    def shiftFromScale(scaleExp):
                        # scaleExp = 0
                        # n = scaleExp = 0
                        if scaleExp == 0:
                            return 0
                        # 1 <= scaleExp <= 5
                        # 15 >= n = 16 - scaleExp >= 11
                        if scaleExp > 0:
                            if scaleExp <= 5:
                                return 16 - scaleExp
                            else:
                                log.error('{!r} scale too big: {}', bl_material, scaleExp)
                                return 0
                        # -10 <= scaleExp <= -1
                        # 10 >= n = -scaleExp >= 1
                        if scaleExp < 0:
                            if scaleExp >= -10:
                                return -scaleExp
                            else:
                                log.error('{!r} scale too low: {}', bl_material, scaleExp)
                                return 0
                    fw('gbivar shifts{} {}\n'.format(i, shiftFromScale(texel.uScale)))
                    fw('gbivar shiftt{} {}\n'.format(i, shiftFromScale(texel.vScale)))
            if any(texel is not None for texel in (cd_material.texel0, cd_material.texel1)):
                fw('gbi _loadtexels\n')
                fw('gbi gsDPSetTileSize(G_TX_RENDERTILE, 0, 0, '
                    'qu102(_texel{0}width-1), qu102(_texel{0}height-1))\n'
                    .format('0' if cd_material.texel0 is not None else '1')
                ) # 421fixme purpose?
            if objex_data.external_material_segment:
                fw('gbi gsSPDisplayList({0}{1})\n'.format(
                    '' if objex_data.external_material_segment.startswith('0x') else '0x',
                    objex_data.external_material_segment)
                )
        # FIXME handle face_image_materials
            '''
            else:
                image = None
                # Write images!
                # face_img.filepath may be '' for generated images
                if face_img and face_img.filepath: # We have an image on the face!
                    image = face_img
                elif (material  # No face image. if we have a material search for MTex image.
                    and hasattr(material, 'texture_slots') # < 2.80
                ):
                    # backwards so topmost are highest priority (421todo ... sure about that?)
                    for mtex in reversed(material.texture_slots):
                        if mtex and mtex.texture and mtex.texture.type == 'IMAGE':
                            image = mtex.texture.image
                            if image and (mtex.use_map_color_diffuse and
                                (mtex.use_map_warp is False) and (mtex.texture_coords != 'REFLECTION')):
                                """
                                what about mtex.offset, mtex.scale? see original code
                                
                                if mtex.offset != Vector((0.0, 0.0, 0.0)):
                                    options.append('-o %.6f %.6f %.6f' % mtex.offset[:])
                                if mtex.scale != Vector((1.0, 1.0, 1.0)):
                                    options.append('-s %.6f %.6f %.6f' % mtex.scale[:])
                                """
                                break
                            else:
                                image = None
                elif material: # 2.80+
                    # based on the Blender 2.82 obj exporter
                    mat_wrap = bpy_extras.node_shader_utils.PrincipledBSDFWrapper(material)
                    # image can be None
                    image = mat_wrap.base_color_texture.image

                if image:
                    texture_name_q = writeTexture(image)
                else:
                    texture_name_q = None
                fw('newmtl %s\n' % name_q)
                if texture_name_q:
                    fw('texel0 %s\n' % texture_name_q)
            '''

def write_collision_material(fw, collision):
    if collision.ignore_camera:
        fw('attrib collision.IGNORE_CAMERA\n')
    if collision.ignore_entity:
        fw('attrib collision.IGNORE_ENTITY\n')
    if collision.ignore_ammo:
        fw('attrib collision.IGNORE_AMMO\n')
    if collision.sound != 'UNSET':
        fw('attrib collision.{}\n'.format(collision.sound))
    if collision.floor != 'UNSET':
        fw('attrib collision.{}\n'.format(collision.floor))
    if collision.wall != 'UNSET':
        fw('attrib collision.{}\n'.format(collision.wall))
    if collision.special != 'UNSET':
        fw('attrib collision.{}\n'.format(collision.special))
    if not collision.horse:
        fw('attrib collision.NOHORSE\n')
    if collision.one_lower:
        fw('attrib collision.RAYCAST\n')
    if collision.wall_damage:
        fw('attrib collision.WALL_DAMAGE\n')
    if collision.hookshot:
        fw('attrib collision.HOOKSHOT\n')
    if collision.steep:
        fw('attrib collision.FLOOR_STEEP\n')
    if collision.warp_enabled:
        fw('attrib collision.WARP,exit={}\n'.format(collision.warp_exit_index))
    if collision.camera_enabled:
        fw('attrib collision.CAMERA,id={}\n'.format(collision.camera_index))
    if collision.echo_enabled:
        fw('attrib collision.ECHO,value={}\n'.format(collision.echo_index))
    if collision.lighting_enabled:
        fw('attrib collision.LIGHTING,value={}\n'.format(collision.lighting_index))
    if collision.conveyor_enabled:
        fw('attrib collision.CONVEYOR,direction={},speed={}{}\n'
            .format(collision.conveyor_direction, collision.conveyor_speed,
                ',inherit' if collision.conveyor_inherit else '')
        )
