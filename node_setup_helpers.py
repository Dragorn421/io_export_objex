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

from . import interface
from . import blender_version_compatibility
from . import template

def clearLinks(tree, socket):
    while socket.links:
        tree.links.remove(socket.links[0])

def setLinks_multiply_by(tree, colorSocket, alphaSocket, multiply_by):
    if multiply_by == 'LIGHTING':
        if bpy.app.version < (2, 80, 0):
            colorSocket.input_flags_C_C_0 = 'G_CCMUX_SHADE'
            alphaSocket.input_flags_A_C_0 = 'G_ACMUX_SHADE'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_Shade'].outputs['Color'], colorSocket)
            tree.links.new(tree.nodes['OBJEX_Shade'].outputs['Alpha'], alphaSocket)
        tree.links.new(tree.nodes['OBJEX_Color1'].outputs[0], tree.nodes['OBJEX_Shade'].inputs['Color'])
        tree.links.new(tree.nodes['OBJEX_Color1'].outputs[0], tree.nodes['OBJEX_Shade'].inputs['Alpha'])
    elif multiply_by == 'VERTEX_COLORS':
        if bpy.app.version < (2, 80, 0):
            colorSocket.input_flags_C_C_0 = 'G_CCMUX_SHADE'
            alphaSocket.input_flags_A_C_0 = 'G_ACMUX_SHADE'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_Shade'].outputs['Color'], colorSocket)
            tree.links.new(tree.nodes['OBJEX_Shade'].outputs['Alpha'], alphaSocket)
        if 'Vertex Color' in tree.nodes['Geometry'].outputs: # < 2.80
            tree.links.new(tree.nodes['Geometry'].outputs['Vertex Color'], tree.nodes['OBJEX_Shade'].inputs['Color'])
            tree.links.new(tree.nodes['Geometry'].outputs['Vertex Alpha'], tree.nodes['OBJEX_Shade'].inputs['Alpha'])
        else: # 2.80+
            tree.links.new(tree.nodes['Vertex Color'].outputs['Color'], tree.nodes['OBJEX_Shade'].inputs['Color'])
            tree.links.new(tree.nodes['Vertex Color'].outputs['Alpha'], tree.nodes['OBJEX_Shade'].inputs['Alpha'])
    elif multiply_by == 'ENV_COLOR':
        if bpy.app.version < (2, 80, 0):
            colorSocket.input_flags_C_C_0 = 'G_CCMUX_ENVIRONMENT'
            alphaSocket.input_flags_A_C_0 = 'G_ACMUX_ENVIRONMENT'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_EnvColor'].outputs['Color'], colorSocket)
            tree.links.new(tree.nodes['OBJEX_EnvColor'].outputs['Alpha'], alphaSocket)
    elif multiply_by == 'PRIM_COLOR':
        if bpy.app.version < (2, 80, 0):
            colorSocket.input_flags_C_C_0 = 'G_CCMUX_PRIMITIVE'
            alphaSocket.input_flags_A_C_0 = 'G_ACMUX_PRIMITIVE'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_PrimColor'].outputs['Color'], colorSocket)
            tree.links.new(tree.nodes['OBJEX_PrimColor'].outputs['Alpha'], alphaSocket)

class OBJEX_OT_material_combiner(bpy.types.Operator):
    bl_idname = 'objex.material_combiner'
    bl_label = 'Setup Combiner Template'
    bl_options = {'REGISTER', 'UNDO'}

    template_enum = bpy.props.EnumProperty(
        items=[
            ('DEFAULT',     'Default (Texel0, Prim, Shade)',            '', 'SHADING_RENDERED', 0),
            ('DEFAULT_ENV', 'Default (Texel0, Env, Shade)',             '', 'SHADING_RENDERED', 1),
            ('MIX',         'Mix (Texel0, Texel1, Prim, Shade)',        '', 'XRAY',             2),
            ('MIX_ENV',     'Mix (Texel0, Texel1, Env, Shade)',         '', 'XRAY',             3),
            ('LIGHTED',     'Default (Texel0, Prim, Shade Color',       '', 'SHADING_RENDERED', 5),
            ('MULT',        'Multiply (Texel0, Texel1, Shade)',         '', 'SELECT_EXTEND',    4),
            ('FLAME_TEXEL', 'Flame (Texel0, Texel1, Prim, Env, Shade)', '', 'OUTLINER_OB_FORCE_FIELD', 59),
        ],
        default='DEFAULT',
        name='txt'
    )

    def draw(self, context):
        box = self.layout.box()
        box.prop_tabs_enum(self, 'template_enum')

    @classmethod
    def poll(self, context):
        material = context.material if hasattr(context, 'material') else None
        return material and material.objex_bonus.is_objex_material and material.objex_bonus.use_display
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        template.combiner_apply_template(self.template_enum, context.material)
        return {'FINISHED'}

class OBJEX_OT_material_material(bpy.types.Operator):
    bl_idname = 'objex.material_material'
    bl_label = 'Setup Material Template'
    bl_options = {'REGISTER', 'UNDO'}

    template_enum = bpy.props.EnumProperty(
        items=[
            ('OPAQUE',     'OPAQUE',     ''),
            ('CLIP',       'CLIP',       ''),
            ('BLEND',      'BLEND',      ''),
            ('OPAQUE_XLU', 'OPAQUE_XLU', ''),
        ],
        default='OPAQUE',
        name='txt'
    )

    def draw(self, context):
        box = self.layout.box()
        box.prop_tabs_enum(self, 'template_enum')

    @classmethod
    def poll(self, context):
        material = context.material if hasattr(context, 'material') else None
        return material and material.objex_bonus.is_objex_material and material.objex_bonus.use_display
    
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)
    
    def execute(self, context):
        template.material_apply_template(self.template_enum, context.material)
        return {'FINISHED'}

def set_shade_source_vertex_colors(material):
    tree = material.node_tree
    shadeNode = tree.nodes['OBJEX_Shade']
    vertexColorNode = tree.nodes['Vertex Color']
    vertexColorSocketColor = vertexColorNode.outputs['Color']
    color1socket = tree.nodes['OBJEX_Color1'].outputs[0]

    clearLinks(tree, shadeNode.inputs['Color'])
    clearLinks(tree, shadeNode.inputs['Alpha'])
    tree.links.new(vertexColorSocketColor, shadeNode.inputs['Color'])
    tree.links.new(color1socket, shadeNode.inputs['Alpha'])

def set_shade_source_vertex_colors_and_alpha(material):
    tree = material.node_tree
    shadeNode = tree.nodes['OBJEX_Shade']
    vertexColorNode = tree.nodes['Vertex Color']
    vertexColorSocketColor = vertexColorNode.outputs['Color']
    vertexColorSocketAlpha = vertexColorNode.outputs['Alpha']

    clearLinks(tree, shadeNode.inputs['Color'])
    clearLinks(tree, shadeNode.inputs['Alpha'])
    tree.links.new(vertexColorSocketColor, shadeNode.inputs['Color'])
    tree.links.new(vertexColorSocketAlpha, shadeNode.inputs['Alpha'])

def set_shade_source_lighting(material):
    tree = material.node_tree
    shadeNode = tree.nodes['OBJEX_Shade']
    color1socket = tree.nodes['OBJEX_Color1'].outputs[0]

    clearLinks(tree, shadeNode.inputs['Color'])
    clearLinks(tree, shadeNode.inputs['Alpha'])
    tree.links.new(color1socket, shadeNode.inputs['Color'])
    tree.links.new(color1socket, shadeNode.inputs['Alpha'])

class OBJEX_OT_material_set_shade_source_vertex_colors(bpy.types.Operator):

    bl_idname = 'objex.material_set_shade_source_vertex_colors'
    bl_label = 'Set Shade Source Vertex Colors'
    bl_description = 'Link the Shade node of objex materials to use vertex colors'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if hasattr(context, 'material'):
            materials = [context.material]
        else:
            materials = set()
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    for material in obj.data.materials:
                        if material.objex_bonus.is_objex_material and material.objex_bonus.use_display:
                            materials.add(material)
        for material in materials:
            set_shade_source_vertex_colors(material)
        return {'FINISHED'}

class OBJEX_OT_material_set_shade_source_lighting(bpy.types.Operator):

    bl_idname = 'objex.material_set_shade_source_lighting'
    bl_label = 'Set Shade Source Lighting'
    bl_description = 'Link the Shade node of objex materials to use lighting'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if hasattr(context, 'material'):
            materials = [context.material]
        else:
            materials = set()
            for obj in context.selected_objects:
                if obj.type == 'MESH':
                    for material in obj.data.materials:
                        if material.objex_bonus.is_objex_material and material.objex_bonus.use_display:
                            materials.add(material)
        for material in materials:
            set_shade_source_lighting(material)
        return {'FINISHED'}

classes = (
    OBJEX_OT_material_combiner,
    OBJEX_OT_material_material,
    OBJEX_OT_material_set_shade_source_vertex_colors,
    OBJEX_OT_material_set_shade_source_lighting,
)

def register():
    for clazz in classes:
        blender_version_compatibility.make_annotations(clazz)
        bpy.utils.register_class(clazz)

def unregister():
    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
