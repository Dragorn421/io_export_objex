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

# material

def create_node_group_color_cycle(group_name):
    cc = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    def addMixRGBnode(operation):
        n = cc.nodes.new('ShaderNodeMixRGB')
        n.blend_type = operation
        n.inputs[0].default_value = 1 # "Fac"
        return n

    cc_inputs_node = cc.nodes.new('NodeGroupInput')
    cc_inputs_node.location = (-450,0)
    cc.inputs.new('NodeSocketColor', 'A')
    cc.inputs.new('NodeSocketColor', 'B')
    cc.inputs.new('NodeSocketColor', 'C')
    cc.inputs.new('NodeSocketColor', 'D')

    # todo extend NodeSocketColor, redefine draw, show /!\ icon when a link isn't possible with n64 combine
    """
    allowed links (for now ignore the ? ones)
    
    A, B, C, D:
        G_CCMUX_COMBINED -> not for cycle 0 (loop)
        texel0
        texel1
        primColor
        G_CCMUX_SHADE todo vertex colors
        envColor
        0
    A only:
        1
        G_CCMUX_NOISE ?
    B only:
        G_CCMUX_CENTER ?
        G_CCMUX_K4 ?
    C only:
        G_CCMUX_SCALE ?
        G_CCMUX_COMBINED_ALPHA -> not for cycle 0 (loop)
        G_CCMUX_TEXEL0_ALPHA todo
        G_CCMUX_TEXEL1_ALPHA todo
        G_CCMUX_PRIMITIVE_ALPHA todo
        G_CCMUX_SHADE_ALPHA todo vertex colors
        G_CCMUX_ENV_ALPHA todo
        G_CCMUX_LOD_FRACTION ?
        G_CCMUX_PRIM_LOD_FRAC ?
        G_CCMUX_K5 ?
    D only:
        1
    """

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
    cc.outputs.new('NodeSocketColor', 'Result')
    cc.links.new(plus_D.outputs[0], cc_outputs_node.inputs['Result'])

    return cc

def create_node_group_color_static(group_name, colorValue, colorValueName):
    color0 = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    rgb = color0.nodes.new('ShaderNodeRGB')
    rgb.outputs[0].default_value = colorValue
    rgb.location = (0,100)
    
    outputs_node = color0.nodes.new('NodeGroupOutput')
    outputs_node.location = (150,50)
    color0.outputs.new('NodeSocketColor', colorValueName)
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

def update_node_groups():
    # dict mapping group names (keys in bpy.data.node_groups) to (latest_version, create_function) tuples
    # version is stored in 'objex_version' for each group and compared to latest_version
    # usage: increment associated latest_version when making changes in the create_function of some group
    # WARNING: the upgrading preserves links, which is the intent, but it means outputs/inputs order must not change
    #   (if the order must change, more complex upgrading code is required)
    groups = {
        'OBJEX_ColorCycle': (1, create_node_group_color_cycle),
        'OBJEX_Color0': (1, lambda group_name: create_node_group_color_static(group_name, (0,0,0,0), '0')),
        'OBJEX_Color1': (1, lambda group_name: create_node_group_color_static(group_name, (1,1,1,1), '1')),
        'OBJEX_ScaleUV': (1, create_node_group_scale_uv),
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
        
        if 'OBJEX_Texel0' not in nodes:
            texel0 = nodes.new('ShaderNodeTexture')
            texel0.name = 'OBJEX_Texel0'
            texel0.label = 'Texel 0'
            texel0.location = (100, 300)
        else:
            texel0 = nodes['OBJEX_Texel0']
        if 'OBJEX_Texel1' not in nodes:
            texel1 = nodes.new('ShaderNodeTexture')
            texel1.name = 'OBJEX_Texel1'
            texel1.label = 'Texel 1'
            texel1.location = (100, 0)
        else:
            texel1 = nodes['OBJEX_Texel1']
        
        if 'OBJEX_PrimColor' not in nodes:
            primColor = nodes.new('ShaderNodeRGB')
            primColor.name = 'OBJEX_PrimColor'
            primColor.label = 'Prim Color'
            primColor.location = (300, 300)
        else:
            primColor = nodes['OBJEX_PrimColor']
        if 'OBJEX_EnvColor' not in nodes:
            envColor = nodes.new('ShaderNodeRGB')
            envColor.name = 'OBJEX_EnvColor'
            envColor.label = 'Env Color'
            envColor.location = (300, 100)
        else:
            envColor = nodes['OBJEX_EnvColor']
        
        if 'OBJEX_Color0' not in nodes:
            color0 = nodes.new('ShaderNodeGroup')
            color0.node_tree = bpy.data.node_groups['OBJEX_Color0']
            color0.name = 'OBJEX_Color0'
            color0.label = 'Color 0'
            color0.location = (300, -100)
        else:
            color0 = nodes['OBJEX_Color0']
        if 'OBJEX_Color1' not in nodes:
            color1 = nodes.new('ShaderNodeGroup')
            color1.node_tree = bpy.data.node_groups['OBJEX_Color1']
            color1.name = 'OBJEX_Color1'
            color1.label = 'Color 1'
            color1.location = (300, -200)
        else:
            color1 = nodes['OBJEX_Color1']
        
        if 'OBJEX_ColorCycle0' not in nodes:
            cc0 = nodes.new('ShaderNodeGroup')
            cc0.node_tree = bpy.data.node_groups['OBJEX_ColorCycle']
            cc0.name = 'OBJEX_ColorCycle0' # internal name
            cc0.label = 'Color Cycle 0' # displayed name
            cc0.location = (500, 100)
        else:
            cc0 = nodes['OBJEX_ColorCycle0']
        if 'OBJEX_ColorCycle1' not in nodes:
            cc1 = nodes.new('ShaderNodeGroup')
            cc1.node_tree = bpy.data.node_groups['OBJEX_ColorCycle']
            cc1.name = 'OBJEX_ColorCycle1'
            cc1.label = 'Color Cycle 1'
            cc1.location = (700, 100)
        else:
            cc1 = nodes['OBJEX_ColorCycle1']
        
        if 'Output' not in nodes:
            output = nodes.new('ShaderNodeOutput')
            output.name = 'Output'
            output.location = (900, 100)
        else:
            output = nodes['Output']
        
        node_tree.links.new(geometry.outputs['UV'], multiTexScale0.inputs['UV'])
        node_tree.links.new(multiTexScale0.outputs[0], texel0.inputs[0])
        node_tree.links.new(geometry.outputs['UV'], multiTexScale1.inputs['UV'])
        node_tree.links.new(multiTexScale1.outputs[0], texel1.inputs[0])
        node_tree.links.new(cc1.outputs[0], output.inputs[0])
        
        return {'FINISHED'}

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
    OBJEX_OT_material_init,
    ObjexMaterialProperties,
    OBJEX_PT_material
)

def register_interface():
    for clazz in classes:
        try:
            bpy.utils.register_class(clazz)
        except:
            traceback.print_exc()
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
