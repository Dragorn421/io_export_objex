#  Copyright 2020-2021 Dragorn421
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

import bpy

from .. import util
from ..logging_util import getLogger

class CollectedTexel:
    def __init__(self):
        self.image = None
        self.uScale = None
        self.vScale = None
        self.uWrap = None
        self.vWrap = None
        self.uMirror = None
        self.vMirror = None

class CollectedDisplayMaterial:
    def __init__(self):
        self.combinerFlags = None
        self.primColor = None
        self.primLodFrac = None
        self.envColor = None
        self.shadeSource = None # None, NORMALS, VERTEX_COLORS
        self.vertexColorLayer = None
        self.texel0 = None
        self.texel1 = None
        self.uvLayer = None
        self.uScaleMain = None
        self.vScaleMain = None
        self.texgen = None # None, TEXGEN, TEXGEN_LINEAR
        # FIXME copy objex properties in here yes or no?

class ObjexDisplayMaterialNodeTreeExplorer():
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
                    log.error('Color cycle {!r} is combining alpha from alpha cycle node {!r} which was not used in alpha cycles', cc, socket.node)
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
        cdm = CollectedDisplayMaterial()
        cdm.combinerFlags = self.combinerFlags
        cdm.primColor = self.data.get('primitive')
        cdm.primLodFrac = self.data.get('primitiveLodFrac')
        cdm.envColor = self.data.get('environment')
        if 'shade' in self.data:
            if self.data['shade']['type'] == 'vertex_colors':
                cdm.shadeSource = 'VERTEX_COLORS'
                cdm.vertexColorLayer = self.data['shade']['vertex_color_layer']
            elif self.data['shade']['type'] == 'normals':
                cdm.shadeSource = 'NORMALS'
                cdm.vertexColorLayer = None
            else:
                # FIXME raise exception?
                cdm.shadeSource = self.data['shade']['type']
                cdm.vertexColorLayer = None
        else:
            cdm.shadeSource = None
            cdm.vertexColorLayer = None
        for texelKey in ('texel0', 'texel1'):
            texelData = self.data.get(texelKey)
            if texelData is None:
                setattr(cdm, texelKey, None)
            else:
                ct = CollectedTexel()
                ct.image = texelData['image']
                ct.uScale = texelData['uv_scale_u']
                ct.vScale = texelData['uv_scale_v']
                ct.uWrap = texelData['uv_wrap_u']
                ct.vWrap = texelData['uv_wrap_v']
                ct.uMirror = texelData['uv_mirror_u']
                ct.vMirror = texelData['uv_mirror_v']
                setattr(cdm, texelKey, ct)
        uvMainData = self.data.get('uv_main')
        if uvMainData is None:
            cdm.uvLayer = None
            cdm.uScaleMain = None
            cdm.vScaleMain = None
            cdm.texgen = None
        else:
            cdm.uvLayer = uvMainData['uv_layer']
            cdm.uScaleMain = uvMainData['uv_scale_u_main']
            cdm.vScaleMain = uvMainData['uv_scale_v_main']
            if uvMainData['texgen']:
                if uvMainData['texgen_linear']:
                    cdm.texgen = 'TEXGEN_LINEAR'
                else:
                    cdm.texgen = 'TEXGEN'
            else:
                cdm.texgen = None
        return cdm

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
                log.debug('getting {} from {!r} (socket node: {!r})', k, socket, socket.node)
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
                        .format(self.tree.name, textureNode.texture.type))
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
