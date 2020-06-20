import bpy
import re

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

class ObjexArmatureProperties(bpy.types.PropertyGroup):
    parent_object = bpy.props.PointerProperty(
            type=bpy.types.Object,
            name='Parent Object',
            description=''
        )
    parent_bone = bpy.props.StringProperty(
            name='Parent Bone',
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
    segment = bpy.props.StringProperty(
            name='Segment',
            description=''
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
        self.layout.label(text='Hello World')
        armature = context.armature
        data = armature.objex_bonus
        self.layout.prop(data, 'parent_object')
        if data.parent_object and data.parent_object.type == 'ARMATURE':
            self.layout.prop_search(data, 'parent_bone', data.parent_object.data, 'bones', text='Parent Bone', icon=('NONE' if data.parent_bone in armature.bones else 'ERROR'))
        self.layout.prop(data, 'type')
        self.layout.prop(data, 'segment', icon=('NONE' if re.match(r'^(?:0x)?[0-9a-fA-F]+$', data.segment) else 'ERROR'))
        self.layout.label(text='end!')

# material

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
    
    def draw(self, context):
        self.layout.label(text='Hello World')
        material = context.material
        data = material.objex_bonus
        self.layout.prop(data, 'my_int')
        self.layout.prop(data, 'my_color')
        self.layout.label(text='HELLLLLLLOOOOO')

def register_interface():
    bpy.utils.register_class(ObjexArmatureProperties)
    bpy.types.Armature.objex_bonus = bpy.props.PointerProperty(type=ObjexArmatureProperties)
    bpy.utils.register_class(OBJEX_PT_armature)
    bpy.utils.register_class(ObjexMaterialProperties)
    bpy.types.Material.objex_bonus = bpy.props.PointerProperty(type=ObjexMaterialProperties)
    bpy.utils.register_class(OBJEX_PT_material)

def unregister_interface():
    bpy.utils.unregister_class(OBJEX_PT_armature)
    del bpy.types.Armature.objex_bonus
    bpy.utils.unregister_class(ObjexArmatureProperties)
    bpy.utils.unregister_class(OBJEX_PT_material)
    del bpy.types.Material.objex_bonus
    bpy.utils.unregister_class(ObjexMaterialProperties)
