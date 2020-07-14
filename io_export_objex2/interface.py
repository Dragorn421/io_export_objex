import bpy
import mathutils
import re

from . import const_data as CST
from .logging_util import getLogger

"""
useful reference for UI
Vanilla Blender Material UI https://github.com/uzairakbar/blender/blob/master/blender/2.79/scripts/startup/bl_ui/properties_material.py
About Panel Ordering (2016): no API https://blender.stackexchange.com/questions/24041/how-i-can-define-the-order-of-the-panels
Thorough UI script example https://blender.stackexchange.com/questions/57306/how-to-create-a-custom-ui
More examples https://b3d.interplanety.org/en/creating-panels-for-placing-blender-add-ons-user-interface-ui/
bl_idname and class name guidelines (Blender 2.80) https://wiki.blender.org/wiki/Reference/Release_Notes/2.80/Python_API/Addons
General information https://docs.blender.org/api/2.79/info_overview.html#integration-through-classes
Menu examples https://docs.blender.org/api/2.79/bpy.types.Menu.html
Panel examples https://docs.blender.org/api/2.79/bpy.types.Panel.html
Preferences example https://docs.blender.org/api/2.79/bpy.types.AddonPreferences.html
Using properties, and a list of properties https://docs.blender.org/api/2.79/bpy.props.html
"Color property" (2014) https://blender.stackexchange.com/questions/6154/custom-color-property-in-panel-draw-layout
UILayout https://docs.blender.org/api/2.79/bpy.types.UILayout.html
Looks like a nice tutorial, demonstrates operator.draw but not other UI stuff https://michelanders.blogspot.com/p/creating-blender-26-python-add-on.html
custom properties https://docs.blender.org/api/2.79/bpy.types.bpy_struct.html
very nice bare-bones example with custom node and ui https://gist.github.com/OEP/5978445

other useful reference
GPL https://www.gnu.org/licenses/gpl-3.0.en.html
API changes https://docs.blender.org/api/current/change_log.html
Addon Tutorial (not part of the addon doc) https://docs.blender.org/manual/en/latest/advanced/scripting/addon_tutorial.html
Operator examples https://docs.blender.org/api/2.79/bpy.types.Operator.html
bl_idname requirements https://github.com/blender/blender/blob/f149d5e4b21f372f779fdb28b39984355c9682a6/source/blender/windowmanager/intern/wm_operators.c#L167

add input socket to a specific node instance #bpy.data.materials['Material'].node_tree.nodes['Material'].inputs.new('NodeSocketColor', 'envcolor2')

"""

def propOffset(layout, data, key, propName):
    offsetStr = getattr(data, key)
    bad_offset = None
    # also allows an empty string
    if not re.match(r'^(?:(?:0x)?[0-9a-fA-F]|)+$', offsetStr):
        bad_offset = 'not_hex'
    if re.match(r'^[0-9]+$', offsetStr):
        bad_offset = 'warn_decimal'
    layout.prop(data, key, icon=('ERROR' if bad_offset else 'NONE'))
    if bad_offset == 'not_hex':
        layout.label(text='%s must be hexadecimal' % propName)
    elif bad_offset == 'warn_decimal':
        layout.label(text='%s looks like base 10' % propName)
        layout.label(text='It will be read in base 16')
        layout.label(text='Use 0x prefix to be explicit')


# mesh

class OBJEX_PT_mesh(bpy.types.Panel):
    bl_label = 'Objex'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'

    @classmethod
    def poll(self, context):
        object = context.object
        return object.type == 'MESH'

    def draw(self, context):
        object = context.object
        data = object.data.objex_bonus # ObjexMeshProperties
        self.layout.prop(data, 'priority')
        self.layout.prop(data, 'write_origin')
        self.layout.prop(data, 'attrib_billboard')
        for attrib in ('LIMBMTX', 'POSMTX', 'NOSPLIT', 'NOSKEL', 'PROXY'):
            self.layout.prop(data, 'attrib_%s' % attrib)
        self.layout.operator('OBJEX_OT_mesh_find_multiassigned_vertices', text='Find multiassigned vertices')
        self.layout.operator('OBJEX_OT_mesh_find_unassigned_vertices', text='Find unassigned vertices')
        self.layout.operator('OBJEX_OT_mesh_list_vertex_groups', text='List groups of selected vertex')


# armature

# do not use the self argument, as the function is used by at least 2 properties
def armature_export_actions_change(self, context):
    armature = context.armature
    data = armature.objex_bonus
    actions = data.export_actions
    # remove all items without an action set
    # this purposefully skips actions[-1]
    i = len(actions) - 1
    while i > 0:
        i -= 1
        item = actions[i]
        if not item.action:
            actions.remove(i)
    # make sure last item is empty, to allow adding actions
    if not actions or actions[-1].action:
        actions.add()

class OBJEX_UL_actions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, 'action', text='')

class OBJEX_PT_armature(bpy.types.Panel):
    bl_label = 'Objex'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    
    @classmethod
    def poll(self, context):
        armature = context.armature
        return armature is not None
    
    def draw(self, context):
        armature = context.armature
        data = armature.objex_bonus
        # actions
        self.layout.prop(data, 'export_all_actions')
        if not data.export_all_actions:
            self.layout.label(text='Actions to export:')
            self.layout.template_list('OBJEX_UL_actions', '', data, 'export_actions', data, 'export_actions_active')
        # type
        self.layout.prop(data, 'type')
        # pbody
        if data.pbody:
            box = self.layout.box()
            box.prop(data, 'pbody')
            if data.pbody_parent_object:
                if hasattr(data.pbody_parent_object, 'type') and data.pbody_parent_object.type == 'ARMATURE':
                    box.prop(data, 'pbody_parent_object')
                    valid_bone = data.pbody_parent_bone in armature.bones
                    box.prop_search(data, 'pbody_parent_bone', data.pbody_parent_object.data, 'bones', icon=('NONE' if valid_bone else 'ERROR'))
                    if not valid_bone:
                        box.label(text='A bone must be picked')
                else:
                    box.prop(data, 'pbody_parent_object', icon='ERROR')
                    box.label(text='If set, parent must be an armature')
            else:
                box.prop(data, 'pbody_parent_object')
        else:
            self.layout.prop(data, 'pbody')
        # segment
        box = self.layout.box()
        propOffset(box, data, 'segment', 'Segment')
        box.prop(data, 'segment_local')

#
# material
#

def stripPrefix(s, prefix):
    return s[len(prefix):] if s.startswith(prefix) else s

# NodeSocketInterface

class OBJEX_NodeSocketInterface_CombinerIO():
    def draw(self, context, layout):
        pass
    def draw_color(self, context):
        return CST.COLOR_OK

class OBJEX_NodeSocketInterface_CombinerOutput(bpy.types.NodeSocketInterface, OBJEX_NodeSocketInterface_CombinerIO):
    bl_socket_idname = 'OBJEX_NodeSocket_CombinerOutput'

class OBJEX_NodeSocketInterface_CombinerInput(bpy.types.NodeSocketInterface, OBJEX_NodeSocketInterface_CombinerIO):
    bl_socket_idname = 'OBJEX_NodeSocket_CombinerInput'

class OBJEX_NodeSocketInterface_RGBA_Color(bpy.types.NodeSocketInterface):
    bl_socket_idname = 'OBJEX_NodeSocket_RGBA_Color'
    # 421fixme COLOR_GAMMA or COLOR for the different uses in this file?
    # 421fixme is default_value in interface used at all?
    default_value = bpy.props.FloatVectorProperty(name='default_value', default=(1,1,1), min=0, max=1, subtype='COLOR')
    def draw(self, context, layout):
        pass
    def draw_color(self, context):
        return CST.COLOR_RGBA_COLOR

class OBJEX_NodeSocketInterface_Dummy():
    def draw(self, context, layout):
        pass
    def draw_color(self, context):
        return CST.COLOR_NONE

# NodeSocket

class OBJEX_NodeSocket_CombinerOutput(bpy.types.NodeSocket):
    default_value = bpy.props.FloatVectorProperty(name='default_value', default=(1,0,0), min=0, max=1, subtype='COLOR')

    flagColorCycle = bpy.props.StringProperty(default='')
    flagAlphaCycle = bpy.props.StringProperty(default='')

    def draw(self, context, layout, node, text):
        if node.bl_idname == 'NodeGroupOutput' or (not self.flagColorCycle and not self.flagAlphaCycle):
            layout.label(text=text)
        else:
            layout.label(text='%s (%s/%s)' % (text, stripPrefix(self.flagColorCycle, 'G_CCMUX_'), stripPrefix(self.flagAlphaCycle, 'G_ACMUX_')))
        # todo "show compat" operator which makes A/B/C/D blink when they support this output?

    def draw_color(self, context, node):
        return CST.COLOR_OK

class OBJEX_NodeSocket_CombinerInput(bpy.types.NodeSocket):
    default_value = bpy.props.FloatVectorProperty(name='default_value', default=(0,1,0), min=0, max=1, subtype='COLOR')

    def linkToFlag(self):
        """
        returns a (flag, error) tuple
        flag standing for what is linked to this socket
        and error being an error message string
        success: flag is a string and error is None
        failure: flag is None and error is a string
        Note that flag may be an empty string '' to
        indicate lack of support for the cycle
        This does not check if the input can be used for
        this socket's variable (A,B,C,D)
        """
        cycle = self.node.get('cycle')
        if cycle not in (CST.CYCLE_COLOR, CST.CYCLE_ALPHA):
            return None, 'Unknown cycle %s' % cycle
        # default to 0 (allowed everywhere)
        if not self.links:
            return CST.COMBINER_FLAGS_0[cycle], None
        otherSocket = self.links[0].from_socket
        if otherSocket.bl_idname != 'OBJEX_NodeSocket_CombinerOutput':
            return None, 'Bad link to %s' % otherSocket.bl_idname
        if cycle == CST.CYCLE_COLOR:
            return otherSocket.flagColorCycle, None
        else: # CST.CYCLE_ALPHA
            return otherSocket.flagAlphaCycle, None

    def draw(self, context, layout, node, text):
        # don't do anything fancy in node group "inside" view
        if node.bl_idname == 'NodeGroupInput':
            layout.label(text=text)
            return
        cycle = self.node.get('cycle')
        name = self.name # A,B,C,D
        flag, warnMsg = self.linkToFlag()
        if flag is None:
            value = '?'
        elif flag == '':
            value = 'XXX'
            warnMsg = 'Not for cycle %s' % cycle
        else:
            value = stripPrefix(flag, CST.COMBINER_FLAGS_PREFIX[cycle])
            if flag not in CST.COMBINER_FLAGS_SUPPORT[cycle][name]:
                warnMsg = 'Only for %s, not %s' % (','.join(var for var,flags in CST.COMBINER_FLAGS_SUPPORT[cycle].items() if flag in flags), name)
        input_flags_prop_name = 'input_flags_%s_%s' % (cycle, name)
        col = layout.column()
        if warnMsg:
            col = layout.column()
            col.label(text=warnMsg, icon='ERROR')
        col.label(text='%s = %s' % (name, value))
        col.prop(self, input_flags_prop_name, text='')

    def draw_color(self, context, node):
        if node.bl_idname == 'NodeGroupInput':
            return CST.COLOR_OK
        flag, warnMsg = self.linkToFlag()
        return CST.COLOR_BAD if warnMsg else CST.COLOR_OK

def input_flag_list_choose_get(variable):
    def input_flag_list_choose(self, context):
        log = getLogger('interface')
        input_flags_prop_name = 'input_flags_%s_%s' % (self.node['cycle'], variable)
        flag = getattr(self, input_flags_prop_name)
        if flag == '_':
            return
        tree = self.id_data
        matching_socket = None
        for n in tree.nodes:
            for s in n.outputs:
                if s.bl_idname == 'OBJEX_NodeSocket_CombinerOutput':
                    if flag == (s.flagColorCycle if self.node['cycle'] == CST.CYCLE_COLOR else s.flagAlphaCycle):
                        if matching_socket:
                            log.error('Found several sockets for flag {}: {!r} {!r}', flag, matching_socket, s)
                        matching_socket = s
        if not matching_socket:
            log.error('Did not find any socket for flag {}', flag)
        while self.links:
            tree.links.remove(self.links[0])
        tree.links.new(matching_socket, self)
        setattr(self, input_flags_prop_name, '_')
    return input_flag_list_choose
for cycle in (CST.CYCLE_COLOR,CST.CYCLE_ALPHA):
    for variable in ('A','B','C','D'):
        setattr(
            OBJEX_NodeSocket_CombinerInput,
            'input_flags_%s_%s' % (cycle, variable),
            bpy.props.EnumProperty(
                items=[
                    (flag, stripPrefix(flag, CST.COMBINER_FLAGS_PREFIX[cycle]), flag)
                        for flag in CST.COMBINER_FLAGS_SUPPORT[cycle][variable]
                        # 421todo can't implement these without using cycle number:
                        if flag not in ('G_CCMUX_COMBINED','G_CCMUX_COMBINED_ALPHA','G_ACMUX_COMBINED')
                ] + [('_','...','')],
                name='%s' % variable,
                default='_',
                update=input_flag_list_choose_get(variable)
            )
        )
del input_flag_list_choose_get

class OBJEX_NodeSocket_RGBA_Color(bpy.types.NodeSocket):
    default_value = bpy.props.FloatVectorProperty(
        name='default_value', default=(1,1,1),
        min=0, max=1, subtype='COLOR',
    )

    def draw(self, context, layout, node, text):
        if self.is_linked:
            layout.label(text=text)
        else:
            col = layout.column()
            col.label(text=text,icon='ERROR')
            col.label(text='MUST BE LINKED',icon='ERROR')

    def draw_color(self, context, node):
        return CST.COLOR_RGBA_COLOR if self.is_linked else CST.COLOR_BAD

    def text(self, txt):
        return txt

class OBJEX_NodeSocket_IntProperty():
    def update_prop(self, context):
        self.node.inputs[self.target_socket_name].default_value = self.default_value
    default_value = bpy.props.IntProperty(update=update_prop)

    def draw(self, context, layout, node, text):
        layout.prop(self, 'default_value', text=text)

    def draw_color(self, context, node):
        return CST.COLOR_NONE

class OBJEX_NodeSocket_BoolProperty():
    def update_prop(self, context):
        self.node.inputs[self.target_socket_name].default_value = 1 if self.default_value else 0
    default_value = bpy.props.BoolProperty(update=update_prop)

    def draw(self, context, layout, node, text):
        layout.prop(self, 'default_value', text=text)

    def draw_color(self, context, node):
        return CST.COLOR_NONE

# node groups creation

def create_node_group_cycle(group_name):
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    def addMixRGBnode(operation):
        n = tree.nodes.new('ShaderNodeMixRGB')
        n.blend_type = operation
        n.inputs[0].default_value = 1 # "Fac"
        return n

    inputs_node = tree.nodes.new('NodeGroupInput')
    inputs_node.location = (-450,0)
    tree.inputs.new('OBJEX_NodeSocket_CombinerInput', 'A')
    tree.inputs.new('OBJEX_NodeSocket_CombinerInput', 'B')
    tree.inputs.new('OBJEX_NodeSocket_CombinerInput', 'C')
    tree.inputs.new('OBJEX_NodeSocket_CombinerInput', 'D')

    A_minus_B = addMixRGBnode('SUBTRACT')
    A_minus_B.location = (-250,150)
    tree.links.new(inputs_node.outputs['A'], A_minus_B.inputs[1])
    tree.links.new(inputs_node.outputs['B'], A_minus_B.inputs[2])

    times_C = addMixRGBnode('MULTIPLY')
    times_C.location = (-50,100)
    tree.links.new(A_minus_B.outputs[0], times_C.inputs[1])
    tree.links.new(inputs_node.outputs['C'], times_C.inputs[2])

    plus_D = addMixRGBnode('ADD')
    plus_D.location = (150,50)
    tree.links.new(times_C.outputs[0], plus_D.inputs[1])
    tree.links.new(inputs_node.outputs['D'], plus_D.inputs[2])

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (350,0)
    tree.outputs.new('OBJEX_NodeSocket_CombinerOutput', 'Result')
    tree.links.new(plus_D.outputs[0], outputs_node.inputs['Result'])
    tree.outputs['Result'].name = '(A-B)*C+D' # rename from 'Result' to formula

    return tree

def create_node_group_color_static(group_name, colorValue, colorValueName):
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    rgb = tree.nodes.new('ShaderNodeRGB')
    rgb.outputs[0].default_value = colorValue
    rgb.location = (0,100)

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (150,50)
    tree.outputs.new('OBJEX_NodeSocket_CombinerOutput', colorValueName)
    tree.links.new(rgb.outputs[0], outputs_node.inputs[colorValueName])

    return tree

# 421todo for texgen preview, see G_TEXTURE_GEN in gSPProcessVertex in GLideN64/src/gSP.cpp
def create_node_group_uv_pipe(group_name):
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')
    
    def draw_if(self, context, layout, node, text):
        super().draw(context, layout, node, text)
    
    inputs_node = tree.nodes.new('NodeGroupInput')
    inputs_node.location = (-600,150)
    tree.inputs.new('NodeSocketVector', 'UV')
    # 421todo if Uniform UV Scale is checked, only display Scale Exponent and use for both U and V scales (is this possible?)
    #tree.inputs.new('NodeSocketBool', 'Uniform UV Scale').default_value = True
    #tree.inputs.new('NodeSocketInt', 'Scale Exponent')
    # blender 2.79 fails to transfer data somewhere when linking int socket to float socket of math node, same for booleans
    # those sockets wrap the float ones that are actually used for calculations
    tree.inputs.new('OBJEX_NodeSocket_UVpipe_ScaleU', 'U Scale Exponent')
    tree.inputs.new('OBJEX_NodeSocket_UVpipe_ScaleV', 'V Scale Exponent')
    tree.inputs.new('OBJEX_NodeSocket_UVpipe_WrapU', 'Wrap U')
    tree.inputs.new('OBJEX_NodeSocket_UVpipe_WrapV', 'Wrap V')
    tree.inputs.new('OBJEX_NodeSocket_UVpipe_MirrorU', 'Mirror U')
    tree.inputs.new('OBJEX_NodeSocket_UVpipe_MirrorV', 'Mirror V')
    # internal hidden sockets
    tree.inputs.new('NodeSocketFloat', 'U Scale Exponent Float')
    tree.inputs.new('NodeSocketFloat', 'V Scale Exponent Float')
    tree.inputs.new('NodeSocketFloat', 'Wrap U (0/1)')
    tree.inputs.new('NodeSocketFloat', 'Wrap V (0/1)')
    tree.inputs.new('NodeSocketFloat', 'Mirror U (0/1)')
    tree.inputs.new('NodeSocketFloat', 'Mirror V (0/1)')
    # pixels along U/V used for better clamping, to clamp the last pixel in the tile
    # before the clamp part instead of clamping at the limit, where color is
    # merged with the wrapping UV
    # (this is only what I am guessing is happening)
    # 421todo this is basically texture width/height right? could be set automatically
    pixelsU = tree.inputs.new('NodeSocketFloat', 'Pixels along U')
    pixelsU.min_value = 1
    inf = float('inf')
    pixelsU.default_value = +inf
    pixelsV = tree.inputs.new('NodeSocketFloat', 'Pixels along V')
    pixelsV.min_value = 1
    pixelsV.default_value = +inf

    separateXYZ = tree.nodes.new('ShaderNodeSeparateXYZ')
    separateXYZ.location = (-200,100)
    tree.links.new(inputs_node.outputs['UV'], separateXYZ.inputs[0])

    def addMathNode(operation, location, in0=None, in1=None):
        n = tree.nodes.new('ShaderNodeMath')
        n.operation = operation
        n.location = location
        for i in (0,1):
            input = (in0,in1)[i]
            if input is not None:
                if isinstance(input, (int,float)):
                    n.inputs[i].default_value = input
                else:
                    tree.links.new(input, n.inputs[i])
        return n

    final = {}
    for uv, i, y in (('U',0,400),('V',1,-600)):
        # looking at the nodes in blender is probably better than trying to understand the code here
        roundedExp = addMathNode('ROUND', (-400,400+y), inputs_node.outputs['%s Scale Exponent Float' % uv])
        scalePow = addMathNode('POWER', (-200,400+y), 2, roundedExp.outputs[0])
        scale = addMathNode('MULTIPLY', (0,400+y), separateXYZ.outputs[i], scalePow.outputs[0])
        # mirror
        notMirroredBool = addMathNode('SUBTRACT', (200,600+y), 1, inputs_node.outputs['Mirror %s (0/1)' % uv])
        identity = addMathNode('MULTIPLY', (400,400+y), scale.outputs[0], notMirroredBool.outputs[0])
        reversed = addMathNode('MULTIPLY', (200,200+y), scale.outputs[0], -1)
        add1 = addMathNode('ADD', (200,0+y), scale.outputs[0], 1)
        mod4_1 = addMathNode('MODULO', (400,0+y), add1.outputs[0], 4)
        add4 = addMathNode('ADD', (600,0+y), mod4_1.outputs[0], 4)
        mod4_2 = addMathNode('MODULO', (800,0+y), add4.outputs[0], 4)
        notMirroredPartBool = addMathNode('LESS_THAN', (1000,0+y), mod4_2.outputs[0], 2)
        mirroredPartNo = addMathNode('MULTIPLY', (1200,400+y), scale.outputs[0], notMirroredPartBool.outputs[0])
        mirroredPartBool = addMathNode('SUBTRACT', (1200,0+y), 1, notMirroredPartBool.outputs[0])
        mirroredPartYes = addMathNode('MULTIPLY', (1400,200+y), reversed.outputs[0], mirroredPartBool.outputs[0])
        withMirror = addMathNode('ADD', (1600,300+y), mirroredPartYes.outputs[0], mirroredPartNo.outputs[0])
        mirrored = addMathNode('MULTIPLY', (1800,400+y), withMirror.outputs[0], inputs_node.outputs['Mirror %s (0/1)' % uv])
        mirroredFinal = addMathNode('ADD', (2000,300+y), identity.outputs[0], mirrored.outputs[0])
        # wrapped (identity)
        wrapped = addMathNode('MULTIPLY', (2200,400+y), mirroredFinal.outputs[0], inputs_node.outputs['Wrap %s (0/1)' % uv])
        # clamped (in [-1;1])
        pixelSizeUVspace  = addMathNode('DIVIDE', (1800,100+y), 1, inputs_node.outputs['Pixels along %s' % uv])
        upperBound = addMathNode('SUBTRACT', (2000,0+y), 1, pixelSizeUVspace.outputs[0])
        lowerBound = addMathNode('ADD', (2000,-300+y), -1, pixelSizeUVspace.outputs[0])
        upperClamped = addMathNode('MINIMUM', (2300,200+y), mirroredFinal.outputs[0], upperBound.outputs[0])
        upperLowerClamped = addMathNode('MAXIMUM', (2500,200+y), upperClamped.outputs[0], lowerBound.outputs[0])
        notWrap = addMathNode('SUBTRACT', (2400,0+y), 1, inputs_node.outputs['Wrap %s (0/1)' % uv])
        clamped = addMathNode('MULTIPLY', (2700,200+y), upperLowerClamped.outputs[0], notWrap.outputs[0])
        #
        finalU = addMathNode('ADD', (2900,300+y), wrapped.outputs[0], clamped.outputs[0])
        final[uv] = finalU
    finalU = final['U']
    finalV = final['V']

    # out

    combineXYZ = tree.nodes.new('ShaderNodeCombineXYZ')
    combineXYZ.location = (3100,100)
    tree.links.new(finalU.outputs[0], combineXYZ.inputs[0])
    tree.links.new(finalV.outputs[0], combineXYZ.inputs[1])

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (3300,100)
    tree.outputs.new('NodeSocketVector', 'UV')
    tree.links.new(combineXYZ.outputs[0], outputs_node.inputs['UV'])

    return tree

def create_node_group_rgba_pipe(group_name):
    """
    "Casts" input for use as cycle inputs
    Inputs: OBJEX_NodeSocket_RGBA_Color 'Color', NodeSocketFloat 'Alpha'
    Outputs: OBJEX_NodeSocket_CombinerOutput 'RGB', OBJEX_NodeSocket_CombinerOutput 'A'
    """
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    inputs_node = tree.nodes.new('NodeGroupInput')
    inputs_node.location = (-100,50)
    tree.inputs.new('OBJEX_NodeSocket_RGBA_Color', 'Color')
    alpha_input_socket = tree.inputs.new('NodeSocketFloat', 'Alpha')
    alpha_input_socket.default_value = 1
    alpha_input_socket.min_value = 0
    alpha_input_socket.max_value = 1

    alpha_3d = tree.nodes.new('ShaderNodeCombineRGB')
    for i in range(3):
        tree.links.new(inputs_node.outputs[1], alpha_3d.inputs[i])

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (100,50)
    tree.outputs.new('OBJEX_NodeSocket_CombinerOutput', 'RGB')
    tree.outputs.new('OBJEX_NodeSocket_CombinerOutput', 'A')
    tree.links.new(inputs_node.outputs[0], outputs_node.inputs['RGB'])
    tree.links.new(alpha_3d.outputs[0], outputs_node.inputs['A'])

    return tree

def update_node_groups():
    # dict mapping group names (keys in bpy.data.node_groups) to (latest_version, create_function) tuples
    # version is stored in 'objex_version' for each group and compared to latest_version
    # usage: increment associated latest_version when making changes in the create_function of some group
    # WARNING: the upgrading preserves links, which is the intent, but it means outputs/inputs order must not change
    #   (if the order must change, more complex upgrading code is required)
    groups = {
        'OBJEX_Cycle': (1, create_node_group_cycle),
        'OBJEX_Color0': (1, lambda group_name: create_node_group_color_static(group_name, (0,0,0,0), '0')),
        'OBJEX_Color1': (1, lambda group_name: create_node_group_color_static(group_name, (1,1,1,1), '1')),
        'OBJEX_UV_pipe': (1, create_node_group_uv_pipe),
        'OBJEX_rgba_pipe': (1, create_node_group_rgba_pipe),
    }
    # dict mapping old groups to new groups, used later for upgrading
    upgrade = {}
    for group_name, (latest_version, group_create) in groups.items():
        old_node_group = None
        current_node_group = bpy.data.node_groups.get(group_name)
        # if current_node_group is outdated
        if current_node_group and (
            'objex_version' not in current_node_group
            or current_node_group['objex_version'] < latest_version
        or True): # 421fixme always make groups outdated, easier testing
            old_node_group = current_node_group
            old_node_group.name = '%s_old' % group_name
            current_node_group = None
        # group must be (re)created
        if not current_node_group:
            current_node_group = group_create(group_name)
            current_node_group['objex_version'] = latest_version
        # store update from old_node_group to current_node_group
        if old_node_group:
            upgrade[old_node_group] = current_node_group
    # upgrade outdated group nodes
    if upgrade:
        for m in bpy.data.materials:
            if m.use_nodes and m.node_tree:
                for n in m.node_tree.nodes:
                    if n.bl_idname == 'ShaderNodeGroup':
                        new_tree = upgrade.get(n.node_tree)
                        if new_tree:
                            n.node_tree = new_tree
        for old_node_group in upgrade:
            bpy.data.node_groups.remove(old_node_group)

class OBJEX_OT_material_init(bpy.types.Operator):

    bl_idname = 'objex.material_init'
    bl_label = 'Initialize a material for use on Objex export'
    bl_options = {'INTERNAL', 'PRESET', 'REGISTER', 'UNDO'}
    
    def execute(self, context):
        material = context.material
        # let the user choose, as use_transparency is used when
        # exporting to distinguish opaque and translucent geometry
        #material.use_transparency = True
        material.use_nodes = True
        update_node_groups()
        node_tree = material.node_tree
        nodes = node_tree.nodes
        
        nodes.clear() # 421fixme do not inconditionally rebuild
        """
        421todo different "rebuild" modes:
        reset (nodes.clear())
        fill (add missing nodes)
        hide sockets (eg "Wrap U (0/1)")
        re-apply dimensions/positions
        ...?
        (this only means splitting this operator in parts, or adding more parameters to it)
        """

        if 'Geometry' not in nodes:
            geometry = nodes.new('ShaderNodeGeometry')
            geometry.name = 'Geometry'
            geometry.location = (-400, -100)
        else:
            geometry = nodes['Geometry']

        for i in (0,1):
            uvTransform_node_name = 'OBJEX_TransformUV%d' % i
            if uvTransform_node_name not in nodes:
                uvTransform = nodes.new('ShaderNodeGroup')
                uvTransform.node_tree = bpy.data.node_groups['OBJEX_UV_pipe']
                uvTransform.name = uvTransform_node_name # internal name
                uvTransform.label = 'UV transform %d' % i # displayed name
                uvTransform.location = (-150, 50 - i * 300)
                uvTransform.width += 50
                # set default values in most common usage, but it is also
                # required to update the default value of "Wrap/Mirror U/V (0/1)"
                # sockets which are used for the actual UV transform
                for uv in ('U','V'):
                    for wrapper_socket_name, float_socket_name, default_value in (
                        ('%s Scale Exponent', '%s Scale Exponent Float', 0),
                        ('Wrap %s', 'Wrap %s (0/1)', True),
                        ('Mirror %s', 'Mirror %s (0/1)', False),
                    ):
                        uvTransform.inputs[wrapper_socket_name % uv].default_value = default_value
                        uvTransform.inputs[float_socket_name % uv].hide = True
        uvTransform0 = nodes['OBJEX_TransformUV0']
        uvTransform1 = nodes['OBJEX_TransformUV1']

        if 'OBJEX_PrimColorRGB' not in nodes:
            primColorRGB = nodes.new('ShaderNodeRGB')
            primColorRGB.name = 'OBJEX_PrimColorRGB'
            primColorRGB.label = 'Primitive Color RGB'
            primColorRGB.location = (100, 450)
            primColorRGB.outputs[0].default_value = (1,1,1,1)
        else:
            primColorRGB = nodes['OBJEX_PrimColorRGB']
        if 'OBJEX_EnvColorRGB' not in nodes:
            envColorRGB = nodes.new('ShaderNodeRGB')
            envColorRGB.name = 'OBJEX_EnvColorRGB'
            envColorRGB.label = 'Environment Color RGB'
            envColorRGB.location = (100, 250)
            envColorRGB.outputs[0].default_value = (1,1,1,1)
        else:
            envColorRGB = nodes['OBJEX_EnvColorRGB']

        if 'OBJEX_Texel0Texture' not in nodes:
            texel0texture = nodes.new('ShaderNodeTexture')
            texel0texture.name = 'OBJEX_Texel0Texture'
            texel0texture.label = 'Texel 0 Texture'
            texel0texture.location = (100, 50)
        else:
            texel0texture = nodes['OBJEX_Texel0Texture']
        if 'OBJEX_Texel1Texture' not in nodes:
            texel1texture = nodes.new('ShaderNodeTexture')
            texel1texture.name = 'OBJEX_Texel1Texture'
            texel1texture.label = 'Texel 1 Texture'
            texel1texture.location = (100, -250)
        else:
            texel1texture = nodes['OBJEX_Texel1Texture']

        if 'OBJEX_PrimColor' not in nodes:
            primColor = nodes.new('ShaderNodeGroup')
            primColor.node_tree = bpy.data.node_groups['OBJEX_rgba_pipe']
            primColor.name = 'OBJEX_PrimColor'
            primColor.label = 'Primitive Color'
            primColor.location = (300, 400)
            primColor.outputs[0].flagColorCycle = 'G_CCMUX_PRIMITIVE'
            primColor.outputs[1].flagColorCycle = 'G_CCMUX_PRIMITIVE_ALPHA'
            primColor.outputs[0].flagAlphaCycle = ''
            primColor.outputs[1].flagAlphaCycle = 'G_ACMUX_PRIMITIVE'
        else:
            primColor = nodes['OBJEX_PrimColor']

        if 'OBJEX_EnvColor' not in nodes:
            envColor = nodes.new('ShaderNodeGroup')
            envColor.node_tree = bpy.data.node_groups['OBJEX_rgba_pipe']
            envColor.name = 'OBJEX_EnvColor'
            envColor.label = 'Environment Color'
            envColor.location = (300, 250)
            envColor.outputs[0].flagColorCycle = 'G_CCMUX_ENVIRONMENT'
            envColor.outputs[1].flagColorCycle = 'G_CCMUX_ENV_ALPHA'
            envColor.outputs[0].flagAlphaCycle = ''
            envColor.outputs[1].flagAlphaCycle = 'G_ACMUX_ENVIRONMENT'
        else:
            envColor = nodes['OBJEX_EnvColor']
        
        if 'OBJEX_Texel0' not in nodes:
            texel0 = nodes.new('ShaderNodeGroup')
            texel0.node_tree = bpy.data.node_groups['OBJEX_rgba_pipe']
            texel0.name = 'OBJEX_Texel0'
            texel0.label = 'Texel 0'
            texel0.location = (300, 100)
            texel0.outputs[0].flagColorCycle = 'G_CCMUX_TEXEL0'
            texel0.outputs[1].flagColorCycle = 'G_CCMUX_TEXEL0_ALPHA'
            texel0.outputs[0].flagAlphaCycle = ''
            texel0.outputs[1].flagAlphaCycle = 'G_ACMUX_TEXEL0'
        else:
            texel0 = nodes['OBJEX_Texel0']
        if 'OBJEX_Texel1' not in nodes:
            texel1 = nodes.new('ShaderNodeGroup')
            texel1.node_tree = bpy.data.node_groups['OBJEX_rgba_pipe']
            texel1.name = 'OBJEX_Texel1'
            texel1.label = 'Texel 1'
            texel1.location = (300, -50)
            texel1.outputs[0].flagColorCycle = 'G_CCMUX_TEXEL1'
            texel1.outputs[1].flagColorCycle = 'G_CCMUX_TEXEL1_ALPHA'
            texel1.outputs[0].flagAlphaCycle = ''
            texel1.outputs[1].flagAlphaCycle = 'G_ACMUX_TEXEL1'
        else:
            texel1 = nodes['OBJEX_Texel1']
        
        if 'OBJEX_Shade' not in nodes:
            shade = nodes.new('ShaderNodeGroup')
            shade.node_tree = bpy.data.node_groups['OBJEX_rgba_pipe']
            shade.name = 'OBJEX_Shade'
            shade.label = 'Shade'
            shade.location = (300, -200)
            shade.outputs[0].flagColorCycle = 'G_CCMUX_SHADE'
            shade.outputs[1].flagColorCycle = 'G_CCMUX_SHADE_ALPHA'
            shade.outputs[0].flagAlphaCycle = ''
            shade.outputs[1].flagAlphaCycle = 'G_ACMUX_SHADE'
        else:
            shade = nodes['OBJEX_Shade']
        
        if 'OBJEX_Color0' not in nodes:
            color0 = nodes.new('ShaderNodeGroup')
            color0.node_tree = bpy.data.node_groups['OBJEX_Color0']
            color0.name = 'OBJEX_Color0'
            color0.label = 'Color 0'
            color0.location = (300, -350)
            color0.outputs[0].flagColorCycle = 'G_CCMUX_0'
            color0.outputs[0].flagAlphaCycle = 'G_ACMUX_0'
        else:
            color0 = nodes['OBJEX_Color0']
        if 'OBJEX_Color1' not in nodes:
            color1 = nodes.new('ShaderNodeGroup')
            color1.node_tree = bpy.data.node_groups['OBJEX_Color1']
            color1.name = 'OBJEX_Color1'
            color1.label = 'Color 1'
            color1.location = (300, -430)
            color1.outputs[0].flagColorCycle = 'G_CCMUX_1'
            color1.outputs[0].flagAlphaCycle = 'G_ACMUX_1'
        else:
            color1 = nodes['OBJEX_Color1']
        
        if 'OBJEX_ColorCycle0' not in nodes:
            cc0 = nodes.new('ShaderNodeGroup')
            cc0.node_tree = bpy.data.node_groups['OBJEX_Cycle']
            cc0.name = 'OBJEX_ColorCycle0'
            cc0.label = 'Color Cycle 0'
            cc0.location = (500, 250)
            cc0.width = 200
            cc0.outputs[0].flagColorCycle = 'G_CCMUX_COMBINED'
            cc0['cycle'] = CST.CYCLE_COLOR
        else:
            cc0 = nodes['OBJEX_ColorCycle0']
        if 'OBJEX_ColorCycle1' not in nodes:
            cc1 = nodes.new('ShaderNodeGroup')
            cc1.node_tree = bpy.data.node_groups['OBJEX_Cycle']
            cc1.name = 'OBJEX_ColorCycle1'
            cc1.label = 'Color Cycle 1'
            cc1.location = (750, 250)
            cc1.width = 200
            cc1['cycle'] = CST.CYCLE_COLOR
        else:
            cc1 = nodes['OBJEX_ColorCycle1']
        
        if 'OBJEX_AlphaCycle0' not in nodes:
            ac0 = nodes.new('ShaderNodeGroup')
            ac0.node_tree = bpy.data.node_groups['OBJEX_Cycle']
            ac0.name = 'OBJEX_AlphaCycle0'
            ac0.label = 'Alpha Cycle 0'
            ac0.location = (500, -50)
            ac0.width = 200
            ac0.outputs[0].flagColorCycle = 'G_CCMUX_COMBINED_ALPHA'
            ac0.outputs[0].flagAlphaCycle = 'G_ACMUX_COMBINED'
            ac0['cycle'] = CST.CYCLE_ALPHA
        else:
            ac0 = nodes['OBJEX_AlphaCycle0']
        if 'OBJEX_AlphaCycle1' not in nodes:
            ac1 = nodes.new('ShaderNodeGroup')
            ac1.node_tree = bpy.data.node_groups['OBJEX_Cycle']
            ac1.name = 'OBJEX_AlphaCycle1'
            ac1.label = 'Alpha Cycle 1'
            ac1.location = (750, -50)
            ac1.width = 200
            ac1['cycle'] = CST.CYCLE_ALPHA
        else:
            ac1 = nodes['OBJEX_AlphaCycle1']
        
        if 'Output' not in nodes:
            output = nodes.new('ShaderNodeOutput')
            output.name = 'Output'
            output.location = (1000, 100)
        else:
            output = nodes['Output']
        
        # decoration
        if 'OBJEX_Frame_CombinerInputs' not in nodes:
            frame = nodes.new('NodeFrame')
            frame.name = 'OBJEX_Frame_CombinerInputs'
            frame.label = 'Combiner Inputs'
        for n in (primColor, envColor, texel0, texel1, shade, color0, color1):
            n.parent = frame

        # texel0
        node_tree.links.new(geometry.outputs['UV'], uvTransform0.inputs['UV'])
        node_tree.links.new(uvTransform0.outputs[0], texel0texture.inputs[0])
        node_tree.links.new(texel0texture.outputs[1], texel0.inputs[0])
        node_tree.links.new(texel0texture.outputs[0], texel0.inputs[1])
        # texel1
        node_tree.links.new(geometry.outputs['UV'], uvTransform1.inputs['UV'])
        node_tree.links.new(uvTransform1.outputs[0], texel1texture.inputs[0])
        node_tree.links.new(texel1texture.outputs[1], texel1.inputs[0])
        node_tree.links.new(texel1texture.outputs[0], texel1.inputs[1])
        # envColor, primColor RGB
        node_tree.links.new(primColorRGB.outputs[0], primColor.inputs[0])
        node_tree.links.new(envColorRGB.outputs[0], envColor.inputs[0])
        # shade
        # vertex colors (do not use by default as it would make shade (0,0,0,0))
        #node_tree.links.new(geometry.outputs['Vertex Color'], shade.inputs[0])
        #node_tree.links.new(geometry.outputs['Vertex Alpha'], shade.inputs[1])
        # 421todo implement lighting calculations
        # for now, use opaque white shade
        node_tree.links.new(color1.outputs[0], shade.inputs[0])
        node_tree.links.new(color1.outputs[0], shade.inputs[1])
        # cycle 0: (TEXEL0 - 0) * PRIM  + 0
        node_tree.links.new(texel0.outputs[0], cc0.inputs['A'])
        # an alternative to the above line:
        #cc0.inputs['A'].input_flags_C_A = 'G_CCMUX_TEXEL0'
        node_tree.links.new(primColor.outputs[0], cc0.inputs['C'])
        node_tree.links.new(texel0.outputs[1], ac0.inputs['A'])
        node_tree.links.new(primColor.outputs[1], ac0.inputs['C'])
        # cycle 1: (RESULT - 0) * SHADE + 0
        node_tree.links.new(cc0.outputs[0], cc1.inputs['A'])
        node_tree.links.new(shade.outputs[0], cc1.inputs['C'])
        node_tree.links.new(ac0.outputs[0], ac1.inputs['A'])
        node_tree.links.new(shade.outputs[1], ac1.inputs['C'])
        # combiners output
        node_tree.links.new(cc1.outputs[0], output.inputs[0])
        node_tree.links.new(ac1.outputs[0], output.inputs[1])

        material.objex_bonus.is_objex_material = True

        return {'FINISHED'}

# properties and non-node UI

class OBJEX_PT_material(bpy.types.Panel):
    bl_label = 'Objex'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'material'
    
    @classmethod
    def poll(self, context):
        material = context.material
        return material is not None
    
    def draw(self, context):
        material = context.material
        data = material.objex_bonus
        # setup operators
        if not data.is_objex_material:
            self.layout.operator('OBJEX_OT_material_init', text='Init Objex material')
            return
        # handle is_objex_material, use_nodes mismatch
        if not material.use_nodes:
            self.layout.label(text='Material was initialized', icon='ERROR')
            self.layout.label(text='as an objex material')
            self.layout.label(text='but does not use nodes')
            self.layout.label(text='Did you uncheck')
            self.layout.label(text='"Use Nodes" for it?')
            self.layout.label(text='Solutions:', icon='INFO')
            box = self.layout.box()
            box.label('1) Check "Use Nodes"')
            box.prop(material, 'use_nodes')
            # 421todo "clear objex material" operator "Click here to make this a standard, non-objex, material"
            # would allow ctrl+z
            box = self.layout.box()
            box.label('2) Disable objex features')
            box.label('for this material')
            box.prop(data, 'is_objex_material')
            box = self.layout.box()
            box.label('3) Reset nodes')
            box.operator('OBJEX_OT_material_init', text='Reset nodes')
            return
        self.layout.operator('OBJEX_OT_material_init', text='Reset nodes')
        self.layout.operator('OBJEX_OT_material_multitexture', text='Multitexture')
        # 421todo more quick-setup operators
        # often-used options
        self.layout.prop(data, 'backface_culling')
        self.layout.prop(data, 'frontface_culling')
        for prop in ('write_primitive_color','write_environment_color'):
            if getattr(data, prop) == 'GLOBAL':
                box = self.layout.box()
                box.prop(data, prop)
                box.prop(context.scene.objex_bonus, prop)
            else:
                self.layout.prop(data, prop)
        self.layout.prop(data, 'use_texgen')
        # texel0/1 image properties
        for textureNode in (n for n in material.node_tree.nodes if n.bl_idname == 'ShaderNodeTexture' and n.texture):
            box = self.layout.box()
            image = textureNode.texture.image
            if not image:
                continue
            box.label(text=image.filepath if image.filepath else 'Image without filepath?')
            box.prop(textureNode.texture, 'image')
            imdata = image.objex_bonus
            box.prop(imdata, 'format')
            if imdata.format[:2] == 'CI':
                box.prop(imdata, 'palette')
            propOffset(box, imdata, 'pointer', 'Pointer')
            box.prop(imdata, 'priority')
            box.prop(imdata, 'force_write')
            row = box.row()
            row.label(text='Texture bank:')
            row.template_ID(imdata, 'texture_bank', open='image.open')
        # less used properties
        if material.name.startswith('empty.'):
            self.layout.label(text='empty (material name starts with "empty.")', icon='CHECKBOX_HLT')
        else:
            self.layout.prop(data, 'empty')
        if data.empty or material.name.startswith('empty.'):
            self.layout.prop(data, 'branch_to_object')
        self.layout.prop(data, 'standalone')
        self.layout.prop(data, 'force_write')
        # other mode, lower half (blender settings)
        box = self.layout.box()
        box.label(text='Render mode')
        box.prop(data, 'rendermode_blender_flag_AA_EN')
        box.prop(data, 'rendermode_blender_flag_Z_CMP')
        box.prop(data, 'rendermode_blender_flag_Z_UPD')
        box.prop(data, 'rendermode_blender_flag_IM_RD')
        box.prop(data, 'rendermode_blender_flag_CLR_ON_CVG')
        box.prop(data, 'rendermode_blender_flag_CVG_DST_')
        box.prop(data, 'rendermode_zmode')
        box.prop(data, 'rendermode_blender_flag_CVG_X_ALPHA')
        box.prop(data, 'rendermode_blender_flag_ALPHA_CVG_SEL')
        box.prop(data, 'rendermode_forceblending')
        box.prop(data, 'rendermode_blending_cycle0')
        if data.rendermode_blending_cycle0 == 'CUSTOM':
            for v in ('P','A','M','B'):
                box.prop(data, 'rendermode_blending_cycle0_custom_%s' % v)
        box.prop(data, 'rendermode_blending_cycle1')
        if data.rendermode_blending_cycle1 == 'CUSTOM':
            for v in ('P','A','M','B'):
                box.prop(data, 'rendermode_blending_cycle1_custom_%s' % v)
        # other rarely-used or auto settings
        self.layout.prop(data, 'vertex_shading')
        self.layout.prop(data, 'geometrymode_G_FOG')
        if data.geometrymode_G_FOG == 'NO':
            self.layout.label(text='G_FOG off does not disable fog', icon='ERROR')
        self.layout.prop(data, 'geometrymode_G_ZBUFFER')
        self.layout.prop(data, 'scaleS')
        self.layout.prop(data, 'scaleT')

class OBJEX_OT_material_multitexture(bpy.types.Operator):

    bl_idname = 'objex.material_multitexture'
    bl_label = 'Configures nodes of an objex material for multitextures'
    bl_options = {'REGISTER', 'UNDO'}

    # Cannot use PointerProperty in operators unfortunately...
    texel0 = bpy.props.StringProperty(
            name='Image 1',
            description='The first of the two images to use'
        )
    texel1 = bpy.props.StringProperty(
            name='Image 2',
            description='The second of the two images to use'
        )
    alpha = bpy.props.FloatProperty(
            name='Factor',
            description='How to blend the two images together\n'
                        '1 -> 100% Image 1\n'
                        '0 -> 100% Image 2',
            min=0, max=1, step=0.01, precision=2,
            default=1
        )

    def draw(self, context):
        layout = self.layout
        layout.operator('image.open')
        layout.prop_search(self, 'texel0', bpy.data, 'images')
        layout.prop_search(self, 'texel1', bpy.data, 'images')
        layout.prop(self, 'alpha')

    @classmethod
    def poll(self, context):
        material = context.material if hasattr(context, 'material') else None
        return material and material.objex_bonus.is_objex_material

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        material = context.material
        tree = material.node_tree
        for texel, n in ((self.texel0,'0'),(self.texel1,'1')):
            if not texel or texel not in bpy.data.images:
                return {'CANCELLED'}
            texture = bpy.data.textures.new(texel, 'IMAGE')
            texture.image = bpy.data.images[texel]
            tree.nodes['OBJEX_Texel%sTexture' % n].texture = texture
        tree.nodes['OBJEX_EnvColor'].inputs['Alpha'].default_value = self.alpha
        cc0 = tree.nodes['OBJEX_ColorCycle0']
        cc1 = tree.nodes['OBJEX_ColorCycle1']
        ac0 = tree.nodes['OBJEX_AlphaCycle0']
        ac1 = tree.nodes['OBJEX_AlphaCycle1']
        # color cycles
        cc0.inputs['A'].input_flags_C_A = 'G_CCMUX_TEXEL0'
        cc0.inputs['B'].input_flags_C_B = 'G_CCMUX_TEXEL1'
        cc0.inputs['C'].input_flags_C_C = 'G_CCMUX_ENV_ALPHA'
        cc0.inputs['D'].input_flags_C_D = 'G_CCMUX_TEXEL1'
        # todo more parameters for second cycle
        #cc1.inputs['A'].input_flags_C_A = 'G_CCMUX_COMBINED'
        tree.links.new(cc0.outputs[0], cc1.inputs['A'])
        cc1.inputs['B'].input_flags_C_B = 'G_CCMUX_0'
        cc1.inputs['C'].input_flags_C_C = 'G_CCMUX_SHADE'
        cc1.inputs['D'].input_flags_C_D = 'G_CCMUX_0'
        # alpha cycles
        ac0.inputs['A'].input_flags_A_A = 'G_ACMUX_TEXEL0'
        ac0.inputs['B'].input_flags_A_B = 'G_ACMUX_TEXEL1'
        ac0.inputs['C'].input_flags_A_C = 'G_ACMUX_ENVIRONMENT'
        ac0.inputs['D'].input_flags_A_D = 'G_ACMUX_TEXEL1'
        #ac1.inputs['A'].input_flags_A_A = 'G_ACMUX_COMBINED'
        tree.links.new(ac0.outputs[0], ac1.inputs['A'])
        ac1.inputs['B'].input_flags_A_B = 'G_ACMUX_0'
        ac1.inputs['C'].input_flags_A_C = 'G_ACMUX_SHADE'
        ac1.inputs['D'].input_flags_A_D = 'G_ACMUX_0'
        return {'FINISHED'}

classes = (
    OBJEX_PT_mesh,

    OBJEX_UL_actions,
    OBJEX_PT_armature,

    # order matters: each socket interface must be registered before its matching socket
    OBJEX_NodeSocketInterface_CombinerOutput,
    OBJEX_NodeSocketInterface_CombinerInput,
    OBJEX_NodeSocketInterface_RGBA_Color,
    OBJEX_NodeSocket_CombinerOutput,
    OBJEX_NodeSocket_CombinerInput,
    OBJEX_NodeSocket_RGBA_Color,

    OBJEX_OT_material_init,
    OBJEX_OT_material_multitexture,
    OBJEX_PT_material,
)

def register_interface():
    log = getLogger('interface')
    for clazz in classes:
        try:
            bpy.utils.register_class(clazz)
        except:
            log.exception('Failed to register {!r}', clazz)
            raise
    for class_name_suffix, target_socket_name, mixin in (
        ('UVpipe_ScaleU', 'U Scale Exponent Float', OBJEX_NodeSocket_IntProperty),
        ('UVpipe_ScaleV', 'V Scale Exponent Float', OBJEX_NodeSocket_IntProperty),
        ('UVpipe_WrapU', 'Wrap U (0/1)', OBJEX_NodeSocket_BoolProperty),
        ('UVpipe_WrapV', 'Wrap V (0/1)', OBJEX_NodeSocket_BoolProperty),
        ('UVpipe_MirrorU', 'Mirror U (0/1)', OBJEX_NodeSocket_BoolProperty),
        ('UVpipe_MirrorV', 'Mirror V (0/1)', OBJEX_NodeSocket_BoolProperty),
    ):
        socket_interface_class = type(
            'OBJEX_NodeSocketInterface_%s' % class_name_suffix,
            (bpy.types.NodeSocketInterface, OBJEX_NodeSocketInterface_Dummy),
            dict()
        )
        socket_class_name = 'OBJEX_NodeSocket_%s' % class_name_suffix
        socket_interface_class.bl_socket_idname = socket_class_name
        socket_class = type(
            socket_class_name,
            (bpy.types.NodeSocket, mixin),
            {'target_socket_name': target_socket_name}
        )
        bpy.utils.register_class(socket_interface_class)
        bpy.utils.register_class(socket_class)

def unregister_interface():
    for clazz in reversed(classes):
        try:
            bpy.utils.unregister_class(clazz)
        except:
            log.exception('Failed to unregister {!r}', clazz)
