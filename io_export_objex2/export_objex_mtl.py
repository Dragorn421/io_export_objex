# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import os

import bpy
import bpy_extras.io_utils

from . import util
from .logging_util import getLogger

class ObjexMaterialNodeTreeExplorer():
    def __init__(self, tree):
        self.log = getLogger('ObjexMaterialNodeTreeExplorer')
        self.tree = tree
        self.colorCycles = []
        self.alphaCycles = []
        self.flagSockets = {}
        self.defaulFlagColorCycle = 'G_CCMUX_0'
        self.defaulFlagAlphaCycle = 'G_ACMUX_0'

    def buildFromColorCycle(self, cc):
        log = self.log
        if cc in (cc for cc,flags,prev_alpha_cycle_node in self.colorCycles):
            log.error('Looping: already visited color cycle node {!r}', cc)
            return
        flags = []
        prev_color_cycle_node = None
        prev_alpha_cycle_node = None
        for i in range(4):
            if not cc.inputs[i].links:
                flags.append(self.defaulFlagColorCycle)
                continue
            socket = cc.inputs[i].links[0].from_socket
            if socket.bl_idname != 'OBJEX_NodeSocket_CombinerOutput':
                log.error('What is this socket? not combiner output! {!r}', socket)
            flag = socket.flagColorCycle
            if not flag:
                log.error('Unsupported flag {} for input {} of {!r}', flag, 'ABCD'[i], cc)
            flags.append(flag)
            if flag == 'G_CCMUX_COMBINED':
                if prev_color_cycle_node and prev_color_cycle_node != socket.node:
                    log.error('Different color cycle nodes used for combine {!r} {!r}', prev_color_cycle_node, socket.node)
                prev_color_cycle_node = socket.node
            elif flag == 'G_CCMUX_COMBINED_ALPHA':
                if socket.node not in self.alphaCycles:
                    log.error('Color cycle {!r} is combining alpha from alpha cycle node {!r} which was not used in alpha cycles', cc, ac)
                if prev_alpha_cycle_node and prev_alpha_cycle_node != socket.node:
                    log.error('Different alpha cycle nodes used for combine {!r} {!r}', prev_alpha_cycle_node, socket.node)
                prev_alpha_cycle_node = socket.node
            else:
                storedFlagSocket = self.flagSockets.get(flag)
                if storedFlagSocket and socket != storedFlagSocket:
                    log.error('Flag {} is used by two different sockets {!r} {!r}', flag, storedFlagSocket, socket)
                self.flagSockets[flag] = socket
        self.colorCycles.append((cc, flags, prev_alpha_cycle_node))
        if prev_color_cycle_node:
            self.buildFromColorCycle(prev_color_cycle_node)

    def buildFromAlphaCycle(self, ac):
        log = self.log
        if ac in (ac for ac,flags in self.alphaCycles):
            log.error('Looping: already visited alpha cycle node {!r}', ac)
            return
        flags = []
        prev_alpha_cycle_node = None
        for i in range(4):
            if not ac.inputs[i].links:
                flags.append(self.defaulFlagAlphaCycle)
                continue
            socket = ac.inputs[i].links[0].from_socket
            if socket.bl_idname != 'OBJEX_NodeSocket_CombinerOutput':
                log.error('What is this socket? not combiner output! {!r}', socket)
            flag = socket.flagAlphaCycle
            if not flag:
                log.error('Unsupported flag {} for input {} of {!r}', flag, 'ABCD'[i], ac)
            flags.append(flag)
            if flag == 'G_ACMUX_COMBINED':
                if prev_alpha_cycle_node and prev_alpha_cycle_node != socket.node:
                    log.error('Different cycle nodes used for combine {!r} {!r}', prev_alpha_cycle_node, socket.node)
                prev_alpha_cycle_node = socket.node
            else:
                storedFlagSocket = self.flagSockets.get(flag)
                if storedFlagSocket and socket != storedFlagSocket:
                    log.error('Flag {} is used by two different sockets {!r} {!r}', flag, storedFlagSocket, socket)
                self.flagSockets[flag] = socket
        self.alphaCycles.append((ac, flags))
        if prev_alpha_cycle_node:
            self.buildFromAlphaCycle(prev_alpha_cycle_node)

    def buildCyclesFromOutput(self, output):
        log = self.log
        # 421todo a lot of checks
        # build alpha cycles first because color cycle 1 may use alpha cycle 0
        self.buildFromAlphaCycle(output.inputs[1].links[0].from_node)
        self.buildFromColorCycle(output.inputs[0].links[0].from_node)
        # check the cycles make sense
        self.colorCycles.reverse()
        self.alphaCycles.reverse()
        if len(self.colorCycles) != len(self.alphaCycles):
            log.error('Not the same amount of color ({:d}) and alpha ({:d}) cycles', len(self.colorCycles), len(self.alphaCycles))
        flags = []
        for i in range(len(self.colorCycles)):
            cc,colorFlags,prev_alpha_cycle_node = self.colorCycles[i]
            ac,alphaFlags = self.alphaCycles[i]
            if i == 0 and prev_alpha_cycle_node:
                log.error('First color cycle node {!r} is combining with alpha cycle {!r} (but the first cycle cannot use combine)', cc, prev_alpha_cycle_node)
            if i > 0 and prev_alpha_cycle_node and prev_alpha_cycle_node != self.alphaCycles[i-1][0]:
                log.error('Color cycle {:d} {!r} combines non-previous alpha cycle {!r} instead of previous alpha cycle (based on order) {!r}', i, cc, self.alphaCycles[i-1][0], prev_alpha_cycle_node)
            flags += colorFlags
            flags += alphaFlags
        self.combinerFlags = flags

    def build(self):
        log = self.log
        output = None
        for n in self.tree.nodes:
            if n.bl_idname == 'ShaderNodeOutput':
                if output:
                    log.error('Several output nodes found {!r} {!r}', output, n)
                output = n
        if not output:
            log.error('No Output node found')
        self.buildCyclesFromOutput(output)
        self.buildCombinerInputs()

    def buildCombinerInputs(self):
        log = self.log
        inputs = {
            # color registers
            'primitiveRGB': (('G_CCMUX_PRIMITIVE',),self.buildColorInputRGB),
            'primitiveA': (('G_CCMUX_PRIMITIVE_ALPHA','G_ACMUX_PRIMITIVE',),self.buildColorInputA),
            'environmentRGB': (('G_CCMUX_ENVIRONMENT',),self.buildColorInputRGB),
            'environmentA': (('G_CCMUX_ENV_ALPHA','G_ACMUX_ENVIRONMENT',),self.buildColorInputA),
            # texels
            'texel0RGB': (('G_CCMUX_TEXEL0',),self.buildTexelDataFromColorSocket),
            'texel0A': (('G_CCMUX_TEXEL0_ALPHA','G_ACMUX_TEXEL0',),self.buildTexelDataFromAlphaSocket),
            'texel1RGB': (('G_CCMUX_TEXEL1',),self.buildTexelDataFromColorSocket),
            'texel1A': (('G_CCMUX_TEXEL1_ALPHA','G_ACMUX_TEXEL1',),self.buildTexelDataFromAlphaSocket),
            # vertex colors (or nothing)
            'shadeRGB': (('G_CCMUX_SHADE',),self.buildShadingDataFromColorSocket),
            'shadeA': (('G_CCMUX_SHADE_ALPHA','G_ACMUX_SHADE',),self.buildShadingDataFromAlphaSocket),
        }
        self.data = {}
        log.debug('per-flag used sockets: {!r}', self.flagSockets)
        for k,(flags,socketReader) in inputs.items():
            sockets = set(self.flagSockets[flag] for flag in flags if flag in self.flagSockets)
            if len(sockets) > 1:
                log.error('Different sockets {!r} are used by different flags {!r} but these flags should refer to the same data {}', sockets, flags, k)
            if sockets:
                socket = next(iter(sockets))
                log.debug('getting {} from {!r}', k, socket)
                socketReader(k, socket)
        # FIXME
        def mergeRGBA(rgb, a):
            return (rgb[0], rgb[1], rgb[2], a)
        def mergeRGBA1(rgb):
            return (rgb[0], rgb[1], rgb[2], 1)
        def mergeRGBA2(a):
            return (1,1,1,a)
        def mergeSame(d1, d2):
            if d1 != d2:
                raise ValueError('Merging mismatching data\nd1 = {!r}\nd2 = {!r}'.format(d1,d2))
            return d1
        id = lambda x:x
        merge = {
            'primitive': (('primitiveRGB','primitiveA',),mergeRGBA,mergeRGBA1,mergeRGBA2),
            'environment': (('environmentRGB','environmentA',),mergeRGBA,mergeRGBA1,mergeRGBA2),
            # FIXME check texel0RGB and texel0A are the same, and other checks
            'texel0': (('texel0RGB','texel0A',),mergeSame,id,id),
            'texel1': (('texel1RGB','texel1A',),mergeSame,id,id),
            'shade': (('shadeRGB','shadeA',),mergeSame,id,id),
        }
        data = self.data
        log.debug('data before merge: {!r}', data)
        mergedData = {}
        # FIXME ugly
        for k2,(ks,dataMerger,dataMerger1,dataMerger2) in merge.items():
            if ks[0] in data:
                if ks[1] in data:
                    try:
                        mergedData[k2] = dataMerger(data[ks[0]], data[ks[1]])
                        log.debug('Merged {} {!r} and {} {!r} into {} {!r}', ks[0], data[ks[0]], ks[1], data[ks[1]], k2, mergedData[k2])
                    except ValueError as e:
                        log.exception('Could not merge {} {!r} and {} {!r} into {}', ks[0], data[ks[0]], ks[1], data[ks[1]], k2)
                else:
                    mergedData[k2] = dataMerger1(data[ks[0]])
            else:
                if ks[1] in data:
                    mergedData[k2] = dataMerger2(data[ks[1]])
        self.data = mergedData
        # FIXME uv_layer must be merged from texel01 data

    def buildColorInputRGB(self, k, socket):
        log = self.log
        # OBJEX_NodeSocket_RGBA_Color <- OBJEX_NodeSocket_CombinerInput in node group OBJEX_rgba_pipe
        socket = socket.node.inputs[0]
        # should be linked to a ShaderNodeRGB node
        if socket.links:
            socket = socket.links[0].from_socket
            if socket.node.bl_idname != 'ShaderNodeRGB':
                log.error('(data key: {}) socket {!r} is not linked to a ShaderNodeRGB node, instead it is linked to {!r} ({})', k, socket, socket.node, socket.node.bl_idname)
        else:
            log.error('(data key: {}) socket {!r} is not linked (it should, to a ShaderNodeRGB node)', k, socket)
        self.data[k] = socket.default_value

    def buildColorInputA(self, k, socket):
        log = self.log
        # NodeSocketFloat <- OBJEX_NodeSocket_CombinerInput in node group OBJEX_rgba_pipe
        socket = socket.node.inputs[1]
        if socket.links:
            log.error('(data key: {}) alpha socket {!r} should not be linked', k, socket)
        self.data[k] = socket.default_value

    def buildTexelDataFromColorSocket(self, k, socket):
        # FIXME
        textureNode = socket.node.inputs[0].links[0].from_node
        self.data[k] = self.buildTexelDataFromTextureNode(textureNode)

    def buildTexelDataFromAlphaSocket(self, k, socket):
        # FIXME
        # use alpha input link instead 
        textureNode = socket.node.inputs[1].links[0].from_node
        self.data[k] = self.buildTexelDataFromTextureNode(textureNode)

    def buildTexelDataFromTextureNode(self, textureNode):
        log = self.log
        # FIXME
        if textureNode.type != 'TEXTURE':
            log.error('Expected a texture node but this is {} of type {}', textureNode, textureNode.type)
        if not textureNode.inputs[0].links:
            log.error('First input of texture node {} {} has no links', textureNode, textureNode.inputs[0])
            return {
                # 421fixme ... until logic rewrite
                'texture': textureNode.texture,
                'uv_scale_u': 0,
                'uv_scale_v': 0,
                'uv_wrap_u': True,
                'uv_wrap_v': True,
                'uv_mirror_u': False,
                'uv_mirror_v': False,
                #'uv_layer': None, # unused for now!
            }
        scaleUVnode = textureNode.inputs[0].links[0].from_node
        return {
            'texture': textureNode.texture,
            'uv_scale_u': scaleUVnode.inputs[1].default_value,
            'uv_scale_v': scaleUVnode.inputs[2].default_value,
            'uv_wrap_u': scaleUVnode.inputs[3].default_value,
            'uv_wrap_v': scaleUVnode.inputs[4].default_value,
            'uv_mirror_u': scaleUVnode.inputs[5].default_value,
            'uv_mirror_v': scaleUVnode.inputs[6].default_value,
            'uv_layer': scaleUVnode.inputs[0].links[0].from_node.uv_layer,
        }

    def buildShadingDataFromColorSocket(self, k, socket):
        # FIXME
        n = socket.node.inputs[0].links[0].from_node
        if n.bl_idname == 'ShaderNodeGeometry':
            self.data[k] = {'type':'vertex_colors','vertex_color_layer':n.color_layer}
        else:
            self.data[k] = {'type':'normals'}

    def buildShadingDataFromAlphaSocket(self, k, socket):
        # FIXME
        n = socket.node.inputs[1].links[0].from_node
        if n.bl_idname == 'ShaderNodeGeometry':
            self.data[k] = {'type':'vertex_colors','vertex_color_layer':n.color_layer}
        else:
            self.data[k] = {'type':'normals'}

# fixme this is going to end up finding uv/vcolor layers from node (or default to active I guess), if several layers, may write the wrong layer in .objex ... should call write_mtl and get uvs/vcolor data this way before writing the .objex?
def write_mtl(scene, filepath, append_header, options, copy_set, mtl_dict):
    log = getLogger('export_objex_mtl')

    source_dir = os.path.dirname(bpy.data.filepath)
    dest_dir = os.path.dirname(filepath)
    path_mode = options['PATH_MODE']
    export_packed_images = options['EXPORT_PACKED_IMAGES']
    export_packed_images_dir = options['EXPORT_PACKED_IMAGES_DIR']

    with open(filepath, "w", encoding="utf8", newline="\n") as f:
        fw = f.write

        fw('# Blender MTL File: %r\n' % (os.path.basename(bpy.data.filepath) or "None"))
        fw('# Material Count: %i\n' % len(mtl_dict))

        # used for writing exportid
        append_header(fw)

        # maps a file path to (texture_name, texture_name_q),
        # to avoid duplicate newtex declarations
        # 421fixme is this still expected behavior?
        texture_names = {}

        def getImagePath(image):
            image_filepath = image.filepath
            if image.packed_files:
                if export_packed_images:
                    # save externally a packed image
                    image_filepath = '%s/%s' % (export_packed_images_dir, texture_name)
                    image_filepath = bpy.path.abspath(image_filepath)
                    log.info('Saving packed image {!r} to {}', image, image_filepath)
                    image.save_render(image_filepath)
                else:
                    log.warning('Image {!r} is packed, assuming it exists at {}', image, image_filepath)
            return bpy_extras.io_utils.path_reference(image_filepath, source_dir, dest_dir,
                                                      path_mode, '', copy_set, image.library)

        def writeTexture(image, name):
            image_filepath = image.filepath
            data = texture_names.get(image_filepath)
            if data:
                texture_name, texture_name_q = data
                log.trace('Skipped writing texture {} using file {}', texture_name, image_filepath)
            else:
                texture_name = name
                # make sure texture_name is not already used
                i = 0
                while texture_name in texture_names.values():
                    i += 1
                    texture_name = '%s_%d' % (name, i)
                if i != 0:
                    log.debug('Texture name {} was already used, using {} instead', name, texture_name)
                texture_name_q = util.quote(texture_name)
                texture_names[image_filepath] = (texture_name, texture_name_q)
                fw('newtex %s\n' % texture_name_q)
                filepath = getImagePath(image)
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
                if tod.priority != 0:
                    fw('priority %d\n' % tod.priority)
                if tod.force_write == 'FORCE_WRITE':
                    fw('forcewrite\n')
                elif tod.force_write == 'DO_NOT_WRITE':
                    fw('forcenowrite\n')
                if tod.texture_bank:
                    texturebank_filepath = getImagePath(tod.texture_bank)
                    fw('texturebank %s\n' % texturebank_filepath)
            # texture_name_q is input name if new texture, or
            # the name used for writing the image path (quoted)
            return texture_name_q

        for name, name_q, material, face_img in mtl_dict.values():
            log.trace('Writing name={!r} name_q={!r} material={!r} face_img={!r}', name, name_q, material, face_img)
            objex_data = material.objex_bonus if material else None
            if objex_data and material.use_nodes and not objex_data.is_objex_material:
                log.warning('Material {!r} use_nodes but not is_objex_material '
                    '(did you copy-paste nodes from another material instead of clicking the "Init..." button?), '
                    'nodes will be ignored and the face image will be used '
                    '(for now, to use the current nodes you can make a temporary duplicate of the material, '
                    'click the "Init..." button on the original material, delete all the generated nodes '
                    'and paste the actual nodes from the duplicate)'
                    , material)
            if objex_data and objex_data.is_objex_material:
                # 421todo compare face_img with texel0/1
                if not material.use_nodes:
                    raise util.ObjexExportAbort('Material {0!r} {0.name} is_objex_material but not use_nodes (was "Use Nodes" unchecked after adding objex nodes to it?)'.format(material))
                explorer = ObjexMaterialNodeTreeExplorer(material.node_tree)
                explorer.build()
                if len(explorer.combinerFlags) != 16:
                    log.error('Unexpected combiner flags amount {:d} (are both cycles used?), flags: {!r}', len(explorer.combinerFlags), explorer.combinerFlags)
                data = explorer.data
                texel0data = texel1data = None
                if 'texel0' in data:
                    texel0data = data['texel0']
                if 'texel1' in data:
                    texel1data = data['texel1']
                for texelData in (texel0data,texel1data):
                    if texelData:
                        # todo check texture.type == 'IMAGE'
                        tex = texelData['texture']
                        if not tex:
                            raise util.ObjexExportAbort('Material %s uses texel data %r without a texture '
                                '(make sure texel0 and texel1 have a texture set if they are used in the combiner)'
                                % (name, texelData))
                        texelData['texture_name_q'] = writeTexture(tex.image, tex.name)
                fw('newmtl %s\n' % name_q)
                # 421todo attrib, collision/colliders
                if 'shade' in data:
                    shadingType = data['shade']['type']
                else:
                    shadingType = None
                if objex_data.vertex_shading == 'DYNAMIC':
                    fw('vertexshading dynamic\n')
                else: # vertex_shading == 'AUTO'
                    if shadingType is None:
                        fw('vertexshading none\n')
                    elif shadingType == 'normals':
                        fw('vertexshading normal\n')
                    else:
                        fw('vertexshading color\n')
                if objex_data.standalone:
                    fw('standalone\n')
                # zzconvert detects "empty." on its own, making it explicit here doesn't hurt
                if objex_data.empty or name.startswith('empty.'):
                    fw('empty\n')
                    if objex_data.branch_to_object:
                        fw('gbi gsSPDisplayList(_group=%s)\n' % util.quote(objex_data.branch_to_object.name))
                if objex_data.force_write:
                    fw('forcewrite\n')
                if texel0data:
                    fw('texel0 %s\n' % texel0data['texture_name_q'])
                if texel1data:
                    fw('texel1 %s\n' % texel1data['texture_name_q'])
                scaleS = max(0, min(0xFFFF/0x10000, objex_data.scaleS))
                scaleT = max(0, min(0xFFFF/0x10000, objex_data.scaleT))
                fw('gbi gsSPTexture(qu016(%f), qu016(%f), 0, G_TX_RENDERTILE, G_ON)\n' % (scaleS, scaleT))
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
                if objex_data.rendermode_zmode == 'AUTO':
                    otherModeLowerHalfFlags.append('ZMODE_XLU' if material.use_transparency else 'ZMODE_OPA')
                else:
                    otherModeLowerHalfFlags.append('ZMODE_%s' % objex_data.rendermode_zmode)
                if (objex_data.rendermode_blender_flag_CVG_X_ALPHA == 'YES'
                    or (objex_data.rendermode_blender_flag_CVG_X_ALPHA == 'AUTO'
                        and material.use_transparency)
                ):
                    otherModeLowerHalfFlags.append('CVG_X_ALPHA')
                if objex_data.rendermode_blender_flag_ALPHA_CVG_SEL:
                    otherModeLowerHalfFlags.append('ALPHA_CVG_SEL')
                if (objex_data.rendermode_forceblending == 'YES'
                    or (objex_data.rendermode_forceblending == 'AUTO'
                        and material.use_transparency)
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
                    rm_bl_c0 = 'PASS' if material.use_transparency else 'FOG_SHADE'
                if rm_bl_c1 == 'AUTO':
                    rm_bl_c1 = 'XLU' if material.use_transparency else 'OPA'
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
                # todo better G_?CMUX_ prefix stripping
                fw('gbi gsDPSetCombineLERP(%s)\n' % (', '.join(flag[len('G_?CMUX_'):] for flag in explorer.combinerFlags)))
                def rgba32(rgba):
                    return tuple(int(c*255) for c in rgba)
                if 'primitive' in data and (objex_data.write_primitive_color == 'YES'
                    or (objex_data.write_primitive_color == 'GLOBAL' and scene.objex_bonus.write_primitive_color)
                ):
                    fw('gbi gsDPSetPrimColor(0, qu08(0.5), %d, %d, %d, %d)\n' % rgba32(data['primitive'])) # 421fixme minlevel, lodfrac
                if 'environment' in data and (objex_data.write_environment_color == 'YES'
                    or (objex_data.write_environment_color == 'GLOBAL' and scene.objex_bonus.write_environment_color)
                ):
                    fw('gbi gsDPSetEnvColor(%d, %d, %d, %d)\n' % rgba32(data['environment']))
                """
                421todo
                G_SHADING_SMOOTH ?
                """
                geometryModeFlagsClear = []
                geometryModeFlagsSet = []
                for flag, set_flag in (
                    ('G_SHADE', shadingType is not None),
                    ('G_CULL_FRONT', objex_data.frontface_culling),
                    ('G_CULL_BACK', objex_data.backface_culling),
                    ('G_ZBUFFER', objex_data.geometrymode_G_ZBUFFER),
                    ('G_TEXTURE_GEN', objex_data.use_texgen),
                    ('G_TEXTURE_GEN_LINEAR', objex_data.use_texgen),
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
                if shadingType is not None:
                    (geometryModeFlagsSet
                        if shadingType == 'normals'
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
                for i,texelData in (('0',texel0data),('1',texel1data)):
                    if texelData:
                        fw('gbivar cms%s "%s"\n' % (i, ' | '.join(getUVflags(texelData['uv_wrap_u'], texelData['uv_mirror_u']))))
                        fw('gbivar cmt%s "%s"\n' % (i, ' | '.join(getUVflags(texelData['uv_wrap_v'], texelData['uv_mirror_v']))))
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
                                    log.error('{!r} scale too big: {}', material, scaleExp)
                                    return 0
                            # -10 <= scaleExp <= -1
                            # 10 >= n = -scaleExp >= 1
                            if scaleExp < 0:
                                if scaleExp >= -10:
                                    return -scaleExp
                                else:
                                    log.error('{!r} scale too low: {}', material, scaleExp)
                                    return 0
                        fw('gbivar shifts%s %d\n' % (i, shiftFromScale(texelData['uv_scale_u'])))
                        fw('gbivar shiftt%s %d\n' % (i, shiftFromScale(texelData['uv_scale_v'])))
                if texel0data or texel1data:
                    fw('gbi _loadtexels\n')
                    fw('gbi gsDPSetTileSize(G_TX_RENDERTILE, 0, 0, '
                        'qu102(_texel{0}width-1), qu102(_texel{0}height-1))\n'
                        .format('0' if texel0data else '1')
                    ) # 421fixme ?
            else:
                image = None
                # Write images!
                # face_img.filepath may be '' for generated images
                if face_img and face_img.filepath: # We have an image on the face!
                    image = face_img
                elif material:  # No face image. if we have a material search for MTex image.
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

                if image:
                    texture_name_q = writeTexture(image, image.name)
                else:
                    texture_name_q = None
                fw('newmtl %s\n' % name_q)
                if texture_name_q:
                    fw('texel0 %s\n' % texture_name_q)

