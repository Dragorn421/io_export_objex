import bpy
import mathutils
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
        propOffset(box, data, 'segment', 'Segment')
        box.prop(data, 'segment_local')

#
# material
#

class CST:
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
        if warnMsg:
            col = layout.column()
            col.label(text='%s = %s' % (name, value), icon='ERROR')
            col.label(text=warnMsg, icon='ERROR')
        else:
            layout.label(text='%s = %s' % (name, value))
        # 421todo add a dropdown list with available flags

    def draw_color(self, context, node):
        if node.bl_idname == 'NodeGroupInput':
            return CST.COLOR_OK
        flag, warnMsg = self.linkToFlag()
        return CST.COLOR_BAD if warnMsg else CST.COLOR_OK

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
    # blender 2.79 fails to transfer data somewhere when linking int socket to float socket of math node...
    #tree.inputs.new('NodeSocketInt', 'U Scale Exponent')
    #tree.inputs.new('NodeSocketInt', 'V Scale Exponent')
    # instead, round float inputs
    tree.inputs.new('NodeSocketFloat', 'U Scale Exponent')
    tree.inputs.new('NodeSocketFloat', 'V Scale Exponent')
    # 421todo instead, use U/V scale inputs, and do final_scale = 2^(round(log_2(input_scale))) (as an option?)
    # 421todo try using a custom socket as U/V scale inputs, auto-round on update
    # 421todo same for Wrap U/V booleans, create OBJEX_NodeSocket_Bool and make it update the hidden float socket
    tree.inputs.new('NodeSocketFloat', 'Wrap U (0/1)').default_value = 1
    tree.inputs.new('NodeSocketFloat', 'Wrap V (0/1)').default_value = 1
    tree.inputs.new('NodeSocketFloat', 'Mirror U (0/1)').default_value = 0
    tree.inputs.new('NodeSocketFloat', 'Mirror V (0/1)').default_value = 0

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
        uScale = addMathNode('ROUND', (-400,400+y), inputs_node.outputs['%s Scale Exponent' % uv])
        uScalePower = addMathNode('POWER', (-200,400+y), 2, uScale.outputs[0])
        scaleU = addMathNode('MULTIPLY', (0,400+y), separateXYZ.outputs[i], uScalePower.outputs[0])
        # mirror
        notMirroredBool = addMathNode('SUBTRACT', (200,600+y), 1, inputs_node.outputs['Mirror %s (0/1)' % uv])
        identity = addMathNode('MULTIPLY', (400,400+y), scaleU.outputs[0], notMirroredBool.outputs[0])
        reversed = addMathNode('MULTIPLY', (200,200+y), scaleU.outputs[0], -1)
        add1 = addMathNode('ADD', (200,0+y), scaleU.outputs[0], 1)
        mod4_1 = addMathNode('MODULO', (400,0+y), add1.outputs[0], 4)
        add4 = addMathNode('ADD', (600,0+y), mod4_1.outputs[0], 4)
        mod4_2 = addMathNode('MODULO', (800,0+y), add4.outputs[0], 4)
        notMirroredPartBool = addMathNode('LESS_THAN', (1000,0+y), mod4_2.outputs[0], 2)
        mirroredPartNo = addMathNode('MULTIPLY', (1200,400+y), scaleU.outputs[0], notMirroredPartBool.outputs[0])
        mirroredPartBool = addMathNode('SUBTRACT', (1200,0+y), 1, notMirroredPartBool.outputs[0])
        mirroredPartYes = addMathNode('MULTIPLY', (1400,200+y), reversed.outputs[0], mirroredPartBool.outputs[0])
        withMirror = addMathNode('ADD', (1600,300+y), mirroredPartYes.outputs[0], mirroredPartNo.outputs[0])
        mirrored = addMathNode('MULTIPLY', (1800,400+y), withMirror.outputs[0], inputs_node.outputs['Mirror %s (0/1)' % uv])
        mirroredFinal = addMathNode('ADD', (2000,300+y), identity.outputs[0], mirrored.outputs[0])
        # wrapped (identity)
        wrappedU = addMathNode('MULTIPLY', (2200,400+y), mirroredFinal.outputs[0], inputs_node.outputs['Wrap %s (0/1)' % uv])
        # clamped (in [-1;1])
        upperClampedU = addMathNode('MINIMUM', (2300,200+y), mirroredFinal.outputs[0], 1)
        upperLowerClampedU = addMathNode('MAXIMUM', (2500,200+y), upperClampedU.outputs[0], -1) # fixme -1 looks correct? confirm
        notWrapU = addMathNode('SUBTRACT', (2400,0+y), 1, inputs_node.outputs['Wrap %s (0/1)' % uv])
        clampedU = addMathNode('MULTIPLY', (2700,200+y), upperLowerClampedU.outputs[0], notWrapU.outputs[0])
        #
        finalU = addMathNode('ADD', (2900,300+y), wrappedU.outputs[0], clampedU.outputs[0])
        final[uv] = finalU
    finalU = final['U']
    finalV = final['V']

    # v outdated
    """
    vScale = tree.nodes.new('ShaderNodeMath')
    vScale.operation = 'ROUND'
    vScale.location = (-400,-100)
    tree.links.new(inputs_node.outputs['V Scale Exponent'], vScale.inputs[0])

    vScalePower = tree.nodes.new('ShaderNodeMath')
    vScalePower.operation = 'POWER'
    vScalePower.location = (-200,-100)
    vScalePower.inputs[0].default_value = 2
    tree.links.new(vScale.outputs[0], vScalePower.inputs[1])

    scaleV = tree.nodes.new('ShaderNodeMath')
    scaleV.operation = 'MULTIPLY'
    scaleV.location = (0,0)
    tree.links.new(separateXYZ.outputs[1], scaleV.inputs[0])
    tree.links.new(vScalePower.outputs[0], scaleV.inputs[1])
    """

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
        
        if 'Geometry' not in nodes:
            geometry = nodes.new('ShaderNodeGeometry')
            geometry.name = 'Geometry'
            geometry.location = (-400, -100)
        else:
            geometry = nodes['Geometry']
        
        if 'OBJEX_MultiTexScale0' not in nodes:
            multiTexScale0 = nodes.new('ShaderNodeGroup')
            multiTexScale0.node_tree = bpy.data.node_groups['OBJEX_UV_pipe']
            multiTexScale0.name = 'OBJEX_MultiTexScale0' # internal name
            multiTexScale0.label = 'Multitexture Scale 0' # displayed name
            multiTexScale0.location = (-150, -50)
            multiTexScale0.width += 50
        else:
            multiTexScale0 = nodes['OBJEX_MultiTexScale0']
        if 'OBJEX_MultiTexScale1' not in nodes:
            multiTexScale1 = nodes.new('ShaderNodeGroup')
            multiTexScale1.node_tree = bpy.data.node_groups['OBJEX_UV_pipe']
            multiTexScale1.name = 'OBJEX_MultiTexScale1'
            multiTexScale1.label = 'Multitexture Scale 1'
            multiTexScale1.location = (-150, -350)
            multiTexScale1.width += 50
        else:
            multiTexScale1 = nodes['OBJEX_MultiTexScale1']

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
            cc0.location = (500, 200)
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
            cc1.location = (750, 200)
            cc1.width = 200
            cc1['cycle'] = CST.CYCLE_COLOR
        else:
            cc1 = nodes['OBJEX_ColorCycle1']
        
        if 'OBJEX_AlphaCycle0' not in nodes:
            ac0 = nodes.new('ShaderNodeGroup')
            ac0.node_tree = bpy.data.node_groups['OBJEX_Cycle']
            ac0.name = 'OBJEX_AlphaCycle0'
            ac0.label = 'Alpha Cycle 0'
            ac0.location = (500, 0)
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
            ac1.location = (750, 0)
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
        node_tree.links.new(geometry.outputs['UV'], multiTexScale0.inputs['UV'])
        node_tree.links.new(multiTexScale0.outputs[0], texel0texture.inputs[0])
        node_tree.links.new(texel0texture.outputs[1], texel0.inputs[0])
        node_tree.links.new(texel0texture.outputs[0], texel0.inputs[1])
        # texel1
        node_tree.links.new(geometry.outputs['UV'], multiTexScale1.inputs['UV'])
        node_tree.links.new(multiTexScale1.outputs[0], texel1texture.inputs[0])
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

def material_updated_my_int(self, context):
    print('my_int -> %d' % context.material.objex_bonus.my_int)

class ObjexMaterialProperties(bpy.types.PropertyGroup):
    is_objex_material = bpy.props.BoolProperty(default=False)

    backface_culling = bpy.props.BoolProperty(
            name='Cull backfaces',
            description='Culls the back face of geometry',
            default=True
        )
    rendermode_zmode = bpy.props.EnumProperty(
            items=[
                ('OPA','Opaque','Opaque surfaces (OPA)',1),
                ('INTER','Interpenetrating','Interpenetrating surfaces',2),
                ('XLU','Translucent','Translucent surfaces (XLU)',3),
                ('DECA','Decal','Decal surfaces (eg paths)',4),
                ('AUTO','Auto','Default to Translucent (XLU) if material uses transparency, or Opaque (OPA) otherwise',5),
            ],
            name='zmode',
            description='Not well understood, has to do with rendering order',
            default='AUTO'
        )
    rendermode_forceblending = bpy.props.EnumProperty(
            items=[
                ('YES','Always','Force blending',1),
                ('NO','Never','Do not force blending',2),
                ('AUTO','Auto','Force blending if the material uses transparency',3),
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
                ('AUTO','Auto','Use "Pass" if material uses transparency and "Fog RGB, shade A" otherwise',6),
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

    use_texgen = bpy.props.BoolProperty(
            name='Texgen',
            description='Generates texture coordinates at run time depending on the view',
            default=False
        )

    scaleS = bpy.props.FloatProperty(
            name='"U" scale',
            description='Not fully understood, "as if" it scaled U in UVs?',
            min=0, max=1, step=0.01, precision=6,
            default=1
        )
    scaleT = bpy.props.FloatProperty(
            name='"V" scale',
            description='Not fully understood, "as if" it scaled V in UVs?',
            min=0, max=1, step=0.01, precision=6,
            default=1
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
        # 421todo maybe not show the init button if init has already been done
        self.layout.operator('OBJEX_OT_material_init')
        self.layout.prop(data, 'backface_culling')
        box = self.layout.box()
        box.label(text='Render mode')
        box.prop(data, 'rendermode_zmode')
        box.prop(data, 'rendermode_forceblending')
        box.prop(data, 'rendermode_blending_cycle0')
        if data.rendermode_blending_cycle0 == 'CUSTOM':
            for v in ('P','A','M','B'):
                box.prop(data, 'rendermode_blending_cycle0_custom_%s' % v)
        box.prop(data, 'rendermode_blending_cycle1')
        if data.rendermode_blending_cycle1 == 'CUSTOM':
            for v in ('P','A','M','B'):
                box.prop(data, 'rendermode_blending_cycle1_custom_%s' % v)
        self.layout.prop(data, 'use_texgen')
        self.layout.prop(data, 'scaleS')
        self.layout.prop(data, 'scaleT')

# textures

class ObjexTextureProperties(bpy.types.PropertyGroup):
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
    pointer = bpy.props.StringProperty(
            name='Pointer',
            description='The address that should be used when referencing this texture',
            default=''
        )
    priority = bpy.props.FloatProperty(
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
    texture_bank = bpy.props.StringProperty(
            name='Bank',
            description='Image data to write instead of this texture, useful for dynamic textures (eyes, windows)',
            subtype='FILE_PATH',
            default=''
        )

class OBJEX_PT_texture(bpy.types.Panel):
    bl_label = 'Objex'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'texture'

    @classmethod
    def poll(self, context):
        texture = context.texture
        return texture is not None

    def draw(self, context):
        texture = context.texture
        data = texture.objex_bonus
        self.layout.prop(data, 'format')
        if data.format[:2] == 'CI':
            self.layout.prop(data, 'palette')
        propOffset(self.layout, data, 'pointer', 'Pointer')
        self.layout.prop(data, 'priority')
        self.layout.prop(data, 'force_write')
        self.layout.prop(data, 'texture_bank')


classes = (
    ObjexArmatureExportActionsItem,
    ObjexArmatureProperties,
    OBJEX_UL_actions,
    OBJEX_PT_armature,

    OBJEX_NodeSocketInterface_CombinerOutput,
    OBJEX_NodeSocketInterface_CombinerInput,
    OBJEX_NodeSocketInterface_RGBA_Color,
    OBJEX_NodeSocket_CombinerOutput,
    OBJEX_NodeSocket_CombinerInput,
    OBJEX_NodeSocket_RGBA_Color,

    OBJEX_OT_material_init,
    ObjexMaterialProperties,
    OBJEX_PT_material,

    ObjexTextureProperties,
    OBJEX_PT_texture,
)

def register_interface():
    for clazz in classes:
        try:
            bpy.utils.register_class(clazz)
        except:
            print('Error registering', clazz)
            traceback.print_exc()
            raise
    bpy.types.Armature.objex_bonus = bpy.props.PointerProperty(type=ObjexArmatureProperties)
    bpy.types.Material.objex_bonus = bpy.props.PointerProperty(type=ObjexMaterialProperties)
    bpy.types.Texture.objex_bonus = bpy.props.PointerProperty(type=ObjexTextureProperties)

def unregister_interface():
    del bpy.types.Armature.objex_bonus
    del bpy.types.Material.objex_bonus
    for clazz in reversed(classes):
        try:
            bpy.utils.unregister_class(clazz)
        except:
            print('Error unregistering', clazz)
            traceback.print_exc()
