from . import blender_version_compatibility

import bpy
import mathutils
import re
from math import pi

from . import const_data as CST
from . import data_updater
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
        scene = context.scene
        object = context.object
        data = object.data.objex_bonus # ObjexMeshProperties
        self.layout.prop(data, 'priority')
        self.layout.prop(data, 'write_origin')
        self.layout.prop(data, 'attrib_billboard')
        self.layout.prop(data, 'attrib_POSMTX')
        armature = object.find_armature()
        if armature:
            self.layout.prop(data, 'attrib_PROXY')
            self.layout.prop(data, 'attrib_NOSPLIT')
            if data.attrib_NOSPLIT:
                self.layout.label(text='NOSKEL (implied by NOSPLIT)', icon='CHECKBOX_HLT')
            else:
                self.layout.prop(data, 'attrib_NOSKEL')
            self.layout.prop(data, 'attrib_LIMBMTX')
            self.layout.operator('objex.mesh_find_multiassigned_vertices', text='Find multiassigned vertices')
            self.layout.operator('objex.mesh_find_unassigned_vertices', text='Find unassigned vertices')
            self.layout.operator('objex.mesh_list_vertex_groups', text='List groups of selected vertex')
            # folding/unfolding
            # 421fixme ... does this belong in mesh data tab? may want to (also) put it in armature data tab
            # or make a new panel showing for both armature and mesh
            self.layout.separator()
            self.layout.label(text='Folding')
            # 421todo make it easier/more obvious to use...
            # 421todo export/import saved poses
            row = self.layout.row()
            row.operator('objex.autofold_save_pose', text='Save pose')
            row.operator('objex.autofold_restore_pose', text='Restore pose')
            row = self.layout.row()
            row.operator('objex.autofold_fold_unfold', text='Fold').action = 'FOLD'
            row.operator('objex.autofold_fold_unfold', text='Unfold').action = 'UNFOLD'
            row.operator('objex.autofold_fold_unfold', text='Switch').action = 'SWITCH'
            # 421todo better saved poses management (delete)
            # 'OBJEX_SavedPose' does not refer to any addon-defined class. see documentation
            self.layout.label(text='Default saved pose to use for folding:')
            self.layout.template_list('UI_UL_list', 'OBJEX_SavedPose', scene.objex_bonus, 'saved_poses', armature.data.objex_bonus, 'fold_unfold_saved_pose_index', rows=2)
            """
            self.layout.prop(armature, 'fold_unfold_saved_pose_index')
            self.layout.prop_search(armature, 'fold_unfold_saved_pose_name', scene, 'saved_poses')
            """


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
                    valid_bone = data.pbody_parent_bone in data.pbody_parent_object.data.bones
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
        layout.label(text=text)
        #layout.label(text='%s/%s' % (stripPrefix(self.flagColorCycle, 'G_CCMUX_'), stripPrefix(self.flagAlphaCycle, 'G_ACMUX_')))
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
                items=sorted(
                    (flag, stripPrefix(flag, CST.COMBINER_FLAGS_PREFIX[cycle]), flag)
                        for flag in CST.COMBINER_FLAGS_SUPPORT[cycle][variable]
                        # 421todo can't implement these without using cycle number:
                        if flag not in ('G_CCMUX_COMBINED','G_CCMUX_COMBINED_ALPHA','G_ACMUX_COMBINED')
                ) + [('_','...','')],
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

def addMathNodeTree(tree, operation, location, in0=None, in1=None):
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
    return n.outputs[0]

def create_node_group_uv_pipe_main(group_name):
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    inputs_node = tree.nodes.new('NodeGroupInput')
    inputs_node.location = (-1000,150)
    tree.inputs.new('NodeSocketVector', 'UV')
    tree.inputs.new('NodeSocketVector', 'Normal')
    tree.inputs.new('OBJEX_NodeSocket_UVpipe_main_Texgen', 'Texgen')
    tree.inputs.new('OBJEX_NodeSocket_UVpipe_main_TexgenLinear', 'Texgen Linear')
    for uv in ('U','V'):
        scale = tree.inputs.new('NodeSocketFloat', '%s Scale' % uv)
        scale.default_value = 1
        scale.min_value = 0
        scale.max_value = 1
    tree.inputs.new('NodeSocketFloat', 'Texgen (0/1)')
    tree.inputs.new('NodeSocketFloat', 'Texgen Linear (0/1)')

    # texgen math based on GLideN64/src/gSP.cpp (see G_TEXTURE_GEN in gSPProcessVertex)

    separateUV = tree.nodes.new('ShaderNodeSeparateXYZ')
    separateUV.location = (-800,300)
    tree.links.new(inputs_node.outputs['UV'], separateUV.inputs[0])

    transformNormal = tree.nodes.new('ShaderNodeVectorTransform')
    transformNormal.location = (-800,-100)
    tree.links.new(inputs_node.outputs['Normal'], transformNormal.inputs[0])
    transformNormal.vector_type = 'VECTOR'
    transformNormal.convert_from = 'OBJECT'
    transformNormal.convert_to = 'CAMERA'

    normalize = tree.nodes.new('ShaderNodeVectorMath')
    normalize.location = (-600,-100)
    tree.links.new(transformNormal.outputs[0], normalize.inputs[0])
    normalize.operation = 'NORMALIZE'

    separateUVtexgen = tree.nodes.new('ShaderNodeSeparateXYZ')
    separateUVtexgen.location = (-400,-100)
    tree.links.new(normalize.outputs[0], separateUVtexgen.inputs[0])

    def addMathNode(operation, location, in0=None, in1=None):
        return addMathNodeTree(tree, operation, location, in0, in1)

    texgenOn = inputs_node.outputs['Texgen (0/1)']
    texgenOff = addMathNode('SUBTRACT', (-600,500), 1, texgenOn)

    texgenLinear = inputs_node.outputs['Texgen Linear (0/1)']
    texgenLinearNot = addMathNode('SUBTRACT', (-600,-300), 1, texgenLinear)

    frameLinear = tree.nodes.new('NodeFrame')
    frameLinear.label = '_LINEAR'
    final = {}
    for uv, i, y in (('U',0,100),('V',1,-200)):
        d = -200 if uv == 'V' else 200
        texgenNotLinear = separateUVtexgen.outputs[i]
        texgenNotLinearPart = addMathNode('MULTIPLY', (-200,d+y), texgenLinearNot, texgenNotLinear)
        multMin1 = addMathNode('MULTIPLY', (-200,y), texgenNotLinear, -1)
        acos = addMathNode('ARCCOSINE', (0,y), multMin1)
        divPi = addMathNode('DIVIDE', (200,y), acos, pi)
        mult2 = addMathNode('MULTIPLY', (400,y), divPi, 2)
        sub1 = addMathNode('SUBTRACT', (600,y), mult2, 1)
        for s in (multMin1, acos, divPi, mult2, sub1):
            s.node.parent = frameLinear
        texgenLinearPart = addMathNode('MULTIPLY', (800,d+y), texgenLinear, sub1)
        finalIfTexgen = addMathNode('ADD', (1000,y), texgenNotLinearPart, texgenLinearPart)
        trulyFinalIfTexgen = addMathNode('MULTIPLY', (1200,y), finalIfTexgen, 50)
        texgenPart = addMathNode('MULTIPLY', (1400,d+y), texgenOn, trulyFinalIfTexgen)
        noTexgenPart = addMathNode('MULTIPLY', (1100,d+y), texgenOff, separateUV.outputs[i])
        onlyScaleLeft = addMathNode('ADD', (1600,y), texgenPart, noTexgenPart)
        final[uv] = addMathNode('MULTIPLY', (1800,y), onlyScaleLeft, inputs_node.outputs['%s Scale' % uv])

    combineXYZ = tree.nodes.new('ShaderNodeCombineXYZ')
    combineXYZ.location = (2000,100)
    tree.links.new(final['U'], combineXYZ.inputs[0])
    tree.links.new(final['V'], combineXYZ.inputs[1])

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (2200,100)
    tree.outputs.new('NodeSocketVector', 'UV')
    tree.links.new(combineXYZ.outputs[0], outputs_node.inputs['UV'])

    return tree

def create_node_group_uv_pipe(group_name):
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

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
    separateXYZ.location = (-800,100)
    tree.links.new(inputs_node.outputs['UV'], separateXYZ.inputs[0])

    def addMathNode(operation, location, in0=None, in1=None):
        return addMathNodeTree(tree, operation, location, in0, in1)

    final = {}
    for uv, i, y in (('U',0,400),('V',1,-600)):
        # looking at the nodes in blender is probably better than trying to understand the code here
        # (-1 ; 1) -> (0 ; 1)
        ranged02 = addMathNode('ADD', (-600,200+y), separateXYZ.outputs[i], 1)
        ranged01 = addMathNode('DIVIDE', (-400,200+y), ranged02, 2)
        # blender uses bottom left as (u,v)=(0,0) but oot uses top left as (0,0),
        # so we mirror v around 1/2
        if uv == 'V':
            uv64space = addMathNode('SUBTRACT', (-200,200+y), 1, ranged01)
        else:
            uv64space = ranged01
        # scale from exponent
        roundedExp = addMathNode('ROUND', (-400,400+y), inputs_node.outputs['%s Scale Exponent Float' % uv])
        scalePow = addMathNode('POWER', (-200,400+y), 2, roundedExp)
        scale = addMathNode('MULTIPLY', (0,400+y), uv64space, scalePow)
        # mirror
        notMirroredBool = addMathNode('SUBTRACT', (200,600+y), 1, inputs_node.outputs['Mirror %s (0/1)' % uv])
        identity = addMathNode('MULTIPLY', (400,400+y), scale, notMirroredBool)
        reversed = addMathNode('MULTIPLY', (200,200+y), scale, -1)
        mod2_1 = addMathNode('MODULO', (400,0+y), scale, 2)
        add2 = addMathNode('ADD', (600,0+y), mod2_1, 2)
        mod2_2 = addMathNode('MODULO', (800,0+y), add2, 2)
        notMirroredPartBool = addMathNode('LESS_THAN', (1000,0+y), mod2_2, 1)
        mirroredPartNo = addMathNode('MULTIPLY', (1200,400+y), scale, notMirroredPartBool)
        mirroredPartBool = addMathNode('SUBTRACT', (1200,0+y), 1, notMirroredPartBool)
        mirroredPartYes = addMathNode('MULTIPLY', (1400,200+y), reversed, mirroredPartBool)
        withMirror = addMathNode('ADD', (1600,300+y), mirroredPartYes, mirroredPartNo)
        mirrored = addMathNode('MULTIPLY', (1800,400+y), withMirror, inputs_node.outputs['Mirror %s (0/1)' % uv])
        mirroredFinal = addMathNode('ADD', (2000,300+y), identity, mirrored)
        # wrapped (identity)
        wrapped = addMathNode('MULTIPLY', (2200,400+y), mirroredFinal, inputs_node.outputs['Wrap %s (0/1)' % uv])
        # clamped (in [0;1])
        pixelSizeUVspace  = addMathNode('DIVIDE', (1800,100+y), 1, inputs_node.outputs['Pixels along %s' % uv])
        upperBound = addMathNode('SUBTRACT', (2000,0+y), 1, pixelSizeUVspace)
        lowerBound = addMathNode('ADD', (2000,-300+y), 0, pixelSizeUVspace)
        upperClamped = addMathNode('MINIMUM', (2300,200+y), mirroredFinal, upperBound)
        upperLowerClamped = addMathNode('MAXIMUM', (2500,200+y), upperClamped, lowerBound)
        notWrap = addMathNode('SUBTRACT', (2400,0+y), 1, inputs_node.outputs['Wrap %s (0/1)' % uv])
        clamped = addMathNode('MULTIPLY', (2700,200+y), upperLowerClamped, notWrap)
        #
        final64space = addMathNode('ADD', (2900,300+y), wrapped, clamped)
        # (0 ; 1) -> (-1 ; 1)
        if uv == 'V':
            final01range = addMathNode('SUBTRACT', (3000,500+y), 1, final64space)
        else:
            final01range = final64space
        final02range = addMathNode('MULTIPLY', (3100,300+y), final01range, 2)
        final[uv] = addMathNode('SUBTRACT', (3300,300+y), final02range, 1)
    finalU = final['U']
    finalV = final['V']

    # out

    combineXYZ = tree.nodes.new('ShaderNodeCombineXYZ')
    combineXYZ.location = (3500,100)
    tree.links.new(finalU, combineXYZ.inputs[0])
    tree.links.new(finalV, combineXYZ.inputs[1])

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (3700,100)
    tree.outputs.new('NodeSocketVector', 'UV')
    tree.links.new(combineXYZ.outputs[0], outputs_node.inputs['UV'])

    return tree

def create_node_group_rgba_pipe(group_name):
    """
    "Casts" input for use as cycle inputs
    Inputs: OBJEX_NodeSocket_RGBA_Color 'Color', NodeSocketFloat 'Alpha'
    Outputs: OBJEX_NodeSocket_CombinerOutput 'Color', OBJEX_NodeSocket_CombinerOutput 'Alpha'
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
    tree.outputs.new('OBJEX_NodeSocket_CombinerOutput', 'Color')
    tree.outputs.new('OBJEX_NodeSocket_CombinerOutput', 'Alpha')
    tree.links.new(inputs_node.outputs[0], outputs_node.inputs['Color'])
    tree.links.new(alpha_3d.outputs[0], outputs_node.inputs['Alpha'])

    return tree

# 421fixme check this function still behaves as expected since the updater code was ditched
def update_node_groups():
    # dict mapping group names (keys in bpy.data.node_groups) to (latest_version, create_function) tuples
    # version is stored in 'objex_version' for each group and compared to latest_version
    # usage: increment associated latest_version when making changes in the create_function of some group
    # WARNING: bumping version here is not enough, material version should be bumped too (see data_updater.py)
    groups = {
        'OBJEX_Cycle': (1, create_node_group_cycle),
        'OBJEX_Color0': (1, lambda group_name: create_node_group_color_static(group_name, (0,0,0,0), '0')),
        'OBJEX_Color1': (1, lambda group_name: create_node_group_color_static(group_name, (1,1,1,1), '1')),
        'OBJEX_UV_pipe_main': (1, create_node_group_uv_pipe_main),
        'OBJEX_UV_pipe': (2, create_node_group_uv_pipe),
        'OBJEX_rgba_pipe': (2, create_node_group_rgba_pipe),
    }
    for group_name, (latest_version, group_create) in groups.items():
        old_node_group = None
        current_node_group = bpy.data.node_groups.get(group_name)
        # if current_node_group is outdated
        if current_node_group and (
            'objex_version' not in current_node_group
            or current_node_group['objex_version'] < latest_version
        ):
            old_node_group = current_node_group
            old_node_group.name = '%s_old' % group_name
            current_node_group = None
        # group must be (re)created
        if not current_node_group:
            current_node_group = group_create(group_name)
            current_node_group['objex_version'] = latest_version

def draw_build_nodes_operator(
    layout, text,
    init=False, reset=False,
    create=True, update_groups_of_existing=True,
    set_looks=True, set_basic_links=True
):
    op = layout.operator('objex.material_build_nodes', text=text)
    # set every property because it looks like not setting them keeps values from last call instead of using default values
    op.init = init
    op.reset = reset
    op.create = create
    op.update_groups_of_existing = update_groups_of_existing
    op.set_looks = set_looks
    op.set_basic_links = set_basic_links

# same intent as draw_build_nodes_operator
def exec_build_nodes_operator(
    material,
    init=False, reset=False,
    create=True, update_groups_of_existing=True,
    set_looks=True, set_basic_links=True
):
    bpy.ops.objex.material_build_nodes(
        target_material_name=material.name,
        init=init, reset=reset,
        create=create, update_groups_of_existing=update_groups_of_existing,
        set_looks=set_looks, set_basic_links=set_basic_links
    )

class OBJEX_OT_material_build_nodes(bpy.types.Operator):

    bl_idname = 'objex.material_build_nodes'
    bl_label = 'Initialize a material for use on Objex export'
    bl_options = {'INTERNAL', 'UNDO'}

    # if set, use the material with this name instead of the context one
    target_material_name = bpy.props.StringProperty()

    # defaults for following bool properties are handled by draw_build_nodes_operator and exec_build_nodes_operator

    # indicates the material is becoming an objex material for the first time
    # soft resets by removing nodes that serve no purpose (meant to remove default nodes),
    # add default combiner links, and infer texel0 from face textures
    init = bpy.props.BoolProperty()
    # clear all nodes before building
    reset = bpy.props.BoolProperty()
    # create missing nodes (disabling may cause unchecked errors, set_looks and set_basic_links should be disabled too when create is disabled)
    create = bpy.props.BoolProperty()
    # for existing group nodes, set the used group to the latest
    # in the end, should have no effect unless updating a material
    update_groups_of_existing = bpy.props.BoolProperty()
    # set locations, dimensions
    set_looks = bpy.props.BoolProperty()
    # create basic links (eg vanilla RGB node OBJEX_PrimColorRGB to RGB pipe node OBJEX_PrimColor)
    set_basic_links = bpy.props.BoolProperty()

    def execute(self, context):
        log = getLogger('OBJEX_OT_material_build_nodes')

        if self.target_material_name:
            material = bpy.data.materials[self.target_material_name]
        else:
            material = context.material

        # let the user choose, as use_transparency is used when
        # exporting to distinguish opaque and translucent geometry
        #material.use_transparency = True
        material.use_nodes = True
        update_node_groups()
        node_tree = material.node_tree
        nodes = node_tree.nodes

        if self.reset:
            nodes.clear()

        # nodes are described in const_data.py
        nodes_data = CST.node_setup
        EMPTY_DICT = dict()
        EMPTY_LIST = list()

        # 1st pass: find/create nodes, set properties, looks
        for node_name, node_data in nodes_data.items():
            node_type = node_data.get('type')
            node_type_group = node_data.get('group')
            if not node_type and node_type_group:
                node_type = 'ShaderNodeGroup'
            node_inputs = node_data.get('inputs', EMPTY_DICT)
            node_outputs = node_data.get('outputs', EMPTY_DICT)
            node_outputs_combiner_flags = node_data.get('outputs-combiner-flags', EMPTY_DICT)
            node_properties_dict = node_data.get('properties-dict', EMPTY_DICT)
            node_label = node_data.get('label')
            node_location = node_data.get('location')
            node_width = node_data.get('width')
            node_hidden_inputs = node_data.get('hide-inputs', EMPTY_LIST)
            node = None
            # skip "find node" code even though with the nodes reset there
            # would be nothing to find anyway
            if not self.reset:
                # find a node with same name, or same type
                node = nodes.get(node_name)
                if not node:
                    for n in nodes:
                        if (n.bl_idname == node_type
                            and (not node_type_group
                                or (n.node_tree
                                    and n.node_tree.name == node_type_group
                        ))):
                            # ignore nodes which have a known name (and purpose)
                            if n.name in nodes_data:
                                continue
                            if node: # found several nodes
                                # prefer nodes named like targeted (eg '{node_name}.001')
                                if node_name in n.name:
                                    node = n
                                # else, keep previous match
                            else: # first match
                                node = n
            if not node and not self.create:
                log.info('Skipped creating missing node {}', node_name)
                continue # skip further actions on missing node
            if not node:
                node = nodes.new(node_type)
                if node_type_group:
                    node.node_tree = bpy.data.node_groups[node_type_group]
                for input_socket_key, default_value in node_inputs.items():
                    node.inputs[input_socket_key].default_value = default_value
                for output_socket_key, default_value in node_outputs.items():
                    node.outputs[output_socket_key].default_value = default_value
                for output_socket_key, flags in node_outputs_combiner_flags.items():
                    color_flag, alpha_flag = flags
                    node.outputs[output_socket_key].flagColorCycle = color_flag if color_flag else ''
                    node.outputs[output_socket_key].flagAlphaCycle = alpha_flag if alpha_flag else ''
                for k, v in node_properties_dict.items():
                    node[k] = v
            elif node_type_group and self.update_groups_of_existing:
                node.node_tree = bpy.data.node_groups[node_type_group]
            node.name = node_name # todo set unconditionally? won't set the name if already taken. rename others first? (set exact name needed for 2nd pass with links)
            if self.set_looks:
                if node_label:
                    node.label = node_label
                if node_location:
                    node.location = node_location
                if node_width:
                    node.width = node_width
                for hidden_input_socket_key in node_hidden_inputs:
                    node.inputs[hidden_input_socket_key].hide = True

        if self.init:
            # remove useless nodes
            # tuple() avoids modifying and iterating over nodes at the same time
            for n in tuple(n for n in nodes if n.name not in nodes_data):
                nodes.remove(n)

        # 2nd pass: parenting (frames), links
        # assumes every node described in nodes_data was created and/or named as expected in the 1st pass (unless self.create is False)
        for node_name, node_data in nodes_data.items():
            if not self.create and node_name not in nodes:
                continue # skip missing nodes (only if not self.create, as all nodes should exist otherwise)
            node = nodes[node_name]
            node_links = node_data.get('links', EMPTY_DICT)
            node_children = node_data.get('children', EMPTY_LIST)
            # warning: not checking if node_links/node_children don't refer to a non-existing node (when self.create is False)
            if self.set_basic_links:
                # todo clear links? shouldnt be needed because inputs can only have one link (but maybe old links get moved to unintended sockets like for math nodes?)
                for to_input_socket_key, from_output in node_links.items():
                    from_node_name, from_output_socket_key = from_output
                    node_tree.links.new(
                        nodes[from_node_name].outputs[from_output_socket_key],
                        node.inputs[to_input_socket_key]
                    )
            if self.set_looks:
                for child_node_name in node_children:
                    nodes[child_node_name].parent = node

        if self.set_basic_links:
            # 421todo hardcoding this for now instead of putting it into const_data.py,
            # because it's not exactly a "basic" links
            # but we can't just wait for the user to configure it as it appears as an error when unlinked
            # so, for now default to opaque white shade = lighting shading
            # shade
            # vertex colors (do not use by default as it would make shade (0,0,0,0))
            #node_tree.links.new(geometry.outputs['Vertex Color'], shade.inputs[0])
            #node_tree.links.new(geometry.outputs['Vertex Alpha'], shade.inputs[1])
            # 421todo implement lighting calculations
            # for now, use opaque white shade
            for i in (0,1):
                # do not overwrite any previous link (eg keep vertex colors links)
                if not nodes['OBJEX_Shade'].inputs[i].is_linked:
                    node_tree.links.new(nodes['OBJEX_Color1'].outputs[0], nodes['OBJEX_Shade'].inputs[i])

        if self.init:
            # infer texel0 texture from face textures
            try:
                obj = mesh = None
                context_object_is_mesh = (
                    hasattr(context, 'object')
                    and context.object
                    and context.object.type == 'MESH'
                )
                if (context_object_is_mesh
                        and not hasattr(context.object.data, 'uv_textures')
                ):
                    pass # no face textures (Blender 2.80+)
                elif (context_object_is_mesh
                        and context.object.data.uv_textures.active
                ):
                    obj = context.object
                    mesh = obj.data
                    log.debug('Searching face textures in object {} / mesh {}', obj.name, mesh.name)
                    uv_textures_data = mesh.uv_textures.active.data
                    was_edit_mode = False
                    if not uv_textures_data: # uv_textures_data is empty in edit mode
                        # assume edit mode, go to object mode
                        log.debug('-> OBJECT mode')
                        was_edit_mode = True
                        bpy.ops.object.mode_set(mode='OBJECT')
                        uv_textures_data = mesh.uv_textures.active.data
                    # find slots using our material
                    material_slot_indices = tuple( # use tuple() for speed
                        slot_index for slot_index in range(len(obj.material_slots))
                            if obj.material_slots[slot_index].material == material
                    )
                    # find face images used by faces using our material
                    face_images = set(
                        uv_textures_data[face.index].image for face in mesh.polygons
                            if face.material_index in material_slot_indices
                                and uv_textures_data[face.index].image
                    )
                    # uv_textures_data no longer needed
                    if was_edit_mode:
                        del uv_textures_data # avoid (dangling pointer?) issues
                        bpy.ops.object.mode_set(mode='EDIT')
                    # use face image in texture for texel0, if any
                    if face_images:
                        if len(face_images) > 1:
                            log.info('Found several face images {}', ', '.join(face_image.name for face_image in face_images))
                        face_image = next(iter(face_images))
                        face_image_texture = bpy.data.textures.new(face_image.name, 'IMAGE')
                        face_image_texture.image = face_image
                        texel0texture = nodes['OBJEX_Texel0Texture']
                        texel0texture.texture = face_image_texture
                    else:
                        log.debug('Found no face image')
                else:
                    log.info('Could not find a suitable object (MESH type with uvs) in context to search face textures in')
            except:
                self.report({'WARNING'}, 'Something went wrong while searching a face texture to use for texel0')
                log.exception('material = {!r} obj = {!r} mesh = {!r}', material, obj, mesh)
            # cycle 0: (TEXEL0 - 0) * PRIM  + 0
            cc0 = nodes['OBJEX_ColorCycle0']
            ac0 = nodes['OBJEX_AlphaCycle0']
            cc0.inputs['A'].input_flags_C_A = 'G_CCMUX_TEXEL0'
            cc0.inputs['C'].input_flags_C_C = 'G_CCMUX_PRIMITIVE'
            ac0.inputs['A'].input_flags_A_A = 'G_ACMUX_TEXEL0'
            ac0.inputs['C'].input_flags_A_C = 'G_ACMUX_PRIMITIVE'
            # cycle 1: (RESULT - 0) * SHADE + 0
            cc1 = nodes['OBJEX_ColorCycle1']
            ac1 = nodes['OBJEX_AlphaCycle1']
            node_tree.links.new(cc0.outputs[0], cc1.inputs['A'])
            cc1.inputs['C'].input_flags_C_C = 'G_CCMUX_SHADE'
            node_tree.links.new(ac0.outputs[0], ac1.inputs['A'])
            ac1.inputs['C'].input_flags_A_C = 'G_ACMUX_SHADE'
            # combiners output
            if hasattr(bpy.types, 'ShaderNodeOutput'): # < 2.80
                output = nodes['Output']
                node_tree.links.new(cc1.outputs[0], output.inputs[0])
                node_tree.links.new(ac1.outputs[0], output.inputs[1])
            else: # 2.80+
                principledBSDF = nodes['Principled BSDF']
                node_tree.links.new(cc1.outputs[0], principledBSDF.inputs['Base Color'])
                node_tree.links.new(ac1.outputs[0], principledBSDF.inputs['Alpha'])

        material.objex_bonus.is_objex_material = True
        material.objex_bonus.objex_version = data_updater.addon_material_objex_version

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
            draw_build_nodes_operator(self.layout, 'Init Objex material', init=True)
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
            draw_build_nodes_operator(box, 'Reset nodes', init=True, reset=True)
            return
        # update material
        if data_updater.handle_material(material, self.layout):
            self.layout.separator()
            draw_build_nodes_operator(self.layout, 'Reset nodes', init=True, reset=True)
            return
        # empty: only draw the exported properties empty, branch_to_object, branch_to_object_bone
        if data.empty or material.name.startswith('empty.'):
            self.layout.label(text='Empty materials only', icon='INFO')
            self.layout.label(text='have these few properties:')
            if material.name.startswith('empty.'):
                self.layout.label(text='empty (material name starts with "empty.")', icon='CHECKBOX_HLT')
            else:
                self.layout.prop(data, 'empty')
            self.layout.prop(data, 'branch_to_object')
            if data.branch_to_object: # branch_to_object is a MESH object
                branch_to_object_armature = data.branch_to_object.find_armature()
                if branch_to_object_armature:
                    if data.branch_to_object.data.objex_bonus.attrib_NOSPLIT:
                        self.layout.label('%s is marked NOSPLIT' % data.branch_to_object.name, icon='INFO')
                    else:
                        valid_bone = data.branch_to_object_bone in branch_to_object_armature.data.bones
                        self.layout.prop_search(data, 'branch_to_object_bone', branch_to_object_armature.data, 'bones', icon=('NONE' if valid_bone else 'ERROR'))
                        if not valid_bone:
                            self.layout.label('A bone must be picked', icon='ERROR')
                            self.layout.label('NOSPLIT is off on %s' % data.branch_to_object.name, icon='INFO')
            return
        # node operators
        row = self.layout.row()
        draw_build_nodes_operator(row, 'Reset nodes', init=True, reset=True)
        draw_build_nodes_operator(row, 'Fix nodes')
        self.layout.operator('objex.material_multitexture', text='Multitexture')
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
        # texel0/1 image properties
        images_used = set() # avoid writing the same properties twice if texel0 and texel1 use the same image
        for textureNode in (n for n in material.node_tree.nodes if n.bl_idname == 'ShaderNodeTexture' and n.texture):
            if textureNode.texture.type != 'IMAGE':
                box = self.layout.box()
                box.label(text='Texture used by node', icon='ERROR')
                box.label(text='"%s"' % textureNode.label, icon='ERROR')
                box.label(text='is of type %s.' % textureNode.texture.type, icon='ERROR')
                box.label(text='Only image textures', icon='ERROR')
                box.label(text='should be used.', icon='ERROR')
                continue
            image = textureNode.texture.image
            if not image:
                continue
            images_used.add(image)
        for image in images_used:
            box = self.layout.box()
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
        self.layout.operator('objex.set_pixels_along_uv_from_image_dimensions', text='Fix clamping')
        # less used properties
        self.layout.prop(data, 'empty') # (at this point, material isn't empty)
        self.layout.prop(data, 'standalone')
        self.layout.prop(data, 'force_write')
        self.layout.prop(data, 'priority')
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

class OBJEX_OT_set_pixels_along_uv_from_image_dimensions(bpy.types.Operator):

    bl_idname = 'objex.set_pixels_along_uv_from_image_dimensions'
    bl_label = 'Set Pixels along U/V socket values to image width/height for improved clamping accuracy'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for material in bpy.data.materials:
            if not material.objex_bonus.is_objex_material:
                continue
            for node in material.node_tree.nodes:
                if node.type != 'GROUP':
                    continue
                if node.node_tree.name != 'OBJEX_UV_pipe':
                    continue
                textureNode = node.outputs['UV'].links[0].to_node
                if not textureNode.texture:
                    continue
                image = textureNode.texture.image
                # putting *2 here is simpler than modifying the uv pipe and math nodes again
                # it halves the clamp start offset which becomes eg along U: 1/(width*2) instead of 1/width
                # it makes the offset half a pixel instead of a full pixel (in uv space)
                # so it starts clamping in the "middle" of a pixel instead of the side
                node.inputs['Pixels along U'].default_value = image.size[0] * 2
                node.inputs['Pixels along V'].default_value = image.size[1] * 2
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

    OBJEX_OT_material_build_nodes,
    OBJEX_OT_material_multitexture,
    OBJEX_OT_set_pixels_along_uv_from_image_dimensions,
    OBJEX_PT_material,
)

def register_interface():
    log = getLogger('interface')
    for clazz in classes:
        try:
            blender_version_compatibility.make_annotations(clazz)
            bpy.utils.register_class(clazz)
        except:
            log.exception('Failed to register {!r}', clazz)
            raise
    for class_name_suffix, target_socket_name, mixin in (
        # 421todo warn if texgen && clamp (clamp "takes priority" in oot but not in the node setup)
        ('UVpipe_main_Texgen', 'Texgen (0/1)', OBJEX_NodeSocket_BoolProperty),
        ('UVpipe_main_TexgenLinear', 'Texgen Linear (0/1)', OBJEX_NodeSocket_BoolProperty),
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
        blender_version_compatibility.make_annotations(socket_interface_class)
        bpy.utils.register_class(socket_interface_class)
        blender_version_compatibility.make_annotations(socket_class)
        bpy.utils.register_class(socket_class)

def unregister_interface():
    log = getLogger('interface')
    for clazz in reversed(classes):
        try:
            bpy.utils.unregister_class(clazz)
        except:
            log.exception('Failed to unregister {!r}', clazz)
