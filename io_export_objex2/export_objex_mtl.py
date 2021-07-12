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

class ObjexMaterialNodeTreeExplorer():
    def __init__(self, material):
        self.log = getLogger('ObjexMaterialNodeTreeExplorer')
        self.material = material
        self.tree = material.node_tree
        self.colorCycles = []
        self.alphaCycles = []
        self.flagSockets = {}
        self.defaulFlagColorCycle = 'G_CCMUX_0'
        self.defaulFlagAlphaCycle = 'G_ACMUX_0'

    def fail(self, message, node=None):
        message = 'Failed exploring material %s\n%s' % (self.material.name, message)
        if node is not None:
            message = '%s\nNode: %s %s %r' % (message, node.name, node.bl_idname, node)
        raise util.ObjexExportAbort(message)

    def buildFromColorCycle(self, cc):
        log = self.log
        if cc in (cc for cc,flags,prev_alpha_cycle_node in self.colorCycles):
            log.error('Looping: already visited color cycle node {!r}', cc)
            return
        if cc.bl_idname != 'ShaderNodeGroup':
            self.fail('Expected a node group as color cycle node', node=cc)
        if len(cc.inputs) < 4:
            self.fail('Expected color cycle node to have at least 4 inputs', node=cc)
        flags = []
        prev_color_cycle_node = None
        prev_alpha_cycle_node = None
        for i in range(4):
            if not cc.inputs[i].links:
                flags.append(self.defaulFlagColorCycle)
                continue
            socket = cc.inputs[i].links[0].from_socket
            if socket.bl_idname == 'OBJEX_NodeSocket_CombinerOutput': # < 2.80 (421FIXME_UPDATE would still be nice if custom color sockets could work in 2.80+)
                flag = socket.flagColorCycle
            else: # 2.80+
                flag = socket.node['flagColorCycle %s' % socket.identifier]
            if not flag:
                log.error('No color cycle flag on socket {} of node {}, linked to input {} of {}',
                    socket.name, socket.node.name, 'ABCD'[i], cc.name)
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
        if ac.bl_idname != 'ShaderNodeGroup':
            self.fail('Expected a node group as alpha cycle', node=ac)
        if len(ac.inputs) < 4:
            self.fail('Expected alpha cycle node to have at least 4 inputs', node=ac)
        flags = []
        prev_alpha_cycle_node = None
        for i in range(4):
            if not ac.inputs[i].links:
                flags.append(self.defaulFlagAlphaCycle)
                continue
            socket = ac.inputs[i].links[0].from_socket
            if socket.bl_idname == 'OBJEX_NodeSocket_CombinerOutput': # < 2.80 (421FIXME_UPDATE same as buildFromColorCycle)
                flag = socket.flagAlphaCycle
            else: # 2.80+
                flag = socket.node['flagAlphaCycle %s' % socket.identifier]
            if not flag:
                log.error('No alpha cycle flag on socket {} of node {}, linked to input {} of {}',
                    socket.name, socket.node.name, 'ABCD'[i], ac.name)
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
        if output.bl_idname == 'ShaderNodeOutput': # < 2.80
            lastAlphaCycleNode = output.inputs[1].links[0].from_node
            lastColorCycleNode = output.inputs[0].links[0].from_node
        else: # 2.80+ ShaderNodeOutputMaterial
            principledBsdfNode = output.inputs['Surface'].links[0].from_node
            lastAlphaCycleNode = principledBsdfNode.inputs['Alpha'].links[0].from_node
            lastColorCycleNode = principledBsdfNode.inputs['Base Color'].links[0].from_node
        # build alpha cycles first because color cycle 1 may use alpha cycle 0
        self.buildFromAlphaCycle(lastAlphaCycleNode)
        self.buildFromColorCycle(lastColorCycleNode)
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
            if n.bl_idname in ('ShaderNodeOutput', 'ShaderNodeOutputMaterial'):
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
            'primitiveLodFrac': (('G_CCMUX_PRIM_LOD_FRAC','G_ACMUX_PRIM_LOD_FRAC',),self.buildSingleValue),
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
        mergeTexel = ('uv_layer', 'texgen', 'texgen_linear', 'uv_scale_u_main', 'uv_scale_v_main')
        if 'texel0' in mergedData:
            if 'texel1' in mergedData: # both texel0 and texel1
                mergedData['uv_main'] = dict()
                for k in mergeTexel:
                    if mergedData['texel0'][k] != mergedData['texel1'][k]:
                        log.error('Could not merge texel0 {!r} and texel1 {!r} main uv transform data into {} in uv_main',
                            mergedData['texel0'][k], mergedData['texel1'][k], k)
                        continue
                    mergedData['uv_main'][k] = mergedData['texel0'][k]
                    del mergedData['texel0'][k]
                    del mergedData['texel1'][k]
            else: # only texel0
                mergedData['uv_main'] = dict()
                for k in mergeTexel:
                    mergedData['uv_main'][k] = mergedData['texel0'][k]
                    del mergedData['texel0'][k]
        else:
            if 'texel1' in mergedData: # only texel1
                mergedData['uv_main'] = dict()
                for k in mergeTexel:
                    mergedData['uv_main'][k] = mergedData['texel1'][k]
                    del mergedData['texel1'][k]
            else: # neither texel0 nor texel1
                pass
        self.data = mergedData
        if 'primitiveLodFrac' in data:
            self.data['primitiveLodFrac'] = data['primitiveLodFrac']

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
        if socket.default_value[3] != 1:
            log.warning('(data key: {}) RGB node {} {!r} has its alpha set to {} instead of the default 1\n'
                'This value has no effect and will be ignored, set the alpha in the combiner inputs nodes instead',
                k, socket.node.label, socket.node, socket.default_value[3])
        self.data[k] = socket.default_value

    def buildColorInputA(self, k, socket):
        log = self.log
        # NodeSocketFloat <- OBJEX_NodeSocket_CombinerInput in node group OBJEX_rgba_pipe
        socket = socket.node.inputs[1]
        if socket.links:
            log.error('(data key: {}) alpha socket {!r} should not be linked', k, socket)
        self.data[k] = socket.default_value

    def buildSingleValue(self, k, socket):
        log = self.log
        # NodeSocketFloat <- OBJEX_NodeSocket_CombinerInput in node group OBJEX_single_value
        socket = socket.node.inputs[0]
        if socket.links:
            log.error('(data key: {}) value socket {!r} should not be linked', k, socket)
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
        if textureNode.bl_idname == 'ShaderNodeTexture': # < 2.80
            if textureNode.texture:
                if textureNode.texture.type != 'IMAGE':
                    raise util.ObjexExportAbort(
                        'Material tree {} uses non-image texture type {} '
                        '(only image textures can be exported)'
                        .format(self.tree.name, tex.type))
                image = textureNode.texture.image
            else:
                image = None
        elif textureNode.bl_idname == 'ShaderNodeTexImage': # 2.80+
            image = textureNode.image
        else:
            log.error('Expected a texture node but this is {} {}', textureNode.bl_idname, textureNode)
        if not textureNode.inputs[0].links:
            raise util.ObjexExportAbort('First input of texture node {} {} has no links'.format(textureNode, textureNode.inputs[0]))
        scaleUVnode = textureNode.inputs[0].links[0].from_node
        mainUVtransformNode = scaleUVnode.inputs[0].links[0].from_node
        uvSourceNode = mainUVtransformNode.inputs[0].links[0].from_node
        return {
            'image': image,
            'uv_scale_u': scaleUVnode.inputs[1].default_value,
            'uv_scale_v': scaleUVnode.inputs[2].default_value,
            'uv_wrap_u': scaleUVnode.inputs[3].default_value,
            'uv_wrap_v': scaleUVnode.inputs[4].default_value,
            'uv_mirror_u': scaleUVnode.inputs[5].default_value,
            'uv_mirror_v': scaleUVnode.inputs[6].default_value,
            'uv_layer': uvSourceNode.uv_layer if uvSourceNode.bl_idname == 'ShaderNodeGeometry' else False, # < 2.80
            'uv_map': uvSourceNode.uv_map if uvSourceNode.bl_idname == 'ShaderNodeUVMap' else False, # 2.80+
            'texgen': mainUVtransformNode.inputs[2].default_value,
            'texgen_linear': mainUVtransformNode.inputs[3].default_value,
            'uv_scale_u_main': mainUVtransformNode.inputs[4].default_value,
            'uv_scale_v_main': mainUVtransformNode.inputs[5].default_value,
        }

    def buildShadingDataFromColorSocket(self, k, socket):
        # FIXME
        n = socket.node.inputs[0].links[0].from_node
        self.data[k] = self.buildShadingDataFromShadeSourceNode(n)

    def buildShadingDataFromAlphaSocket(self, k, socket):
        # FIXME
        n = socket.node.inputs[1].links[0].from_node
        self.data[k] = self.buildShadingDataFromShadeSourceNode(n)

    def buildShadingDataFromShadeSourceNode(self, n):
        # FIXME
        if n.bl_idname == 'ShaderNodeGeometry': # < 2.80
            return {'type':'vertex_colors', 'vertex_color_layer':n.color_layer}
        elif n.bl_idname == 'ShaderNodeVertexColor': # 2.80+
            return {'type':'vertex_colors', 'vertex_color_layer':n.layer_name}
        else:
            return {'type':'normals'}

# fixme this is going to end up finding uv/vcolor layers from node (or default to active I guess), if several layers, may write the wrong layer in .objex ... should call write_mtl and get uvs/vcolor data this way before writing the .objex?
def write_mtl(scene, filepath, append_header, options, copy_set, mtl_dict):
    log = getLogger('export_objex_mtl')

    source_dir = os.path.dirname(bpy.data.filepath)
    dest_dir = os.path.dirname(filepath)
    path_mode = options['PATH_MODE']
    export_packed_images = options['EXPORT_PACKED_IMAGES']
    export_packed_images_dir = options['EXPORT_PACKED_IMAGES_DIR']

    warned_about_image_color_space = set()

    with open(filepath, "w", encoding="utf8", newline="\n") as f:
        fw = f.write

        fw('# Blender MTL File: %r\n' % (os.path.basename(bpy.data.filepath) or "None"))
        fw('# Material Count: %i\n' % len(mtl_dict))

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

        # mind the continue used in this loop to skip writing most stuff for empty materials
        for name, name_q, material, face_img in mtl_dict.values():
            log.trace('Writing name={!r} name_q={!r} material={!r} face_img={!r}', name, name_q, material, face_img)
            util.detect_zztag(log, name)
            objex_data = material.objex_bonus if material else None
            # assume non-objex materials using nodes are a rarity before 2.8x
            if objex_data and material.use_nodes and not objex_data.is_objex_material and bpy.app.version < (2, 80, 0):
                log.warning('Material {!r} use_nodes but not is_objex_material\n'
                    '(did you copy-paste nodes from another material instead of clicking the "Init..." button?),\n'
                    'nodes will be ignored and the face image will be used\n'
                    '(for now, to use the current nodes you can make a temporary duplicate of the material,\n'
                    'click the "Init..." button on the original material, delete all the generated nodes\n'
                    'and paste the actual nodes from the duplicate)'
                    , material)
            if objex_data and objex_data.is_objex_material:
                # raises ObjexExportAbort if the material version doesn't match the current addon material version
                data_updater.assert_material_at_current_version(material, util.ObjexExportAbort)
                # 421todo attrib, collision/colliders
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
                # 421todo compare face_img with texel0/1
                if not material.use_nodes:
                    raise util.ObjexExportAbort('Material {0!r} {0.name} is_objex_material but not use_nodes (was "Use Nodes" unchecked after adding objex nodes to it?)'.format(material))
                explorer = ObjexMaterialNodeTreeExplorer(material)
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
                        image = texelData['image']
                        if not image:
                            raise util.ObjexExportAbort('Material %s uses texel data %r without a texture/image '
                                '(make sure texel0 and texel1 have a texture/image set if they are used in the combiner)'
                                % (name, texelData))
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
                        texelData['texture_name_q'] = writeTexture(image)
                # write newmtl after any newtex block
                fw('newmtl %s\n' % name_q)
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
                if objex_data.force_write:
                    fw('forcewrite\n')
                if objex_data.priority != 0:
                    fw('priority %d\n' % objex_data.priority)
                if texel0data:
                    fw('texel0 %s\n' % texel0data['texture_name_q'])
                if texel1data:
                    fw('texel1 %s\n' % texel1data['texture_name_q'])
                if texel0data or texel1data:
                    scaleS = data['uv_main']['uv_scale_u_main']
                    scaleT = data['uv_main']['uv_scale_v_main']
                    for uv,scale in (('U',scaleS),('V',scaleT)):
                        if scale < 0 or scale > 1:
                            log.warning('In material {}, UV scale {} (the one next to texgen settings) {}\n'
                                'is not in the range (0;1) and will be clamped to that range.\n'
                                'Use per-texel scales for larger scale values.',
                                name, uv, scale)
                    scaleS = max(0, min(0xFFFF/0x10000, scaleS))
                    scaleT = max(0, min(0xFFFF/0x10000, scaleT))
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
                if hasattr(material, 'use_transparency'): # < 2.80
                    use_alpha_transparency = 'BLEND' if material.use_transparency else 'NONE'
                else: # 2.80+
                    if material.blend_method == 'OPAQUE':
                        use_alpha_transparency = 'NONE'
                    elif material.blend_method in ('BLEND', 'HASHED'):
                        use_alpha_transparency = 'BLEND'
                    elif material.blend_method == 'CLIP':
                        use_alpha_transparency = 'CLIP'
                    else:
                        log.warning('Material {} uses unknown Blend Mode blend_method={!r}, assuming no transparency', name, material.blend_method)
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
                    flag = explorer.combinerFlags[i]
                    cycle = 'CACA'[i // 4]
                    param = 'ABCD'[i % 4]
                    supported_flags = CST.COMBINER_FLAGS_SUPPORT[cycle][param]
                    if flag not in supported_flags:
                        raise util.ObjexExportAbort(
                            'Unsupported flag for cycle {} param {}: {} (supported: {})'
                            .format(cycle, param, flag, ', '.join(supported_flags)))
                del flag, cycle, param, supported_flags
                # todo better G_?CMUX_ prefix stripping
                fw('gbi gsDPSetCombineLERP(%s)\n' % (', '.join(flag[len('G_?CMUX_'):] for flag in explorer.combinerFlags)))
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
                if 'primitive' in data and (objex_data.write_primitive_color == 'YES'
                    or (objex_data.write_primitive_color == 'GLOBAL' and scene.objex_bonus.write_primitive_color)
                ):
                    rgbaPrimColor = rgba32(data['primitive'])
                    primLodFrac = data['primitiveLodFrac'] if 'primitiveLodFrac' in data else 0
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
                if 'environment' in data and (objex_data.write_environment_color == 'YES'
                    or (objex_data.write_environment_color == 'GLOBAL' and scene.objex_bonus.write_environment_color)
                ):
                    fw('gbi gsDPSetEnvColor(%d, %d, %d, %d)\n' % rgba32(data['environment']))
                if hasattr(material, 'use_backface_culling') and material.use_backface_culling != objex_data.backface_culling: # 2.80+
                    log.warning('Material {} has backface culling {} in objex properties (used for exporting) '
                                'but {} in the Blender material settings (used for viewport rendering)',
                                name, 'ON' if objex_data.backface_culling else 'OFF',
                                'ON' if material.use_backface_culling else 'OFF')
                geometryModeFlagsClear = []
                geometryModeFlagsSet = []
                for flag, set_flag in (
                    ('G_SHADE', shadingType is not None),
                    ('G_SHADING_SMOOTH', objex_data.geometrymode_G_SHADING_SMOOTH),
                    ('G_CULL_FRONT', objex_data.frontface_culling),
                    ('G_CULL_BACK', objex_data.backface_culling),
                    ('G_ZBUFFER', objex_data.geometrymode_G_ZBUFFER),
                    ('G_TEXTURE_GEN', 'uv_main' in data and data['uv_main']['texgen']),
                    ('G_TEXTURE_GEN_LINEAR', 'uv_main' in data and data['uv_main']['texgen_linear']),
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
                    if objex_data.external_material_segment:
                    	fw('gbi gsSPDisplayList({0}{1}})\n'.format(
                            '' if objex_data.external_material_segment.startswith('0x') else '0x',
                            objex_data.external_material_segment)
                        )
                    else:
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

