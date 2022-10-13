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

class OBJEX_OT_material_single_texture(bpy.types.Operator):

    bl_idname = 'objex.material_single_texture'
    bl_label = 'Configures nodes of an objex material for a single texture'
    bl_options = {'REGISTER', 'UNDO'}

    # Cannot use PointerProperty in operators unfortunately...
    texel = bpy.props.StringProperty(
            name='Image',
            description='The image to use'
        )
    multiply_by0 = bpy.props.EnumProperty(
            items=[
                ('LIGHTING','Lighting','Use shading from lighting',1),
                ('VERTEX_COLORS','Vertex Colors','Use shading from vertex colors',2),
                ('ENV_COLOR','Environment Color','Use environment color',3),
                ('PRIM_COLOR','Primitive Color','Use primitive color',4),
            ],
            name='With',
            description='What to combine (multiply) the texture with.',
            default='PRIM_COLOR'
        )
    multiply_by1 = bpy.props.EnumProperty(
            items=[
                ('LIGHTING','Lighting','Use shading from lighting',1),
                ('VERTEX_COLORS','Vertex Colors','Use shading from vertex colors',2),
                ('ENV_COLOR','Environment Color','Use environment color',3),
                ('PRIM_COLOR','Primitive Color','Use primitive color',4),
            ],
            name='With',
            description='What to combine (multiply) the texture with.',
            default='LIGHTING'
        )

    def draw(self, context):
        layout = self.layout
        layout.operator('image.open')
        layout.prop_search(self, 'texel', bpy.data, 'images')
        layout.prop(self, 'multiply_by0')
        layout.prop(self, 'multiply_by1')
        if set((self.multiply_by0, self.multiply_by1,)) == set(('LIGHTING', 'VERTEX_COLORS',)):
            layout.label(text='Lighting and Vertex Colors', icon='ERROR')
            layout.label(text='cannot be used together', icon='ERROR')

    @classmethod
    def poll(self, context):
        material = context.material if hasattr(context, 'material') else None
        return material and material.objex_bonus.is_objex_material and material.objex_bonus.use_display

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        material = context.material
        tree = material.node_tree
        if not self.texel or self.texel not in bpy.data.images:
            self.report({'WARNING'}, 'No image set')
            return {'CANCELLED'}
        if set((self.multiply_by0, self.multiply_by1,)) == set(('LIGHTING', 'VERTEX_COLORS',)):
            self.report({'WARNING'}, 'Lighting and Vertex Colors cannot be used together')
            return {'CANCELLED'}
        textureNode = tree.nodes['OBJEX_Texel0Texture']
        if textureNode.bl_idname == 'ShaderNodeTexture': # < 2.80
            texture = bpy.data.textures.new(self.texel, 'IMAGE')
            texture.image = bpy.data.images[self.texel]
            textureNode.texture = texture
        else: # 2.80+ assume ShaderNodeTexImage
            textureNode.image = bpy.data.images[self.texel]
        cc0 = tree.nodes['OBJEX_ColorCycle0']
        cc1 = tree.nodes['OBJEX_ColorCycle1']
        ac0 = tree.nodes['OBJEX_AlphaCycle0']
        ac1 = tree.nodes['OBJEX_AlphaCycle1']
        # color cycles
        tree.links.new(tree.nodes['OBJEX_Texel0'].outputs['Color'], cc0.inputs['A'])
        clearLinks(tree, cc0.inputs['B'])
        clearLinks(tree, cc0.inputs['D'])
        tree.links.new(cc0.outputs[0], cc1.inputs['A'])
        clearLinks(tree, cc1.inputs['B'])
        clearLinks(tree, cc1.inputs['D'])
        # alpha cycles
        tree.links.new(tree.nodes['OBJEX_Texel0'].outputs['Alpha'], ac0.inputs['A'])
        clearLinks(tree, ac0.inputs['B'])
        clearLinks(tree, ac0.inputs['D'])
        tree.links.new(ac0.outputs[0], ac1.inputs['A'])
        clearLinks(tree, ac1.inputs['B'])
        clearLinks(tree, ac1.inputs['D'])
        # set C of first color/alpha cycle
        setLinks_multiply_by(tree, cc0.inputs['C'], ac0.inputs['C'], self.multiply_by0)
        # set C of second color/alpha cycle according to self.multiply_by
        setLinks_multiply_by(tree, cc1.inputs['C'], ac1.inputs['C'], self.multiply_by1)
        interface.exec_build_nodes_operator(material)
        return {'FINISHED'}

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
    alpha_source = bpy.props.EnumProperty(
            items=[
                ('ENV','Environment Color','Store factor in environment color',1),
                ('PRIM','Primitive Color','Store factor in primitive color',2),
            ],
            name='Factor source',
            description='In what color register to store the blend factor.',
            default='ENV'
        )
    multiply_by = bpy.props.EnumProperty(
            items=[
                ('LIGHTING','Lighting','Use shading from lighting',1),
                ('VERTEX_COLORS','Vertex Colors','Use shading from vertex colors',2),
                ('ENV_COLOR','Environment Color','Use environment color',3),
                ('PRIM_COLOR','Primitive Color','Use primitive color',4),
            ],
            name='With',
            description='What to combine (multiply) the multitextured result with.',
            default='LIGHTING'
        )

    def draw(self, context):
        layout = self.layout
        layout.operator('image.open')
        layout.prop_search(self, 'texel0', bpy.data, 'images')
        layout.prop_search(self, 'texel1', bpy.data, 'images')
        layout.prop(self, 'alpha')
        layout.prop(self, 'alpha_source')
        layout.prop(self, 'multiply_by')

    @classmethod
    def poll(self, context):
        material = context.material if hasattr(context, 'material') else None
        return material and material.objex_bonus.is_objex_material and material.objex_bonus.use_display

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        material = context.material
        tree = material.node_tree
        for texel, n in ((self.texel0,'0'),(self.texel1,'1')):
            if not texel or texel not in bpy.data.images:
                return {'CANCELLED'}
            textureNode = tree.nodes['OBJEX_Texel%sTexture' % n]
            if textureNode.bl_idname == 'ShaderNodeTexture': # < 2.80
                texture = bpy.data.textures.new(texel, 'IMAGE')
                texture.image = bpy.data.images[texel]
                textureNode.texture = texture
            else: # 2.80+ assume ShaderNodeTexImage
                textureNode.image = bpy.data.images[texel]
        cc0 = tree.nodes['OBJEX_ColorCycle0']
        cc1 = tree.nodes['OBJEX_ColorCycle1']
        ac0 = tree.nodes['OBJEX_AlphaCycle0']
        ac1 = tree.nodes['OBJEX_AlphaCycle1']
        # color cycles
        if bpy.app.version < (2, 80, 0):
            cc0.inputs['A'].input_flags_C_A_0 = 'G_CCMUX_TEXEL0'
            cc0.inputs['B'].input_flags_C_B_0 = 'G_CCMUX_TEXEL1'
            cc0.inputs['D'].input_flags_C_D_0 = 'G_CCMUX_TEXEL1'
            #cc1.inputs['A'].input_flags_C_A_1 = 'G_CCMUX_COMBINED'
            tree.links.new(cc0.outputs[0], cc1.inputs['A'])
            cc1.inputs['B'].input_flags_C_B_1 = 'G_CCMUX_0'
            cc1.inputs['D'].input_flags_C_D_1 = 'G_CCMUX_0'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_Texel0'].outputs['Color'], cc0.inputs['A'])
            tree.links.new(tree.nodes['OBJEX_Texel1'].outputs['Color'], cc0.inputs['B'])
            tree.links.new(tree.nodes['OBJEX_Texel1'].outputs['Color'], cc0.inputs['D'])
            tree.links.new(cc0.outputs[0], cc1.inputs['A'])
            clearLinks(tree, cc1.inputs['B'])
            clearLinks(tree, cc1.inputs['D'])
        # alpha cycles
        if bpy.app.version < (2, 80, 0):
            ac0.inputs['A'].input_flags_A_A_0 = 'G_ACMUX_TEXEL0'
            ac0.inputs['B'].input_flags_A_B_0 = 'G_ACMUX_TEXEL1'
            ac0.inputs['D'].input_flags_A_D_0 = 'G_ACMUX_TEXEL1'
            #ac1.inputs['A'].input_flags_A_A_1 = 'G_ACMUX_COMBINED'
            tree.links.new(ac0.outputs[0], ac1.inputs['A'])
            ac1.inputs['B'].input_flags_A_B_1 = 'G_ACMUX_0'
            ac1.inputs['D'].input_flags_A_D_1 = 'G_ACMUX_0'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_Texel0'].outputs['Alpha'], ac0.inputs['A'])
            tree.links.new(tree.nodes['OBJEX_Texel1'].outputs['Alpha'], ac0.inputs['B'])
            tree.links.new(tree.nodes['OBJEX_Texel1'].outputs['Alpha'], ac0.inputs['D'])
            tree.links.new(ac0.outputs[0], ac1.inputs['A'])
            clearLinks(tree, ac1.inputs['B'])
            clearLinks(tree, ac1.inputs['D'])
        # set C of first color/alpha cycle according to self.alpha_source
        if self.alpha_source == 'ENV':
            tree.nodes['OBJEX_EnvColor'].inputs['Alpha'].default_value = self.alpha
            if bpy.app.version < (2, 80, 0):
                cc0.inputs['C'].input_flags_C_C_0 = 'G_CCMUX_ENV_ALPHA'
                ac0.inputs['C'].input_flags_A_C_0 = 'G_ACMUX_ENVIRONMENT'
            else: # 2.80+
                tree.links.new(tree.nodes['OBJEX_EnvColor'].outputs['Alpha'], cc0.inputs['C'])
                tree.links.new(tree.nodes['OBJEX_EnvColor'].outputs['Alpha'], ac0.inputs['C'])
        else: # PRIM
            tree.nodes['OBJEX_PrimColor'].inputs['Alpha'].default_value = self.alpha
            if bpy.app.version < (2, 80, 0):
                cc0.inputs['C'].input_flags_C_C_0 = 'G_CCMUX_PRIMITIVE_ALPHA'
                ac0.inputs['C'].input_flags_A_C_0 = 'G_ACMUX_PRIMITIVE'
            else: # 2.80+
                tree.links.new(tree.nodes['OBJEX_PrimColor'].outputs['Alpha'], cc0.inputs['C'])
                tree.links.new(tree.nodes['OBJEX_PrimColor'].outputs['Alpha'], ac0.inputs['C'])
        # set C of second color/alpha cycle according to self.multiply_by
        setLinks_multiply_by(tree, cc1.inputs['C'], ac1.inputs['C'], self.multiply_by)
        interface.exec_build_nodes_operator(material)
        return {'FINISHED'}

class OBJEX_OT_material_flat_color(bpy.types.Operator):

    bl_idname = 'objex.material_flat_color'
    bl_label = 'Use a flat color'
    bl_description = 'Configures nodes of an objex material for using a flat color'
    bl_options = {'REGISTER', 'UNDO'}

    colorRGB = bpy.props.FloatVectorProperty(
            subtype='COLOR',
            name='Color',
            description='The color to use',
            default=(1,1,1)
        )
    colorA = bpy.props.FloatProperty(
            name='Color Alpha',
            description='The color alpha to use',
            min=0, max=1, step=10,
            default=1
        )
    mainColorRegister = bpy.props.EnumProperty(
            items=[
                ('ENV_COLOR','Environment Color','Use environment color',1),
                ('PRIM_COLOR','Primitive Color','Use primitive color',2),
            ],
            name='Register',
            description='Which register to use for the main color.',
            default='PRIM_COLOR'
        )
    multiply_by0 = bpy.props.EnumProperty(
            items=[
                ('LIGHTING','Lighting','Use shading from lighting',1),
                ('VERTEX_COLORS','Vertex Colors','Use shading from vertex colors',2),
                ('ENV_COLOR','Environment Color','Use environment color',3),
                ('PRIM_COLOR','Primitive Color','Use primitive color',4),
                ('NONE','None','',5),
            ],
            name='With',
            description='What to combine (multiply) the color with.',
            default='ENV_COLOR'
        )
    multiply_by1 = bpy.props.EnumProperty(
            items=[
                ('LIGHTING','Lighting','Use shading from lighting',1),
                ('VERTEX_COLORS','Vertex Colors','Use shading from vertex colors',2),
                ('ENV_COLOR','Environment Color','Use environment color',3),
                ('PRIM_COLOR','Primitive Color','Use primitive color',4),
                ('NONE','None','',5),
            ],
            name='With',
            description='What to combine (multiply) the color with.',
            default='LIGHTING'
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'colorRGB')
        layout.prop(self, 'colorA')
        layout.prop(self, 'mainColorRegister')
        layout.prop(self, 'multiply_by0')
        layout.prop(self, 'multiply_by1')
        if set((self.multiply_by0, self.multiply_by1,)) == set(('LIGHTING', 'VERTEX_COLORS',)):
            layout.label(text='Lighting and Vertex Colors', icon='ERROR')
            layout.label(text='cannot be used together', icon='ERROR')

    @classmethod
    def poll(self, context):
        material = context.material if hasattr(context, 'material') else None
        return material and material.objex_bonus.is_objex_material and material.objex_bonus.use_display

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        material = context.material
        tree = material.node_tree
        if set((self.multiply_by0, self.multiply_by1,)) == set(('LIGHTING', 'VERTEX_COLORS',)):
            self.report({'WARNING'}, 'Lighting and Vertex Colors cannot be used together')
            return {'CANCELLED'}
        if self.mainColorRegister == 'PRIM_COLOR':
            mainColorRegisterNode = tree.nodes['OBJEX_PrimColor']
        elif self.mainColorRegister == 'ENV_COLOR':
            mainColorRegisterNode = tree.nodes['OBJEX_EnvColor']
        mainColorRegisterNode.inputs[0].links[0].from_node.outputs[0].default_value = list(self.colorRGB) + [1];
        mainColorRegisterNode.inputs[1].default_value = self.colorA;
        cc0 = tree.nodes['OBJEX_ColorCycle0']
        cc1 = tree.nodes['OBJEX_ColorCycle1']
        ac0 = tree.nodes['OBJEX_AlphaCycle0']
        ac1 = tree.nodes['OBJEX_AlphaCycle1']
        for c in (cc0,cc1,ac0,ac1):
            for variable in ('A','B','C','D'):
                clearLinks(tree, c.inputs[variable])
        # color cycles
        tree.links.new(mainColorRegisterNode.outputs['Color'], cc0.inputs['D' if self.multiply_by0 == 'NONE' else 'A'])
        tree.links.new(cc0.outputs[0], cc1.inputs['D' if self.multiply_by1 == 'NONE' else 'A'])
        # alpha cycles
        tree.links.new(mainColorRegisterNode.outputs['Alpha'], ac0.inputs['D' if self.multiply_by0 == 'NONE' else 'A'])
        tree.links.new(ac0.outputs[0], ac1.inputs['D' if self.multiply_by1 == 'NONE' else 'A'])
        # set C of all cycle
        if self.multiply_by0 != 'NONE':
            setLinks_multiply_by(tree, cc0.inputs['C'], ac0.inputs['C'], self.multiply_by0)
        if self.multiply_by1 != 'NONE':
            setLinks_multiply_by(tree, cc1.inputs['C'], ac1.inputs['C'], self.multiply_by1)
        interface.exec_build_nodes_operator(material)
        return {'FINISHED'}

class OBJEX_OT_material_set_shade_source(bpy.types.Operator):

    bl_idname = 'objex.material_set_shade_source'
    bl_label = 'Set Shade Source'
    bl_description = 'Link the Shade node of objex materials to use vertex colors or lighting'
    bl_options = set()

    def draw(self, context):
        layout = self.layout
        material = context.material if hasattr(context, 'material') else None
        if not material:
            layout.label(text='Apply to all materials')
            layout.label(text='used in selection')
        layout.operator('objex.material_set_shade_source_vertex_colors')
        layout.operator('objex.material_set_shade_source_lighting')

    @classmethod
    def poll(self, context):
        material = context.material if hasattr(context, 'material') else None
        return material and material.objex_bonus.is_objex_material and material.objex_bonus.use_display

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
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
    OBJEX_OT_material_single_texture,
    OBJEX_OT_material_multitexture,
    OBJEX_OT_material_flat_color,
    OBJEX_OT_material_set_shade_source,
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
