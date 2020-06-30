import bpy
import re
import traceback

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

# armature

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

class ObjexArmatureExportActionsItem(bpy.types.PropertyGroup):
    action = bpy.props.PointerProperty(
            type=bpy.types.Action,
            name='Action',
            description='',
            update=armature_export_actions_change
        )

class OBJEX_UL_actions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        layout.prop(item, 'action', text='')

class ObjexArmatureProperties(bpy.types.PropertyGroup):
    export_all_actions = bpy.props.BoolProperty(
            name='Export all actions',
            description='',
            default=True,
            update=armature_export_actions_change
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
                ('z64dummy','z64dummy','',3)
            ],
            name='Type',
            description='',
            default='z64dummy'
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
        valid_segment = re.match(r'^(?:(?:0x)?[0-9a-fA-F]|)+$', data.segment)
        box.prop(data, 'segment', icon=('NONE' if valid_segment else 'ERROR'))
        if not valid_segment:
            box.label(text='Segment must be hexadecimal')
        box.prop(data, 'segment_local')

#
# material
#

# 421todo regroup constants
class CST:
    COLOR_OK = (0,1,0,1)
    COLOR_BAD = (1,0,0,1)
    CYCLE_COLOR = 'C'
    CYCLE_ALPHA = 'A'

    # 421todo *_SHADE* is only vertex colors atm
    SUPPORTED_FLAGS_COLOR = {
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
    }

    SUPPORTED_FLAGS_ALPHA = {
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
    }

def stripPrefix(s, prefix):
    return s[len(prefix):] if s.startswith(prefix) else s

# NodeSocketInterface

class OBJEX_NodeSocketCombiner_CA_IO_Interface(bpy.types.NodeSocketInterface):
    def draw(self, context, layout):
        pass
    def draw_color(self, context):
        return CST.COLOR_OK

class OBJEX_NodeSocketCombinerColorOutputInterface(OBJEX_NodeSocketCombiner_CA_IO_Interface):
    bl_socket_idname = 'OBJEX_NodeSocketCombinerColorOutput'

class OBJEX_NodeSocketCombinerColorInputInterface(OBJEX_NodeSocketCombiner_CA_IO_Interface):
    bl_socket_idname = 'OBJEX_NodeSocketCombinerColorInput'

class OBJEX_NodeSocketCombinerAlphaOutputInterface(OBJEX_NodeSocketCombiner_CA_IO_Interface):
    bl_socket_idname = 'OBJEX_NodeSocketCombinerAlphaOutput'

class OBJEX_NodeSocketCombinerAlphaInputInterface(OBJEX_NodeSocketCombiner_CA_IO_Interface):
    bl_socket_idname = 'OBJEX_NodeSocketCombinerAlphaInput'

# NodeSocket

# used for mixin by Color/Alpha outputs
class OBJEX_NodeSocketCombiner_CA_Output():

    flagColorCycle = bpy.props.StringProperty()
    flagAlphaCycle = bpy.props.StringProperty()

    def draw(self, context, layout, node, text):
        layout.label(text='%s (%s/%s)' % (text, stripPrefix(self.flagColorCycle, 'G_CCMUX_'), stripPrefix(self.flagAlphaCycle, 'G_ACMUX_')))
        # todo "show compat" operator which makes A/B/C/D blink when they support this output?

    def draw_color(self, context, node):
        return CST.COLOR_OK

class OBJEX_NodeSocketCombinerColorOutput(bpy.types.NodeSocket, OBJEX_NodeSocketCombiner_CA_Output):
    default_value = bpy.props.FloatVectorProperty(name='default_value', default=(0.0, 0.0, 0.0), min=0, max=1, subtype='COLOR')

class OBJEX_NodeSocketCombinerAlphaOutput(bpy.types.NodeSocket, OBJEX_NodeSocketCombiner_CA_Output):
    default_value = bpy.props.FloatProperty(name='default_value', default=0, min=0, max=1)

class OBJEX_NodeSocketCombiner_CA_Input():
    def linkToFlag(self):
        pass # 421todo

    def draw(self, context, layout, node, text):
        value = None
        icon = 'NONE'
        warnMsg = None
        if not self.links:
            value = '0'
        else:
            otherSocket = self.links[0].from_socket
            flag = None
            if hasattr(otherSocket, 'flagColorCycle'): # 421todo better "is mixin with OBJEX_NodeSocketCombiner_CA_Output" check
                if self.__class__.cycle == CST.CYCLE_COLOR:
                    flag = otherSocket.flagColorCycle
                    value = stripPrefix(flag, 'G_CCMUX_')
                elif self.__class__.cycle == CST.CYCLE_ALPHA:
                    flag = otherSocket.flagAlphaCycle
                    value = stripPrefix(flag, 'G_ACMUX_')
                else:
                    value = '?'
                    icon = 'ERROR'
                    warnMsg = 'Unknown cycle'
            if flag:
                if flag not in (CST.SUPPORTED_FLAGS_COLOR if self.__class__.cycle == CST.CYCLE_COLOR else CST.SUPPORTED_FLAGS_ALPHA)[text]: # 421todo do not rely on text = A/B/C/D
                    icon = 'ERROR'
                    warnMsg = 'Unsupported for %s' % text
            else: # flag can be empty if non exists
                icon = 'ERROR'
                warnMsg = 'Unsupported'
        if warnMsg:
            col = layout.column()
            col.label(text='%s = %s' % (text, value), icon=icon)
            col.label(text=warnMsg, icon='ERROR')
        else:
            layout.label(text='%s = %s' % (text, value), icon=icon)

    def draw_color(self, context, node):
        text = self.name
        # 421fixme copypaste of the above
        value = None
        icon = 'NONE'
        warnMsg = None
        if not self.links:
            value = '0'
        else:
            otherSocket = self.links[0].from_socket
            flag = None
            if hasattr(otherSocket, 'flagColorCycle'): # 421todo better "is mixin with OBJEX_NodeSocketCombiner_CA_Output" check
                if self.__class__.cycle == CST.CYCLE_COLOR:
                    flag = otherSocket.flagColorCycle
                    value = stripPrefix(flag, 'G_CCMUX_')
                elif self.__class__.cycle == CST.CYCLE_ALPHA:
                    flag = otherSocket.flagAlphaCycle
                    value = stripPrefix(flag, 'G_ACMUX_')
                else:
                    value = '?'
                    icon = 'ERROR'
                    warnMsg = 'Unknown cycle'
            if flag:
                if flag not in (CST.SUPPORTED_FLAGS_COLOR if self.__class__.cycle == CST.CYCLE_COLOR else CST.SUPPORTED_FLAGS_ALPHA)[text]: # 421todo do not rely on text = A/B/C/D
                    icon = 'ERROR'
                    warnMsg = 'Unsupported for %s' % text
            else: # flag can be empty if non exists
                icon = 'ERROR'
                warnMsg = 'Unsupported'
        # (199/255,199/255,41/255,1) vanilla NodeSocketColor color
        return (0,1,0,1) if icon != 'ERROR' else (1,0,0,1)

class OBJEX_NodeSocketCombinerColorInput(bpy.types.NodeSocket, OBJEX_NodeSocketCombiner_CA_Input):
    default_value = bpy.props.FloatVectorProperty(name='default_value', default=(0.0, 0.0, 0.0), min=0, max=1, subtype='COLOR')
    cycle = CST.CYCLE_COLOR

class OBJEX_NodeSocketCombinerAlphaInput(bpy.types.NodeSocket, OBJEX_NodeSocketCombiner_CA_Input):
    default_value = bpy.props.FloatProperty(name='default_value', default=0, min=0, max=1)
    cycle = CST.CYCLE_ALPHA

# node groups creation

def create_node_group_color_cycle(group_name):
    cc = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    def addMixRGBnode(operation):
        n = cc.nodes.new('ShaderNodeMixRGB')
        n.blend_type = operation
        n.inputs[0].default_value = 1 # "Fac"
        return n

    cc_inputs_node = cc.nodes.new('NodeGroupInput')
    cc_inputs_node.location = (-450,0)
    cc.inputs.new('OBJEX_NodeSocketCombinerColorInput', 'A')
    cc.inputs.new('OBJEX_NodeSocketCombinerColorInput', 'B')
    cc.inputs.new('OBJEX_NodeSocketCombinerColorInput', 'C')
    cc.inputs.new('OBJEX_NodeSocketCombinerColorInput', 'D')

    A_minus_B = addMixRGBnode('SUBTRACT')
    A_minus_B.location = (-250,150)
    cc.links.new(cc_inputs_node.outputs['A'], A_minus_B.inputs[1])
    cc.links.new(cc_inputs_node.outputs['B'], A_minus_B.inputs[2])

    times_C = addMixRGBnode('MULTIPLY')
    times_C.location = (-50,100)
    cc.links.new(A_minus_B.outputs[0], times_C.inputs[1])
    cc.links.new(cc_inputs_node.outputs['C'], times_C.inputs[2])

    plus_D = addMixRGBnode('ADD')
    plus_D.location = (150,50)
    cc.links.new(times_C.outputs[0], plus_D.inputs[1])
    cc.links.new(cc_inputs_node.outputs['D'], plus_D.inputs[2])

    cc_outputs_node = cc.nodes.new('NodeGroupOutput')
    cc_outputs_node.location = (350,0)
    cc.outputs.new('OBJEX_NodeSocketCombinerColorOutput', 'Result')
    cc.links.new(plus_D.outputs[0], cc_outputs_node.inputs['Result'])
    cc.outputs['Result'].name = '(A-B)*C+D' # rename from 'Result' to formula

    return cc

def create_node_group_alpha_cycle(group_name):
    ac = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    def addMathNode(operation):
        n = ac.nodes.new('ShaderNodeMath')
        n.operation = operation
        return n

    ac_inputs_node = ac.nodes.new('NodeGroupInput')
    ac_inputs_node.location = (-450,0)
    ac.inputs.new('OBJEX_NodeSocketCombinerAlphaInput', 'A')
    ac.inputs.new('OBJEX_NodeSocketCombinerAlphaInput', 'B')
    ac.inputs.new('OBJEX_NodeSocketCombinerAlphaInput', 'C')
    ac.inputs.new('OBJEX_NodeSocketCombinerAlphaInput', 'D')

    A_minus_B = addMathNode('SUBTRACT')
    A_minus_B.location = (-250,150)
    ac.links.new(ac_inputs_node.outputs['A'], A_minus_B.inputs[0])
    ac.links.new(ac_inputs_node.outputs['B'], A_minus_B.inputs[1])

    times_C = addMathNode('MULTIPLY')
    times_C.location = (-50,100)
    ac.links.new(A_minus_B.outputs[0], times_C.inputs[0])
    ac.links.new(ac_inputs_node.outputs['C'], times_C.inputs[1])

    plus_D = addMathNode('ADD')
    plus_D.location = (150,50)
    ac.links.new(times_C.outputs[0], plus_D.inputs[0])
    ac.links.new(ac_inputs_node.outputs['D'], plus_D.inputs[1])

    ac_outputs_node = ac.nodes.new('NodeGroupOutput')
    ac_outputs_node.location = (350,0)
    ac.outputs.new('OBJEX_NodeSocketCombinerAlphaOutput', 'Result')
    ac.links.new(plus_D.outputs[0], ac_outputs_node.inputs['Result'])
    ac.outputs['Result'].name = '(A-B)*C+D' # rename from 'Result' to formula

    return ac

def create_node_group_color_static(group_name, colorValue, colorValueName):
    color0 = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    rgb = color0.nodes.new('ShaderNodeRGB')
    rgb.outputs[0].default_value = colorValue
    rgb.location = (0,100)
    
    outputs_node = color0.nodes.new('NodeGroupOutput')
    outputs_node.location = (150,50)
    color0.outputs.new('OBJEX_NodeSocketCombinerColorOutput', colorValueName)
    color0.links.new(rgb.outputs[0], outputs_node.inputs[colorValueName])

    return color0

def create_node_group_scale_uv(group_name):
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    inputs_node = tree.nodes.new('NodeGroupInput')
    inputs_node.location = (-400,0)
    tree.inputs.new('NodeSocketVector', 'UV')
    tree.inputs.new('NodeSocketInt', 'Scale Exponent')

    scalePower = tree.nodes.new('ShaderNodeMath')
    scalePower.operation = 'POWER'
    scalePower.location = (-200,0)
    scalePower.inputs[0].default_value = 2
    tree.links.new(inputs_node.outputs['Scale Exponent'], scalePower.inputs[1])

    separateXYZ = tree.nodes.new('ShaderNodeSeparateXYZ')
    separateXYZ.location = (-200,150)
    tree.links.new(inputs_node.outputs['UV'], separateXYZ.inputs[0])

    scaleU = tree.nodes.new('ShaderNodeMath')
    scaleU.operation = 'MULTIPLY'
    scaleU.location = (0,200)
    tree.links.new(separateXYZ.outputs[0], scaleU.inputs[0])
    tree.links.new(scalePower.outputs[0], scaleU.inputs[1])

    scaleV = tree.nodes.new('ShaderNodeMath')
    scaleV.operation = 'MULTIPLY'
    scaleV.location = (0,0)
    tree.links.new(separateXYZ.outputs[1], scaleV.inputs[0])
    tree.links.new(scalePower.outputs[0], scaleV.inputs[1])

    combineXYZ = tree.nodes.new('ShaderNodeCombineXYZ')
    combineXYZ.location = (200,100)
    tree.links.new(scaleU.outputs[0], combineXYZ.inputs[0])
    tree.links.new(scaleV.outputs[0], combineXYZ.inputs[1])

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (400,100)
    tree.outputs.new('NodeSocketVector', 'Scaled UV')
    tree.links.new(combineXYZ.outputs[0], outputs_node.inputs['Scaled UV'])

    return tree

def create_node_group_rgba(group_name):
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    inputs_node = tree.nodes.new('NodeGroupInput')
    inputs_node.location = (-100,50)
    tree.inputs.new('NodeSocketColor', 'Color')
    # doesn't seem like blender 2.79 provides a way to pick and use rgba directly
    alpha_input_socket = tree.inputs.new('NodeSocketFloat', 'Alpha')
    alpha_input_socket.min_value = 0
    alpha_input_socket.max_value = 1

    rgb_a = inputs_node

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (100,50)
    tree.outputs.new('OBJEX_NodeSocketCombinerColorOutput', 'RGB')
    tree.outputs.new('OBJEX_NodeSocketCombinerAlphaOutput', 'A')
    tree.links.new(rgb_a.outputs[0], outputs_node.inputs['RGB'])
    tree.links.new(rgb_a.outputs[1], outputs_node.inputs['A'])

    return tree

def update_node_groups():
    # dict mapping group names (keys in bpy.data.node_groups) to (latest_version, create_function) tuples
    # version is stored in 'objex_version' for each group and compared to latest_version
    # usage: increment associated latest_version when making changes in the create_function of some group
    # WARNING: the upgrading preserves links, which is the intent, but it means outputs/inputs order must not change
    #   (if the order must change, more complex upgrading code is required)
    groups = {
        'OBJEX_ColorCycle': (1, create_node_group_color_cycle),
        'OBJEX_AlphaCycle': (1, create_node_group_alpha_cycle),
        'OBJEX_Color0': (1, lambda group_name: create_node_group_color_static(group_name, (0,0,0,0), '0')),
        'OBJEX_Color1': (1, lambda group_name: create_node_group_color_static(group_name, (1,1,1,1), '1')),
        'OBJEX_ScaleUV': (1, create_node_group_scale_uv),
        'OBJEX_rgba': (1, create_node_group_rgba)
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
        material.use_nodes = True
        update_node_groups()
        node_tree = material.node_tree
        nodes = node_tree.nodes
        
        nodes.clear() # todo
        
        if 'Geometry' not in nodes:
            geometry = nodes.new('ShaderNodeGeometry')
            geometry.name = 'Geometry'
            geometry.location = (-400, 100)
        else:
            geometry = nodes['Geometry']
        
        if 'OBJEX_MultiTexScale0' not in nodes:
            multiTexScale0 = nodes.new('ShaderNodeGroup')
            multiTexScale0.node_tree = bpy.data.node_groups['OBJEX_ScaleUV']
            multiTexScale0.name = 'OBJEX_MultiTexScale0'
            multiTexScale0.label = 'Multitexture Scale 0'
            multiTexScale0.location = (-150, 200)
            multiTexScale0.width += 50
        else:
            multiTexScale0 = nodes['OBJEX_MultiTexScale0']
        if 'OBJEX_MultiTexScale1' not in nodes:
            multiTexScale1 = nodes.new('ShaderNodeGroup')
            multiTexScale1.node_tree = bpy.data.node_groups['OBJEX_ScaleUV']
            multiTexScale1.name = 'OBJEX_MultiTexScale1'
            multiTexScale1.label = 'Multitexture Scale 1'
            multiTexScale1.location = (-150, -100)
            multiTexScale1.width += 50
        else:
            multiTexScale1 = nodes['OBJEX_MultiTexScale1']
        
        if 'OBJEX_Texel0Texture' not in nodes:
            texel0texture = nodes.new('ShaderNodeTexture')
            texel0texture.name = 'OBJEX_Texel0Texture'
            texel0texture.label = 'Texel 0 Texture'
            texel0texture.location = (100, 300)
        else:
            texel0texture = nodes['OBJEX_Texel0Texture']
        if 'OBJEX_Texel1Texture' not in nodes:
            texel1texture = nodes.new('ShaderNodeTexture')
            texel1texture.name = 'OBJEX_Texel1Texture'
            texel1texture.label = 'Texel 1 Texture'
            texel1texture.location = (100, 0)
        else:
            texel1texture = nodes['OBJEX_Texel1Texture']
        
        if 'OBJEX_PrimColor' not in nodes:
            primColor = nodes.new('ShaderNodeGroup')
            primColor.node_tree = bpy.data.node_groups['OBJEX_rgba']
            primColor.name = 'OBJEX_PrimColor'
            primColor.label = 'Prim Color'
            primColor.location = (300, 300)
            primColor.outputs[0].flagColorCycle = 'G_CCMUX_PRIMITIVE'
            primColor.outputs[1].flagColorCycle = 'G_CCMUX_PRIMITIVE_ALPHA'
            primColor.outputs[0].flagAlphaCycle = ''
            primColor.outputs[1].flagAlphaCycle = 'G_ACMUX_PRIMITIVE'
        else:
            primColor = nodes['OBJEX_PrimColor']
        if 'OBJEX_EnvColor' not in nodes:
            envColor = nodes.new('ShaderNodeGroup')
            envColor.node_tree = bpy.data.node_groups['OBJEX_rgba']
            envColor.name = 'OBJEX_EnvColor'
            envColor.label = 'Env Color'
            envColor.location = (300, 100)
            envColor.outputs[0].flagColorCycle = 'G_CCMUX_ENVIRONMENT'
            envColor.outputs[1].flagColorCycle = 'G_CCMUX_ENV_ALPHA'
            envColor.outputs[0].flagAlphaCycle = ''
            envColor.outputs[1].flagAlphaCycle = 'G_ACMUX_ENVIRONMENT'
        else:
            envColor = nodes['OBJEX_EnvColor']
        
        if 'OBJEX_Texel0' not in nodes:
            texel0 = nodes.new('ShaderNodeGroup')
            texel0.node_tree = bpy.data.node_groups['OBJEX_rgba']
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
            texel1.node_tree = bpy.data.node_groups['OBJEX_rgba']
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
            shade.node_tree = bpy.data.node_groups['OBJEX_rgba']
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
            color0.location = (300, -100)
            color0.outputs[0].flagColorCycle = 'G_CCMUX_0'
            color0.outputs[0].flagAlphaCycle = 'G_ACMUX_0'
        else:
            color0 = nodes['OBJEX_Color0']
        if 'OBJEX_Color1' not in nodes:
            color1 = nodes.new('ShaderNodeGroup')
            color1.node_tree = bpy.data.node_groups['OBJEX_Color1']
            color1.name = 'OBJEX_Color1'
            color1.label = 'Color 1'
            color1.location = (300, -200)
            color1.outputs[0].flagColorCycle = 'G_CCMUX_1'
            color1.outputs[0].flagAlphaCycle = 'G_ACMUX_1'
        else:
            color1 = nodes['OBJEX_Color1']
        
        if 'OBJEX_ColorCycle0' not in nodes:
            cc0 = nodes.new('ShaderNodeGroup')
            cc0.node_tree = bpy.data.node_groups['OBJEX_ColorCycle']
            cc0.name = 'OBJEX_ColorCycle0' # internal name
            cc0.label = 'Color Cycle 0' # displayed name
            cc0.location = (500, 200)
            cc0.width = 200
            cc0.outputs[0].flagColorCycle = 'G_CCMUX_COMBINED'
        else:
            cc0 = nodes['OBJEX_ColorCycle0']
        if 'OBJEX_ColorCycle1' not in nodes:
            cc1 = nodes.new('ShaderNodeGroup')
            cc1.node_tree = bpy.data.node_groups['OBJEX_ColorCycle']
            cc1.name = 'OBJEX_ColorCycle1'
            cc1.label = 'Color Cycle 1'
            cc1.location = (750, 200)
            cc1.width = 200
        else:
            cc1 = nodes['OBJEX_ColorCycle1']
        
        if 'OBJEX_AlphaCycle0' not in nodes:
            ac0 = nodes.new('ShaderNodeGroup')
            ac0.node_tree = bpy.data.node_groups['OBJEX_AlphaCycle']
            ac0.name = 'OBJEX_AlphaCycle0'
            ac0.label = 'Alpha Cycle 0'
            ac0.location = (500, 0)
            ac0.width = 200
            ac0.outputs[0].flagColorCycle = 'G_CCMUX_COMBINED_ALPHA'
            ac0.outputs[0].flagAlphaCycle = 'G_ACMUX_COMBINED'
        else:
            ac0 = nodes['OBJEX_AlphaCycle0']
        if 'OBJEX_AlphaCycle1' not in nodes:
            ac1 = nodes.new('ShaderNodeGroup')
            ac1.node_tree = bpy.data.node_groups['OBJEX_AlphaCycle']
            ac1.name = 'OBJEX_AlphaCycle1'
            ac1.label = 'Alpha Cycle 1'
            ac1.location = (750, 0)
            ac1.width = 200
        else:
            ac1 = nodes['OBJEX_AlphaCycle1']
        
        if 'Output' not in nodes:
            output = nodes.new('ShaderNodeOutput')
            output.name = 'Output'
            output.location = (1000, 100)
        else:
            output = nodes['Output']
        
        # texel0
        node_tree.links.new(geometry.outputs['UV'], multiTexScale0.inputs['UV'])
        node_tree.links.new(multiTexScale0.outputs[0], texel0texture.inputs[0])
        node_tree.links.new(texel0texture.outputs[1], texel0.inputs[0])
        node_tree.links.new(texel0texture.outputs[0], texel0.inputs[1])
        # texel1
        node_tree.links.new(geometry.outputs['UV'], multiTexScale1.inputs['UV'])
        node_tree.links.new(multiTexScale1.outputs[0], texel1texture.inputs[0])
        node_tree.links.new(texel1texture.outputs[1], texel1.inputs[0])
        node_tree.links.new(texel1texture.outputs[0], texel1.inputs[1])
        # shade
        node_tree.links.new(geometry.outputs['Vertex Color'], shade.inputs[0])
        node_tree.links.new(geometry.outputs['Vertex Alpha'], shade.inputs[1])
        node_tree.links.new(cc1.outputs[0], output.inputs[0])
        
        return {'FINISHED'}

# properties and non-node UI

def material_updated_my_int(self, context):
    print('my_int -> %d' % context.material.objex_bonus.my_int)

class ObjexMaterialProperties(bpy.types.PropertyGroup):
    my_int = bpy.props.IntProperty(
            name='int32',
            description='integeeeerr',
            update=material_updated_my_int
        )
    my_color = bpy.props.FloatVectorProperty(  
            name='object_color',
            subtype='COLOR',
            default=(1.0, 1.0, 1.0),
            min=0.0, max=1.0,
            description='color picker'
        )

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
        self.layout.label(text='Hello World')
        material = context.material
        data = material.objex_bonus
        # 421todo maybe not show the init button if init has already been done
        self.layout.operator('OBJEX_OT_material_init')
        self.layout.prop(data, 'my_int')
        self.layout.prop(data, 'my_color')
        self.layout.label(text='HELLLLLLLOOOOO')

classes = (
    ObjexArmatureExportActionsItem,
    ObjexArmatureProperties,
    OBJEX_UL_actions,
    OBJEX_PT_armature,

    OBJEX_NodeSocketCombinerColorOutputInterface,
    OBJEX_NodeSocketCombinerColorOutput,
    OBJEX_NodeSocketCombinerAlphaOutputInterface,
    OBJEX_NodeSocketCombinerAlphaOutput,
    OBJEX_NodeSocketCombinerColorInputInterface,
    OBJEX_NodeSocketCombinerColorInput,
    OBJEX_NodeSocketCombinerAlphaInputInterface,
    OBJEX_NodeSocketCombinerAlphaInput,
    OBJEX_OT_material_init,
    ObjexMaterialProperties,
    OBJEX_PT_material
)

def register_interface():
    for clazz in classes:
        try:
            bpy.utils.register_class(clazz)
        except:
            print(clazz)
            traceback.print_exc()
            raise
    bpy.types.Armature.objex_bonus = bpy.props.PointerProperty(type=ObjexArmatureProperties)
    bpy.types.Material.objex_bonus = bpy.props.PointerProperty(type=ObjexMaterialProperties)

def unregister_interface():
    del bpy.types.Armature.objex_bonus
    del bpy.types.Material.objex_bonus
    for clazz in reversed(classes):
        try:
            bpy.utils.unregister_class(clazz)
        except:
            traceback.print_exc()
