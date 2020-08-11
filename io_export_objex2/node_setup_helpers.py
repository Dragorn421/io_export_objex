import bpy

from . import blender_version_compatibility

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
    OBJEX_OT_material_multitexture,
)

def register():
    for clazz in classes:
        blender_version_compatibility.make_annotations(clazz)
        bpy.utils.register_class(clazz)

def unregister():
    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
