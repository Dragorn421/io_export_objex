import bpy

from . import blender_version_compatibility

def clearLinks(tree, socket):
    while socket.links:
        tree.links.remove(socket.links[0])

def setLinks_multiply_by(tree, colorSocket, alphaSocket, multiply_by):
    if multiply_by == 'LIGHTING':
        if bpy.app.version < (2, 80, 0):
            colorSocket.input_flags_C_C = 'G_CCMUX_SHADE'
            alphaSocket.input_flags_A_C = 'G_ACMUX_SHADE'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_Shade'].outputs['Color'], colorSocket)
            tree.links.new(tree.nodes['OBJEX_Shade'].outputs['Alpha'], alphaSocket)
        tree.links.new(tree.nodes['OBJEX_Color1'].outputs[0], tree.nodes['OBJEX_Shade'].inputs['Color'])
        tree.links.new(tree.nodes['OBJEX_Color1'].outputs[0], tree.nodes['OBJEX_Shade'].inputs['Alpha'])
    elif multiply_by == 'VERTEX_COLORS':
        if bpy.app.version < (2, 80, 0):
            colorSocket.input_flags_C_C = 'G_CCMUX_SHADE'
            alphaSocket.input_flags_A_C = 'G_ACMUX_SHADE'
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
            colorSocket.input_flags_C_C = 'G_CCMUX_ENVIRONMENT'
            alphaSocket.input_flags_A_C = 'G_ACMUX_ENVIRONMENT'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_EnvColor'].outputs['Color'], colorSocket)
            tree.links.new(tree.nodes['OBJEX_EnvColor'].outputs['Alpha'], alphaSocket)
    elif multiply_by == 'PRIM_COLOR':
        if bpy.app.version < (2, 80, 0):
            colorSocket.input_flags_C_C = 'G_CCMUX_PRIMITIVE'
            alphaSocket.input_flags_A_C = 'G_ACMUX_PRIMITIVE'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_PrimColor'].outputs['Color'], colorSocket)
            tree.links.new(tree.nodes['OBJEX_PrimColor'].outputs['Alpha'], alphaSocket)

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
        return material and material.objex_bonus.is_objex_material

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
        return material and material.objex_bonus.is_objex_material

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
            cc0.inputs['A'].input_flags_C_A = 'G_CCMUX_TEXEL0'
            cc0.inputs['B'].input_flags_C_B = 'G_CCMUX_TEXEL1'
            cc0.inputs['D'].input_flags_C_D = 'G_CCMUX_TEXEL1'
            #cc1.inputs['A'].input_flags_C_A = 'G_CCMUX_COMBINED'
            tree.links.new(cc0.outputs[0], cc1.inputs['A'])
            cc1.inputs['B'].input_flags_C_B = 'G_CCMUX_0'
            cc1.inputs['D'].input_flags_C_D = 'G_CCMUX_0'
        else: # 2.80+
            tree.links.new(tree.nodes['OBJEX_Texel0'].outputs['Color'], cc0.inputs['A'])
            tree.links.new(tree.nodes['OBJEX_Texel1'].outputs['Color'], cc0.inputs['B'])
            tree.links.new(tree.nodes['OBJEX_Texel1'].outputs['Color'], cc0.inputs['D'])
            tree.links.new(cc0.outputs[0], cc1.inputs['A'])
            clearLinks(tree, cc1.inputs['B'])
            clearLinks(tree, cc1.inputs['D'])
        # alpha cycles
        if bpy.app.version < (2, 80, 0):
            ac0.inputs['A'].input_flags_A_A = 'G_ACMUX_TEXEL0'
            ac0.inputs['B'].input_flags_A_B = 'G_ACMUX_TEXEL1'
            ac0.inputs['D'].input_flags_A_D = 'G_ACMUX_TEXEL1'
            #ac1.inputs['A'].input_flags_A_A = 'G_ACMUX_COMBINED'
            tree.links.new(ac0.outputs[0], ac1.inputs['A'])
            ac1.inputs['B'].input_flags_A_B = 'G_ACMUX_0'
            ac1.inputs['D'].input_flags_A_D = 'G_ACMUX_0'
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
                cc0.inputs['C'].input_flags_C_C = 'G_CCMUX_ENV_ALPHA'
                ac0.inputs['C'].input_flags_A_C = 'G_ACMUX_ENVIRONMENT'
            else: # 2.80+
                tree.links.new(tree.nodes['OBJEX_EnvColor'].outputs['Alpha'], cc0.inputs['C'])
                tree.links.new(tree.nodes['OBJEX_EnvColor'].outputs['Alpha'], ac0.inputs['C'])
        else: # PRIM
            tree.nodes['OBJEX_PrimColor'].inputs['Alpha'].default_value = self.alpha
            if bpy.app.version < (2, 80, 0):
                cc0.inputs['C'].input_flags_C_C = 'G_CCMUX_PRIMITIVE_ALPHA'
                ac0.inputs['C'].input_flags_A_C = 'G_ACMUX_PRIMITIVE'
            else: # 2.80+
                tree.links.new(tree.nodes['OBJEX_PrimColor'].outputs['Alpha'], cc0.inputs['C'])
                tree.links.new(tree.nodes['OBJEX_PrimColor'].outputs['Alpha'], ac0.inputs['C'])
        # set C of second color/alpha cycle according to self.multiply_by
        setLinks_multiply_by(tree, cc1.inputs['C'], ac1.inputs['C'], self.multiply_by)
        return {'FINISHED'}

classes = (
    OBJEX_OT_material_single_texture,
    OBJEX_OT_material_multitexture,
)

def register():
    for clazz in classes:
        blender_version_compatibility.make_annotations(clazz)
        bpy.utils.register_class(clazz)

def unregister():
    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
