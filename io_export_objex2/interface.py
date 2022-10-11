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
import bpy.utils.previews
import mathutils
import re
from math import pi

from . import const_data as CST
from . import data_updater
from . import node_setup_helpers
from .logging_util import getLogger
from . import util
from . import rigging_helpers

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
More up-to-date-ish but somewhat vague and summarized version changes https://wiki.blender.org/wiki/Reference/Release_Notes
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

def menu_draw_mesh(self:bpy.types.Panel, context:bpy.types.Context):
    objex_scene = context.scene.objex_bonus
    object = context.object
    data = object.data.objex_bonus # ObjexMeshProperties

    box = self.layout.box()
    box.row().prop(data, 'type', expand=True)

    box = self.layout.box()
    row = box.row()
    row.alignment = 'CENTER'
    row.label(text='Mesh')
    row = box.row()
    # row.use_property_split = True
    row.use_property_decorate = False # Do not display keyframe setting
    row.label(text='Origin')
    row.prop(data, 'write_origin', expand=True)

    row = box.row()
    # row.use_property_split = True
    row.use_property_decorate = False # Do not display keyframe setting
    row.label(text='Billboard')
    row.prop(data, 'attrib_billboard', expand=True)
    box.prop(data, 'priority')

    sub_box = box.box()
    row = sub_box.row()
    row.prop(data, 'attrib_POSMTX')
    row.prop(data, 'attrib_PROXY')
    row.label(text='') # Only for aligning with the next row items
    armature = object.find_armature()
    if armature:
        row = sub_box.row()
        row.prop(data, 'attrib_NOSPLIT')

        invert = False
        col = row.column()
        if data.attrib_NOSPLIT:
            col.enabled = False
            # Make it look like the disabled button is enabled
            if data.attrib_NOSKEL == False:
                invert=True
        
        col.prop(data, 'attrib_NOSKEL', invert_checkbox=invert)
        row.prop(data, 'attrib_LIMBMTX')

        row = box.row()
        row.operator('objex.mesh_find_multiassigned_vertices', text='Find multiassigned vertices')
        row.operator('objex.mesh_find_unassigned_vertices', text='Find unassigned vertices')
        box.operator('objex.mesh_list_vertex_groups', text='List groups of selected vertex')
    
        return
        # folding/unfolding
        if rigging_helpers.AutofoldOperator.poll(context):
            scene = context.scene
            objex_scene = context.scene.objex_bonus

            box = self.layout.box()
            box.use_property_split = False
            row = box.row()
            row.alignment = 'CENTER'
            row.label(text='Folding')
            armature = rigging_helpers.AutofoldOperator.get_armature(self, context)
            # 421todo make it easier/more obvious to use...
            # 421todo export/import saved poses
            row = box.row()
            row.operator('objex.autofold_save_pose', text='Save pose')
            row.operator('objex.autofold_restore_pose', text='Restore pose')
            row = box.row()
            row.operator('objex.autofold_fold_unfold', text='Fold').action = 'FOLD'
            row.operator('objex.autofold_fold_unfold', text='Unfold').action = 'UNFOLD'
            row.operator('objex.autofold_fold_unfold', text='Switch').action = 'SWITCH'
            # 421todo better saved poses management (delete)
            box.label(text='Default saved pose to use for folding:')
            # 'OBJEX_SavedPose' does not refer to any addon-defined class. see documentation of template_list
            box.template_list('UI_UL_list', 'OBJEX_SavedPose', scene.objex_bonus, 'saved_poses', armature.data.objex_bonus, 'fold_unfold_saved_pose_index', rows=2)
            box.operator('objex.autofold_delete_pose', text='Delete pose')

class OBJEX_PT_mesh_object_view3d(bpy.types.Panel):
    bl_category = "Objex"
    bl_label = 'Mesh'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = '.objectmode'
    draw = menu_draw_mesh

    @classmethod
    def poll(self, context):
        object = context.object
        return object.type == 'MESH'

class OBJEX_PT_mesh_object_prop(bpy.types.Panel):
    bl_label = 'Objex'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    draw = menu_draw_mesh

    @classmethod
    def poll(self, context):
        object = context.object
        return object.type == 'MESH'

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
        if blender_version_compatibility.no_ID_PointerProperty:
            layout.prop_search(item, 'action', bpy.data, 'actions', text='')
        else:
            layout.prop(item, 'action', text='')

def menu_draw_armature(self:bpy.types.Panel, context:bpy.types.Context, armature:bpy.types.Armature):
    object = context.object
    data = armature.objex_bonus
    # actions

    box = self.layout.box()
    box.use_property_split = False
    row = box.row()
    row.alignment = 'CENTER'
    row.label(text='SkelAnime')

    box.row().prop(data, 'type', expand=True)
    row2 = box.row()
    row2.prop(data, 'export_all_actions')
    row2.prop(data, 'start_frame_clamp')
    if data.start_frame_clamp == True:
        box.prop(data, 'start_frame_clamp_value')

    if not data.export_all_actions:
        box.label(text='Actions to export:')
        box.template_list('OBJEX_UL_actions', '', data, 'export_actions', data, 'export_actions_active')
        
    if data.pbody:
        sub_box = box.box()
        sub_box.prop(data, 'pbody')
        def prop_pbody_parent_object(layout, icon='NONE'):
            if blender_version_compatibility.no_ID_PointerProperty:
                layout.prop_search(data, 'pbody_parent_object', bpy.data, 'objects', icon=icon)
            else:
                layout.prop(data, 'pbody_parent_object', icon=icon)
        if data.pbody_parent_object:
            if blender_version_compatibility.no_ID_PointerProperty:
                pbody_parent_object = bpy.data.objects[data.pbody_parent_object]
            else:
                pbody_parent_object = data.pbody_parent_object
            if hasattr(pbody_parent_object, 'type') and pbody_parent_object.type == 'ARMATURE':
                prop_pbody_parent_object(sub_box)
                valid_bone = data.pbody_parent_bone in pbody_parent_object.data.bones
                sub_box.prop_search(data, 'pbody_parent_bone', pbody_parent_object.data, 'bones', icon=('NONE' if valid_bone else 'ERROR'))
                if not valid_bone:
                    sub_box.label(text='A bone must be picked')
            else:
                prop_pbody_parent_object(sub_box, icon='ERROR')
                sub_box.label(text='If set, parent must be an armature')
        else:
            prop_pbody_parent_object(sub_box)
    else:
        box.box().prop(data, 'pbody')
    # segment
    sub_box = box.box()
    propOffset(sub_box, data, 'segment', 'Segment')
    sub_box.prop(data, 'segment_local')

class OBJEX_PT_armature_prop(bpy.types.Panel):
    bl_label = 'Objex'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    
    @classmethod
    def poll(self, context):
        armature = context.armature
        return armature is not None
    
    def draw(self, context):
        menu_draw_armature(self, context, context.armature)

class OBJEX_PT_armature_view3d(bpy.types.Panel):
    bl_category = "Objex"
    bl_label = 'Skeleton'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_context = '.objectmode'
    
    @classmethod
    def poll(self, context:bpy.types.Context):
        if context.object.find_armature():
            return True
        return False
    
    def draw(self, context):
        menu_draw_armature(self, context, context.object.find_armature().data)

# material

def stripPrefix(s, prefix):
    return s[len(prefix):] if s.startswith(prefix) else s

# NodeSocketInterface

class OBJEX_NodeSocketInterface_CombinerIO():
    def draw(self, context, layout):
        pass
    def draw_color(self, context):
        return CST.COLOR_OK

class OBJEX_NodeSocketInterface_CombinerInput(bpy.types.NodeSocketInterface, OBJEX_NodeSocketInterface_CombinerIO):
    bl_socket_idname = 'OBJEX_NodeSocket_CombinerInput'

# registering NodeSocketInterface classes without registering their NodeSocket classes
# led to many EXCEPTION_ACCESS_VIOLATION crashs, so don't do that
OBJEX_NodeSocketInterface_CombinerOutput = None
OBJEX_NodeSocketInterface_RGBA_Color = None

class OBJEX_NodeSocketInterface_Dummy():
    def draw(self, context, layout):
        pass
    def draw_color(self, context):
        return CST.COLOR_NONE

# NodeSocket

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
        if OBJEX_NodeSocket_CombinerOutput is not None: # < 2.80
            if otherSocket.bl_idname != combinerOutputClassName:
                return None, 'Bad link to %s' % otherSocket.bl_idname
            if cycle == CST.CYCLE_COLOR:
                return otherSocket.flagColorCycle, None
            else: # CST.CYCLE_ALPHA
                return otherSocket.flagAlphaCycle, None
        else: # 2.80+
            key = '%s %s' % (
                    'flagColorCycle' if cycle == CST.CYCLE_COLOR else 'flagAlphaCycle',
                    otherSocket.identifier)
            if otherSocket.bl_idname != combinerOutputClassName or key not in otherSocket.node:
                return None, 'Bad link to %s' % otherSocket.bl_idname
            return otherSocket.node[key], None

    def draw(self, context, layout, node, text):
        # don't do anything fancy in node group "inside" view
        if node.bl_idname == 'NodeGroupInput':
            layout.label(text=text)
            return
        cycle = self.node.get('cycle')
        name = self.name # A,B,C,D
        if node.name == 'OBJEX_AlphaCycle0' or node.name == 'OBJEX_ColorCycle0':
            cycle_id = 0
        else:
            cycle_id = 1
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
        input_flags_prop_name = 'input_flags_%s_%s_%d' % (cycle, name, cycle_id)
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
        cycle = self.node.get('cycle')
        name = self.name # A,B,C,D
        return CST.COLOR_OK if (
            flag and not warnMsg
            and flag in CST.COMBINER_FLAGS_SUPPORT[cycle][name]
        ) else CST.COLOR_BAD

def input_flag_list_choose_get(cycle, variable, cycle_id):
        def input_flag_list_choose(self, context):
            log = getLogger('interface')
            input_flags_prop_name = 'input_flags_%s_%s_%d' % (cycle, variable, cycle_id)
            flag = getattr(self, input_flags_prop_name)
            if flag == '_':
                return
            tree = self.id_data
            matching_socket = None
            for n in tree.nodes:
                for s in n.outputs:
                    if s.bl_idname == combinerOutputClassName:
                        if OBJEX_NodeSocket_CombinerOutput is not None: # < 2.80
                            socket_flag = s.flagColorCycle if cycle == CST.CYCLE_COLOR else s.flagAlphaCycle
                        else: # 2.80+
                            key = '%s %s' % (
                                    'flagColorCycle' if cycle == CST.CYCLE_COLOR else 'flagAlphaCycle',
                                    s.identifier)
                            socket_flag = n[key] if key in n else None
                        if flag == socket_flag:
                            if matching_socket:
                                log.error('Found several sockets for flag {}: {!r} {!r}', flag, matching_socket, s)
                            matching_socket = s
            if not matching_socket:
                log.error('Did not find any socket for flag {}', flag)
                return
            while self.links:
                tree.links.remove(self.links[0])
            tree.links.new(matching_socket, self)
        
        return input_flag_list_choose

for cycle in (CST.CYCLE_COLOR, CST.CYCLE_ALPHA):
    for cycle_id in (0, 1):
        for variable in ('A','B','C','D'):
            setattr(
                OBJEX_NodeSocket_CombinerInput,
                'input_flags_%s_%s_%d' % (cycle, variable, cycle_id),
                bpy.props.EnumProperty(
                    items=sorted(
                        (flag, stripPrefix(flag, CST.COMBINER_FLAGS_PREFIX[cycle]), flag)
                            for flag in CST.COMBINER_FLAGS_SUPPORT[cycle][variable]
                            if cycle_id != 0 or flag not in ('G_CCMUX_COMBINED','G_CCMUX_COMBINED_ALPHA','G_ACMUX_COMBINED')
                    ) + [('_','...','')],
                    name='%s' % variable,
                    default='_',
                    update=input_flag_list_choose_get(cycle, variable, cycle_id)
                )
            )
del input_flag_list_choose_get

combinerInputClassName = 'OBJEX_NodeSocket_CombinerInput'

# 421FIXME_UPDATE this could use refactoring?
# I have no idea how to do custom color sockets in 2.80+...
OBJEX_NodeSocket_CombinerOutput = None
OBJEX_NodeSocket_RGBA_Color = None
combinerOutputClassName = 'NodeSocketColor'
rgbaColorClassName = 'NodeSocketColor'

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
    tree.inputs.new(combinerInputClassName, 'A')
    tree.inputs.new(combinerInputClassName, 'B')
    tree.inputs.new(combinerInputClassName, 'C')
    tree.inputs.new(combinerInputClassName, 'D')

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
    tree.outputs.new(combinerOutputClassName, 'Result')
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
    tree.outputs.new(combinerOutputClassName, colorValueName)
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
    # this trick also seems to work fine in 2.82 though I'm not sure if it is required then
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
        # 421FIXME_UPDATE detect the -1;1 / 0;1 uv range in a cleaner way? not sure the break was exactly at 2.80
        blenderNodesUvRangeIsMinusOneToOne = bpy.app.version < (2, 80, 0)
        if blenderNodesUvRangeIsMinusOneToOne: # < 2.80
            # (-1 ; 1) -> (0 ; 1)
            ranged02 = addMathNode('ADD', (-600,200+y), separateXYZ.outputs[i], 1)
            ranged01 = addMathNode('DIVIDE', (-400,200+y), ranged02, 2)
        else: # 2.80+
            ranged01 = separateXYZ.outputs[i]
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
        # mirror v back around 1/2
        if uv == 'V':
            final01range = addMathNode('SUBTRACT', (3000,500+y), 1, final64space)
        else:
            final01range = final64space
        if blenderNodesUvRangeIsMinusOneToOne: # < 2.80
            # (0 ; 1) -> (-1 ; 1)
            final02range = addMathNode('MULTIPLY', (3100,300+y), final01range, 2)
            final[uv] = addMathNode('SUBTRACT', (3300,300+y), final02range, 1)
        else: # 2.80+
            final[uv] = final01range
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
    Inputs: {rgbaColorClassName} 'Color', NodeSocketFloat 'Alpha'
    Outputs: {combinerOutputClassName} 'Color', {combinerOutputClassName} 'Alpha'
    """
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    inputs_node = tree.nodes.new('NodeGroupInput')
    inputs_node.location = (-100,50)
    tree.inputs.new(rgbaColorClassName, 'Color')
    alpha_input_socket = tree.inputs.new('NodeSocketFloat', 'Alpha')
    alpha_input_socket.default_value = 1
    alpha_input_socket.min_value = 0
    alpha_input_socket.max_value = 1

    alpha_3d = tree.nodes.new('ShaderNodeCombineRGB')
    for i in range(3):
        tree.links.new(inputs_node.outputs[1], alpha_3d.inputs[i])

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (100,50)
    tree.outputs.new(combinerOutputClassName, 'Color')
    tree.outputs.new(combinerOutputClassName, 'Alpha')
    tree.links.new(inputs_node.outputs[0], outputs_node.inputs['Color'])
    tree.links.new(alpha_3d.outputs[0], outputs_node.inputs['Alpha'])

    return tree

def create_node_group_single_value(group_name):
    """
    Simple group to input a single value
    Inputs: NodeSocketFloat 'Value'
    Outputs: {combinerOutputClassName} 'Value'
    """
    tree = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    inputs_node = tree.nodes.new('NodeGroupInput')
    inputs_node.location = (-100,50)
    input_socket = tree.inputs.new('NodeSocketFloat', 'Value')
    input_socket.default_value = 1
    input_socket.min_value = 0
    input_socket.max_value = 1

    value_3d = tree.nodes.new('ShaderNodeCombineRGB')
    for i in range(3):
        tree.links.new(inputs_node.outputs[0], value_3d.inputs[i])

    outputs_node = tree.nodes.new('NodeGroupOutput')
    outputs_node.location = (100,50)
    tree.outputs.new(combinerOutputClassName, 'Value')
    tree.links.new(value_3d.outputs[0], outputs_node.inputs['Value'])

    return tree

def update_node_groups():
    log = getLogger('interface')
    # dict mapping group names (keys in bpy.data.node_groups) to (latest_version, create_function) tuples
    # version is stored in 'objex_version' for each group and compared to latest_version
    # usage: increment associated latest_version when making changes in the create_function of some group
    # WARNING: bumping version here is not enough, material version should be bumped too (see data_updater.py)
    groups = {
        'OBJEX_Cycle': (2, create_node_group_cycle),
        'OBJEX_Color0': (1, lambda group_name: create_node_group_color_static(group_name, (0,0,0,0), '0')),
        'OBJEX_Color1': (1, lambda group_name: create_node_group_color_static(group_name, (1,1,1,1), '1')),
        'OBJEX_UV_pipe_main': (1, create_node_group_uv_pipe_main),
        'OBJEX_UV_pipe': (2, create_node_group_uv_pipe),
        'OBJEX_rgba_pipe': (2, create_node_group_rgba_pipe),
        'OBJEX_single_value': (1, create_node_group_single_value),
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
            log.debug('Renamed old group {} (version {} < {}) to {}', group_name, old_node_group['objex_version'], latest_version, old_node_group.name)
        # group must be (re)created
        if not current_node_group:
            log.debug('Creating group {} with {!r}', group_name, group_create)
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

    @classmethod
    def poll(cls, context):
        return context.object and context.object.data.objex_bonus.type == 'MESH'

    def execute(self, context):
        log = getLogger('OBJEX_OT_material_build_nodes')

        scene = context.scene

        if self.target_material_name:
            material = bpy.data.materials[self.target_material_name]
        else:
            material = context.material

        # let the user choose, as use_transparency is used when
        # exporting to distinguish opaque and translucent geometry
        #material.use_transparency = True # < 2.80
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
            node_force_inputs_attributes = node_data.get('force-inputs-attributes', EMPTY_DICT)
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
                if node and node.bl_idname != node_type:
                    node.name = node.name + '_old'
                    node = None
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
            created_node = False
            if not node:
                created_node = True
                node = nodes.new(node_type)
                if node_type_group:
                    node.node_tree = bpy.data.node_groups[node_type_group]
                for input_socket_key, default_value in node_inputs.items():
                    node.inputs[input_socket_key].default_value = default_value
                for output_socket_key, default_value in node_outputs.items():
                    node.outputs[output_socket_key].default_value = default_value
                for output_socket_key, flags in node_outputs_combiner_flags.items():
                    color_flag, alpha_flag = flags
                    socket = node.outputs[output_socket_key]
                    if OBJEX_NodeSocket_CombinerOutput: # < 2.80 (421FIXME_UPDATE)
                        socket.flagColorCycle = color_flag if color_flag else ''
                        socket.flagAlphaCycle = alpha_flag if alpha_flag else ''
                    else: # 2.80+
                        # 421FIXME_UPDATE not sure how bad/hacky this is
                        node['flagColorCycle %s' % socket.identifier] = color_flag if color_flag else ''
                        node['flagAlphaCycle %s' % socket.identifier] = alpha_flag if alpha_flag else ''
                for k, v in node_properties_dict.items():
                    node[k] = v
            elif node_type_group and self.update_groups_of_existing:
                node.node_tree = bpy.data.node_groups[node_type_group]
            for input_socket_key, socket_attributes in node_force_inputs_attributes.items():
                socket = node.inputs[input_socket_key]
                for k, v in socket_attributes.items():
                    try:
                        setattr(socket, k, v)
                    except ValueError:
                        log.warn('{} setattr({!r}, {!r}, {!r}) ValueError '
                                '(this can be ignored if happening while updating a material)',
                                node_name, socket, k, v)
            node.name = node_name # todo set unconditionally? won't set the name if already taken. rename others first? (set exact name needed for 2nd pass with links)
            if self.set_looks or created_node:
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
            node_tree.links.new(nodes['OBJEX_Texel0'].outputs[0], cc0.inputs['A'])
            node_tree.links.new(nodes['OBJEX_Color0'].outputs[0], cc0.inputs['B'])
            node_tree.links.new(nodes['OBJEX_PrimColor'].outputs[0], cc0.inputs['C'])
            node_tree.links.new(nodes['OBJEX_Color0'].outputs[0], cc0.inputs['D'])

            node_tree.links.new(nodes['OBJEX_Texel0'].outputs[1], ac0.inputs['A'])
            node_tree.links.new(nodes['OBJEX_Color0'].outputs[0], ac0.inputs['B'])
            node_tree.links.new(nodes['OBJEX_PrimColor'].outputs[1], ac0.inputs['C'])
            node_tree.links.new(nodes['OBJEX_Color0'].outputs[0], ac0.inputs['D'])

            # cycle 1: (RESULT - 0) * SHADE + 0
            cc1 = nodes['OBJEX_ColorCycle1']
            ac1 = nodes['OBJEX_AlphaCycle1']
            node_tree.links.new(cc0.outputs[0], cc1.inputs['A'])
            node_tree.links.new(nodes['OBJEX_Color0'].outputs[0], cc1.inputs['B'])
            node_tree.links.new(nodes['OBJEX_Shade'].outputs[0], cc1.inputs['C'])
            node_tree.links.new(nodes['OBJEX_Color0'].outputs[0], cc1.inputs['D'])

            node_tree.links.new(ac0.outputs[0], ac1.inputs['A'])
            node_tree.links.new(nodes['OBJEX_Color0'].outputs[0], ac1.inputs['B'])
            node_tree.links.new(nodes['OBJEX_Shade'].outputs[1], ac1.inputs['C'])
            node_tree.links.new(nodes['OBJEX_Color0'].outputs[0], ac1.inputs['D'])

            # combiners output
            principledBSDF = nodes['Principled BSDF']
            node_tree.links.new(cc1.outputs[0], principledBSDF.inputs['Base Color'])
            node_tree.links.new(ac1.outputs[0], principledBSDF.inputs['Alpha'])

        if not scene.objex_bonus.is_objex_scene:
            scene.objex_bonus.is_objex_scene = True
            addon_preferences = util.get_addon_preferences()
            if addon_preferences:
                colorspace_strategy = addon_preferences.colorspace_default_strategy
                if colorspace_strategy == 'AUTO':
                    colorspace_strategy = 'WARN'
                scene.objex_bonus.colorspace_strategy = colorspace_strategy
            else:
                log.info('No addon preferences, assuming background mode, scene color space strategy stays at default {}',
                    scene.objex_bonus.colorspace_strategy)
        if not material.objex_bonus.is_objex_material:
            material.objex_bonus.is_objex_material = True
            watch_objex_material(material)
        # 421fixme why is objex_version set here? data_updater says it's up to the update functions to do it
        material.objex_bonus.objex_version = data_updater.addon_material_objex_version
        material.objex_bonus.use_display = True
        material.objex_bonus.use_collision = False

        # Update all input_flags
        cc0 = nodes['OBJEX_ColorCycle0']
        ac0 = nodes['OBJEX_AlphaCycle0']
        cc1 = nodes['OBJEX_ColorCycle1']
        ac1 = nodes['OBJEX_AlphaCycle1']
        for input, input_flags_prop_name, cycle_type in (
                ( cc0.inputs['A'], 'input_flags_C_A_0', 'C'),
                ( cc0.inputs['B'], 'input_flags_C_B_0', 'C'),
                ( cc0.inputs['C'], 'input_flags_C_C_0', 'C'),
                ( cc0.inputs['D'], 'input_flags_C_D_0', 'C'),

                ( cc1.inputs['A'], 'input_flags_C_A_1', 'C'),
                ( cc1.inputs['B'], 'input_flags_C_B_1', 'C'),
                ( cc1.inputs['C'], 'input_flags_C_C_1', 'C'),
                ( cc1.inputs['D'], 'input_flags_C_D_1', 'C'),

                ( ac0.inputs['A'], 'input_flags_A_A_0', 'A'),
                ( ac0.inputs['B'], 'input_flags_A_B_0', 'A'),
                ( ac0.inputs['C'], 'input_flags_A_C_0', 'A'),
                ( ac0.inputs['D'], 'input_flags_A_D_0', 'A'),

                ( ac1.inputs['A'], 'input_flags_A_A_1', 'A'),
                ( ac1.inputs['B'], 'input_flags_A_B_1', 'A'),
                ( ac1.inputs['C'], 'input_flags_A_C_1', 'A'),
                ( ac1.inputs['D'], 'input_flags_A_D_1', 'A'),
            ):
                cycle = input.node.get('cycle')

                if cycle_type == 'A':
                    def_value = 'G_ACMUX_0'
                else:
                    def_value = 'G_CCMUX_0'

                if input.links:
                    otherSocket = input.links[0].from_socket
                    key = '%s %s' % ('flagColorCycle' if cycle == CST.CYCLE_COLOR else 'flagAlphaCycle', otherSocket.identifier)
                    setattr(input, input_flags_prop_name, otherSocket.node[key])
                else:
                    setattr(input, input_flags_prop_name, def_value)

        if material.node_tree.nodes['OBJEX_Shade'].inputs['Color'].links[0].from_socket.node.name == 'Vertex Color':
            setattr(material.objex_bonus, 'shading', 'VERTEX_COLOR')
        else:
            setattr(material.objex_bonus, 'shading', 'LIGHTING')

        if material.blend_method != 'HASHED':
            setattr(material.objex_bonus, 'alpha_mode', material.blend_method)
        else:
            setattr(material.objex_bonus, 'alpha_mode', 'BLEND')
        
        for wrap, mirror, property in (
                (
                    material.node_tree.nodes["OBJEX_TransformUV0"].inputs[3].default_value,
                    material.node_tree.nodes["OBJEX_TransformUV0"].inputs[5].default_value,
                    'texture_u_0'
                ),
                (
                    material.node_tree.nodes["OBJEX_TransformUV1"].inputs[3].default_value,
                    material.node_tree.nodes["OBJEX_TransformUV1"].inputs[5].default_value,
                    'texture_u_1'
                ),
                (
                    material.node_tree.nodes["OBJEX_TransformUV0"].inputs[4].default_value,
                    material.node_tree.nodes["OBJEX_TransformUV0"].inputs[6].default_value,
                    'texture_v_0'
                ),
                (
                    material.node_tree.nodes["OBJEX_TransformUV1"].inputs[4].default_value,
                    material.node_tree.nodes["OBJEX_TransformUV1"].inputs[6].default_value,
                    'texture_v_1'
                ),
            ):
            if mirror:
                setattr(material.objex_bonus, property, 'MIRROR')
            elif wrap:
                setattr(material.objex_bonus, property, 'WRAP')
            else:
                setattr(material.objex_bonus, property, 'CLAMP')

        return {'FINISHED'}

class OBJEX_OT_material_init_collision(bpy.types.Operator):

    bl_idname = 'objex.material_init_collision'
    bl_label = 'Initialize a material for use on Objex export as collision'
    bl_options = {'INTERNAL', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object and context.object.data.objex_bonus.type == 'COLLISION'

    def execute(self, context):
        material = context.material
        node = material.node_tree.nodes['Principled BSDF']

        node.inputs[7].default_value = 0.005
        material.objex_bonus.is_objex_material = True
        material.objex_bonus.use_display = False
        material.objex_bonus.use_collision = True

        return {'FINISHED'}

# properties and non-node UI

def init_watch_objex_materials():
    log = getLogger('interface')
    log.debug('Looking for objex materials to watch')
    watched = []
    ignored = []
    for material in bpy.data.materials:
        if material.objex_bonus.is_objex_material and material.objex_bonus.use_display:
            watch_objex_material(material)
            watched.append(material)
        else:
            ignored.append(material)
    log.debug('Watching: {}, ignored: {}', ', '.join(mat.name for mat in watched), ', '.join(mat.name for mat in ignored))

def watch_objex_material(material):
    if blender_version_compatibility.has_per_material_backface_culling:
        watch_objex_material_backface_culling(material)

def watch_objex_material_backface_culling(material):
    log = getLogger('interface')
    log.trace('Watching use_backface_culling of material {} sync_backface_culling = {!r}',
        material.name, bpy.context.scene.objex_bonus.sync_backface_culling)
    bpy.msgbus.subscribe_rna(
        key=material.path_resolve('use_backface_culling', False),
        owner=msgbus_owner,
        args=(material,),
        notify=blender_use_backface_culling_update,
        # 421fixme I don't know what PERSISTENT would do
        # renaming material or object using it doesnt prevent notifications when it isn't set
        #options={'PERSISTENT'}
    )
    if (material.objex_bonus.backface_culling != material.use_backface_culling
        and bpy.context.scene.objex_bonus.sync_backface_culling
    ):
        if 'OBJEX_TO_BLENDER' in bpy.context.scene.objex_bonus.sync_backface_culling:
            log.trace('{} notifying objex backface_culling', material.name)
            # trigger objex_backface_culling_update
            material.objex_bonus.backface_culling = material.objex_bonus.backface_culling
        else: # sync_backface_culling == {'BLENDER_TO_OBJEX'}
            log.trace('{} notifying Blender use_backface_culling', material.name)
            # trigger blender_use_backface_culling_update
            material.use_backface_culling = material.use_backface_culling

def blender_use_backface_culling_update(material):
    log = getLogger('interface')
    log.trace('sync_backface_culling = {!r}', bpy.context.scene.objex_bonus.sync_backface_culling)
    if (material.objex_bonus.backface_culling != material.use_backface_culling
        and 'BLENDER_TO_OBJEX' in bpy.context.scene.objex_bonus.sync_backface_culling
    ):
        log.trace('{} Blender use_backface_culling = {}', material.name, material.use_backface_culling)
        if material.objex_bonus.is_objex_material and material.objex_bonus.use_display:
            material.objex_bonus.backface_culling = material.use_backface_culling
        else:
            log.trace('But material is not a display objex material, ignoring it.')

def objex_backface_culling_update(self, context):
    material = self.id_data
    if material.objex_bonus.is_objex_material:
        material.use_backface_culling = material.objex_bonus.backface_culling

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
            draw_build_nodes_operator(self.layout, 'Init Display Objex material', init=True)
            self.layout.operator('objex.material_init_collision', text='Init Collision Objex material')
            return
        if data.use_collision:
            if not context.object.data.objex_bonus.type == 'COLLISION':
                box = self.layout.box()
                box.alert = True
                box.label(text='', icon='ERROR')
                box.label(text='Can\'t use collision material for mesh!')
                return
            self.menu_collision(context)

            return
        if context.object and context.object.data.objex_bonus.type == 'COLLISION':
            box = self.layout.box()
            box.alert = True
            box.label(text='', icon='ERROR')
            box.label(text='Can\'t use mesh material for collision!')
            return
        # handle is_objex_material, use_nodes mismatch
        if not material.use_nodes:
            messages = (
                ('',                         'ERROR'),
                ('Material was initialized', 'NONE'),
                ('as an objex material',     'NONE'),
                ('but does not use nodes',   'NONE'),
                ('Did you uncheck',          'NONE'),
                ('"Use Nodes" for it?',      'NONE'),
            )
            box = self.layout.box()

            for msg, icon in messages:
                row = box.row()
                row.alert = True
                row.label(text=msg, icon=icon)

            box.label(text='Solutions:', icon='INFO')
            sub_box = box.box()
            sub_box.label(text='1) Check "Use Nodes"')
            sub_box.prop(material, 'use_nodes')
            # 421todo "clear objex material" operator "Click here to make this a standard, non-objex, material"
            # would allow ctrl+z
            sub_box = box.box()
            sub_box.label(text='2) Disable objex features')
            sub_box.label(text='for this material')
            sub_box.prop(data, 'is_objex_material')
            sub_box = box.box()
            sub_box.label(text='3) Reset nodes')
            draw_build_nodes_operator(sub_box, 'Reset nodes', init=True, reset=True)
            return
        # update material
        if data_updater.handle_material(material, self.layout):
            draw_build_nodes_operator(self.layout, 'Reset nodes', init=True, reset=True)
            return
        
        self.menu_material(context)
    
    def get_icon(self, attr):
        if attr:
            return 'DOWNARROW_HLT'
        else:
            return 'RIGHTARROW'
    
    def foldable_menu(self, element, data, attr):
        element.prop(data, attr, icon=self.get_icon(getattr(data, attr)), emboss=False)
        if getattr(data, attr) == True:
            return True
        return False

    def menu_collision(self, context):
        objex_scene = context.scene.objex_bonus
        material:bpy.types.Material = context.material
        color_value = material.node_tree.nodes["Principled BSDF"].inputs[0]
        alpha_value = material.node_tree.nodes["Principled BSDF"].inputs[21]
        data = material.objex_bonus

        box = self.layout.box()
        box.use_property_split = False
        row = box.row()
        row.alignment = 'CENTER'
        row.label(text='Collision')

        col = data.collision

        row = box.row()
        row.prop(color_value, 'default_value', text="")
        row.prop(col, 'alpha', text="", slider=True)

        box.prop(col, 'sound')
        box.prop(col, 'floor')
        box.prop(col, 'wall')
        box.prop(col, 'special')

        row = box.row()
        row.prop(col, 'ignore_camera')
        row.prop(col, 'ignore_entity')

        row = box.row()
        row.prop(col, 'ignore_ammo')
        row.prop(col, 'horse')

        row = box.row()
        row.prop(col, 'one_lower')
        row.prop(col, 'wall_damage')

        row = box.row()
        row.prop(col, 'hookshot')
        row.prop(col, 'steep')

        def draw_optional(prop_enable, prop_data):
            if getattr(col, prop_enable):
                row = box.row()
                row.prop(col, prop_enable, text='')
                row.prop(col, prop_data)
            else:
                row = box.row()
                row.prop(col, prop_enable, text='')
                column = row.column()
                column.enabled = False
                column.prop(col, prop_data)

        draw_optional('warp_enabled', 'warp_exit_index')
        draw_optional('camera_enabled', 'camera_index')
        draw_optional('echo_enabled', 'echo_index')
        draw_optional('lighting_enabled', 'lighting_index')

        if col.conveyor_enabled:
            box.prop(col, 'conveyor_enabled')
            sub_box = box.box()
            sub_box.prop(col, 'conveyor_direction')
            sub_box.row().prop(col, 'conveyor_speed', expand=True)
            sub_box.prop(col, 'conveyor_inherit')
        else:
            box.prop(col, 'conveyor_enabled')

    def menu_material(self, context):
        material = context.material
        data = material.objex_bonus
        objex_scene = context.scene.objex_bonus
        mode_menu = objex_scene.mode_menu

        data_is_empty = data.empty or material.name.startswith('empty.')

        box = self.layout.box()
        box.use_property_split = False
        if self.foldable_menu(box, objex_scene, "menu_tools"):
            shared_row = box.row()

            draw_build_nodes_operator(shared_row, 'Reset nodes', init=True, reset=True)
            draw_build_nodes_operator(shared_row, 'Fix nodes')
            shared_row = box.row()
            shared_row.operator('objex.material_single_texture', text='Single Texture')
            shared_row.operator('objex.material_multitexture', text='Multitexture')
            shared_row.operator('objex.material_flat_color', text='Flat Color')

            scene = context.scene
            sub_box = box.box()
            sub_box.label(text='Color Space Strategy:')
            sub_box.prop(objex_scene, 'colorspace_strategy', text='')

        box = self.layout.box()
        box.use_property_split = False
        if self.foldable_menu(box, objex_scene, "menu_common"):
            row = box.row()
            row.use_property_split = False
            row.prop(data, 'alpha_mode', expand=True)

            row = box.row()
            row.use_property_split = False
            row.prop(data, 'shading', expand=True)
            
            box.prop(data, 'backface_culling')
            box.use_property_split = False

            for color_node, alpha_node, property, title in (
                (
                    material.node_tree.nodes["OBJEX_PrimColorRGB"].outputs[0],
                    material.node_tree.nodes["OBJEX_PrimColor"].inputs[1],
                    'write_primitive_color', 'Prim'
                ),
                (
                    material.node_tree.nodes["OBJEX_EnvColorRGB"].outputs[0],
                    material.node_tree.nodes["OBJEX_EnvColor"].inputs[1],
                    'write_environment_color', 'Env'
                ),
            ):
                sub_box = box.box()

                row = sub_box.row()
                row.label(text=title, icon='COLOR')

                row = sub_box.row()
                row.prop(data, property, text='')
                col = row.column()
                if not getattr(data, property):
                    col.enabled = False
                row = col.row()
                row.prop(color_node, 'default_value', text='')
                row.prop(alpha_node, 'default_value', text='')

        box = self.layout.box()
        if self.foldable_menu(box, objex_scene, "menu_material"):
            row = box.row()
            row.enabled = not(data_is_empty)
            row.prop(objex_scene, 'mode_menu', expand=True)

            if data_is_empty:
                box = box.box()
                if material.name.startswith('empty.'):
                    box.label(text='empty (material name starts with "empty.")', icon='CHECKBOX_HLT')
                else:
                    box.prop(data, 'empty')
                if blender_version_compatibility.no_ID_PointerProperty:
                    box.prop_search(data, 'branch_to_object', bpy.data, 'objects')
                    box.label(text='(mesh objects only)')
                else:
                    box.prop(data, 'branch_to_object')
                if data.branch_to_object: # branch_to_object is a MESH object
                    if blender_version_compatibility.no_ID_PointerProperty:
                        branch_to_object = bpy.data.objects[data.branch_to_object]
                    else:
                        branch_to_object = data.branch_to_object
                    branch_to_object_armature = branch_to_object.find_armature()
                    if branch_to_object_armature:
                        if branch_to_object.data.objex_bonus.attrib_NOSPLIT:
                            box.label(text='%s is marked NOSPLIT' % branch_to_object.name, icon='INFO')
                        else:
                            valid_bone = data.branch_to_object_bone in branch_to_object_armature.data.bones
                            box.prop_search(data, 'branch_to_object_bone', branch_to_object_armature.data, 'bones', icon=('NONE' if valid_bone else 'ERROR'))
                            if not valid_bone:
                                box.label(text='A bone must be picked', icon='ERROR')
                                box.label(text='NOSPLIT is off on %s' % branch_to_object.name, icon='INFO')
                return

            if mode_menu == 'menu_mode_render':
                sub_box = box.box()
                
                sub_box.prop(data, 'texture_filter')

                row = sub_box.row()
                row.prop(data, 'geometrymode_G_FOG')
                row.prop(data, 'rendermode_blender_flag_Z_CMP')
                row.prop(data, 'rendermode_blender_flag_Z_UPD')
                row = sub_box.row()
                row.prop(data, 'rendermode_blender_flag_IM_RD')
                row.prop(data, 'rendermode_blender_flag_AA_EN')
                row.prop(data, 'geometrymode_G_ZBUFFER', text='G_ZBUFFER')
                row = sub_box.row()
                row.prop(data, 'rendermode_blender_flag_CLR_ON_CVG')
                row.prop(data, 'rendermode_blender_flag_ALPHA_CVG_SEL')
                row.prop(data, 'rendermode_blender_flag_CVG_X_ALPHA')
                row = sub_box.row()
                row.prop(data, 'geometrymode_G_SHADING_SMOOTH')
                row.prop(data, 'rendermode_forceblending')
                row.label(text="")

                sub_box.row().prop(data, 'rendermode_blender_flag_CVG_DST_', expand=True)
                sub_box.row().prop(data, 'rendermode_zmode', expand=True)

                sub_sub_box = sub_box.box()
                sub_sub_box.prop(data, 'rendermode_blending_cycle0')
                if data.rendermode_blending_cycle0 == 'CUSTOM':
                    for v in ('P','A','M','B'):
                        sub_sub_box.prop(data, 'rendermode_blending_cycle0_custom_%s' % v, text='')

                sub_sub_box = sub_box.box()
                sub_sub_box.prop(data, 'rendermode_blending_cycle1')
                if data.rendermode_blending_cycle1 == 'CUSTOM':
                    for v in ('P','A','M','B'):
                        sub_sub_box.prop(data, 'rendermode_blending_cycle1_custom_%s' % v, text='')
            elif mode_menu == 'menu_mode_texture':
                for texel, u_scale, v_scale, texture_u, texture_v, menu in (
                    (
                        material.node_tree.nodes["OBJEX_Texel0Texture"], 
                        material.node_tree.nodes["OBJEX_TransformUV0"].inputs[1], 
                        material.node_tree.nodes["OBJEX_TransformUV0"].inputs[2], 
                        'texture_u_0', 
                        'texture_v_0',
                        'menu_texel0',
                    ),
                    (
                        material.node_tree.nodes["OBJEX_Texel1Texture"], 
                        material.node_tree.nodes["OBJEX_TransformUV1"].inputs[1], 
                        material.node_tree.nodes["OBJEX_TransformUV1"].inputs[2], 
                        'texture_u_1', 
                        'texture_v_1',
                        'menu_texel1',
                    ),
                ):
                    sub_box = box.box()
                    
                    sub_box.prop(objex_scene, menu, icon=self.get_icon(getattr(objex_scene, menu)), emboss=False)
                    sub_box.template_ID(texel, 'image', open='image.open')

                    if texel.image:
                        imdata = texel.image.objex_bonus
                        propOffset(sub_box, imdata, 'pointer', 'Pointer')   
                        row = sub_box.row()
                        row.prop(material.objex_bonus, texture_u, text='', icon='EVENT_X')
                        row.prop(material.objex_bonus, texture_v, text='', icon='EVENT_Y')

                        if getattr(objex_scene, menu):
                            row = sub_box.row()
                            row.prop(u_scale, 'default_value', text='X Exp')
                            row.prop(v_scale, 'default_value', text='Y Exp')

                            sub_box.prop(imdata, 'priority')
                            row = sub_box.row()
                            row.label(text='Texture bank:')
                            row.template_ID(imdata, 'texture_bank', open='image.open')
                            sub_box.prop(imdata, 'format')
                            if imdata.format[:2] == 'CI':
                                sub_box.prop(imdata, 'palette')
                            sub_box.prop(imdata, 'alphamode')
                            sub_box.prop(imdata, 'force_write')



                sub_box = box.box()
                row = sub_box.row()

                row.prop(material.node_tree.nodes["OBJEX_TransformUV_Main"].inputs[2], 'default_value', text='Texgen ')
                col = row.column()

                if material.node_tree.nodes["OBJEX_TransformUV_Main"].inputs[2].default_value:
                    col.enabled = True
                else:
                    col.enabled = False
                
                col.prop(material.node_tree.nodes["OBJEX_TransformUV_Main"].inputs[3], 'default_value', text='Texgen Linear')
                
                row = sub_box.row()
                row.prop(material.node_tree.nodes["OBJEX_TransformUV_Main"].inputs[4], 'default_value', text='U Scale')
                row.prop(material.node_tree.nodes["OBJEX_TransformUV_Main"].inputs[5], 'default_value', text='V Scale')

                box.operator('objex.set_pixels_along_uv_from_image_dimensions', text='Fix clamping')
            elif mode_menu == 'menu_mode_combiner':
                sub_box = box.box()
                sub_box.label(text='Color')
                cc0 = material.node_tree.nodes["OBJEX_ColorCycle0"]
                cc1 = material.node_tree.nodes["OBJEX_ColorCycle1"]
                ac0 = material.node_tree.nodes["OBJEX_AlphaCycle0"]
                ac1 = material.node_tree.nodes["OBJEX_AlphaCycle1"]

                row = sub_box.row()
                row.prop(cc0.inputs[0], 'input_flags_C_A_0', text='', icon='EVENT_A')
                row.prop(cc1.inputs[0], 'input_flags_C_A_1', text='', icon='EVENT_A')
                
                row = sub_box.row()
                row.prop(cc0.inputs[1], 'input_flags_C_B_0', text='', icon='EVENT_B')
                row.prop(cc1.inputs[1], 'input_flags_C_B_1', text='', icon='EVENT_B')
                
                row = sub_box.row()
                row.prop(cc0.inputs[2], 'input_flags_C_C_0', text='', icon='EVENT_C')
                row.prop(cc1.inputs[2], 'input_flags_C_C_1', text='', icon='EVENT_C')
                
                row = sub_box.row()
                row.prop(cc0.inputs[3], 'input_flags_C_D_0', text='', icon='EVENT_D')
                row.prop(cc1.inputs[3], 'input_flags_C_D_1', text='', icon='EVENT_D')

                sub_box.label(text='Alpha')

                row = sub_box.row()
                row.prop(ac0.inputs[0], 'input_flags_A_A_0', text='', icon='EVENT_A')
                row.prop(ac1.inputs[0], 'input_flags_A_A_1', text='', icon='EVENT_A')
                
                row = sub_box.row()
                row.prop(ac0.inputs[1], 'input_flags_A_B_0', text='', icon='EVENT_B')
                row.prop(ac1.inputs[1], 'input_flags_A_B_1', text='', icon='EVENT_B')
                
                row = sub_box.row()
                row.prop(ac0.inputs[2], 'input_flags_A_C_0', text='', icon='EVENT_C')
                row.prop(ac1.inputs[2], 'input_flags_A_C_1', text='', icon='EVENT_C')
                
                row = sub_box.row()
                row.prop(ac0.inputs[3], 'input_flags_A_D_0', text='', icon='EVENT_D')
                row.prop(ac1.inputs[3], 'input_flags_A_D_1', text='', icon='EVENT_D')
            elif mode_menu == 'menu_mode_settings':
                sub_box = box.box()
                sub_box.use_property_split = False

                row = sub_box.row()
                row.use_property_split = False
                row.prop(data, 'empty') # (at this point, material isn't empty)
                row.prop(data, 'standalone')
                row.prop(data, 'force_write')
                
                sub_box.prop(data, 'priority')

                sub_box.row().prop(data, 'vertex_shading', expand=True)
                sub_box.prop(data, 'external_material_segment')

class OBJEX_OT_set_pixels_along_uv_from_image_dimensions(bpy.types.Operator):

    bl_idname = 'objex.set_pixels_along_uv_from_image_dimensions'
    bl_label = 'Set Pixels along U/V socket values to image width/height for improved clamping accuracy'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for material in bpy.data.materials:
            if not (material.objex_bonus.is_objex_material and material.objex_bonus.use_display):
                continue
            for node in material.node_tree.nodes:
                if node.type != 'GROUP':
                    continue
                if node.node_tree.name != 'OBJEX_UV_pipe':
                    continue
                textureNode = node.outputs['UV'].links[0].to_node
                if textureNode.bl_idname == 'ShaderNodeTexture': # < 2.80
                    if not textureNode.texture:
                        continue
                    image = textureNode.texture.image
                else: # 2.80+ assume ShaderNodeTexImage
                    if not textureNode.image:
                        continue
                    image = textureNode.image
                # putting *2 here is simpler than modifying the uv pipe and math nodes again
                # it halves the clamp start offset which becomes eg along U: 1/(width*2) instead of 1/width
                # it makes the offset half a pixel instead of a full pixel (in uv space)
                # so it starts clamping in the "middle" of a pixel instead of the side
                node.inputs['Pixels along U'].default_value = image.size[0] * 2
                node.inputs['Pixels along V'].default_value = image.size[1] * 2
        return {'FINISHED'}

classes = (
    OBJEX_UL_actions,
    OBJEX_PT_armature_prop,
    OBJEX_PT_armature_view3d,
    OBJEX_PT_mesh_object_view3d,
    OBJEX_PT_mesh_object_prop,

    # order matters: each socket interface must be registered before its matching socket
    OBJEX_NodeSocketInterface_CombinerOutput,
    OBJEX_NodeSocketInterface_CombinerInput,
    OBJEX_NodeSocketInterface_RGBA_Color,
    OBJEX_NodeSocket_CombinerOutput,
    OBJEX_NodeSocket_CombinerInput,
    OBJEX_NodeSocket_RGBA_Color,

    OBJEX_OT_material_build_nodes,
    OBJEX_OT_material_init_collision,
    OBJEX_OT_set_pixels_along_uv_from_image_dimensions,
    OBJEX_PT_material,
)

msgbus_owner = object()

# handler arguments seem undocumented and vary between 2.7x and 2.8x anyway
def handler_scene_or_depsgraph_update_post_once(*args):
    if bpy.app.version < (2, 80, 0):
        update_handlers = bpy.app.handlers.scene_update_post
    else:
        update_handlers = bpy.app.handlers.depsgraph_update_post
    update_handlers.remove(handler_scene_or_depsgraph_update_post_once)
    init_watch_objex_materials()

@bpy.app.handlers.persistent
def handler_load_post(*args):
    init_watch_objex_materials()

def register_interface():
    log = getLogger('interface')
    for clazz in classes:
        if clazz is None:
            continue
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

    if bpy.app.version < (2, 80, 0):
        update_handlers = bpy.app.handlers.scene_update_post
    else:
        update_handlers = bpy.app.handlers.depsgraph_update_post
    update_handlers.append(handler_scene_or_depsgraph_update_post_once)
    bpy.app.handlers.load_post.append(handler_load_post)

def unregister_interface():
    log = getLogger('interface')

    if bpy.app.version < (2, 80, 0):
        update_handlers = bpy.app.handlers.scene_update_post
    else:
        update_handlers = bpy.app.handlers.depsgraph_update_post
    try:
        update_handlers.remove(handler_scene_or_depsgraph_update_post_once)
    except ValueError: # already removed
        pass
    try:
        bpy.app.handlers.load_post.remove(handler_load_post)
    except ValueError: # already removed
        log.exception('load_post does not have handler handler_load_post, '
            'but that handler should be persistent and kept enabled')
    if hasattr(bpy, 'msgbus'):
        bpy.msgbus.clear_by_owner(msgbus_owner)

    for clazz in reversed(classes):
        if clazz is None:
            continue
        try:
            bpy.utils.unregister_class(clazz)
        except:
            log.exception('Failed to unregister {!r}', clazz)
