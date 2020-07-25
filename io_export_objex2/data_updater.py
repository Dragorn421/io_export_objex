import bpy

from . import interface

# materials

def material_from_0(material, data):
    """
    0 -> 1
    add OBJEX_TransformUV_Main between Geometry and UV pipe nodes
    use_texgen, scaleS and scaleT moved to node sockets in OBJEX_TransformUV_Main node
    """
    use_texgen = data.get('use_texgen', 0) == 1
    scaleS = data.get('scaleS', 1)
    scaleT = data.get('scaleT', 1)
    interface.exec_build_nodes_operator(material)
    uvTransformMain = material.node_tree.nodes['OBJEX_TransformUV_Main']
    uvTransformMain.inputs['Texgen'].default_value = use_texgen
    uvTransformMain.inputs['Texgen Linear'].default_value = use_texgen
    uvTransformMain.inputs['U Scale'].default_value = scaleS
    uvTransformMain.inputs['V Scale'].default_value = scaleT
    data.objex_version = 1

# update_material_function factory for when a material version bump is only due to a node group version bump
def node_groups_internal_change_update_material_function(to_version):
    def update_material_function(material, data):
        interface.exec_build_nodes_operator(material, create=False, set_looks=False, set_basic_links=False)
        data.objex_version = to_version
    return update_material_function

"""
- versions are integers in ascending order
- addon_material_objex_version is the current version
- version should be bumped when properties, node setup or node groups change
- an update function makes material go from version a to any version b
  (a < b <= addon_material_objex_version), and sets objex_version accordingly
- update functions expect (material, material.objex_bonus) as arguments
  with material using the intended version
- node groups as created by update_node_groups are expected to be up-to-date
  (material nodes can still be using _old-like groups)
"""
update_material_functions = {
    0: material_from_0,
    1: node_groups_internal_change_update_material_function(2), # OBJEX_UV_pipe 1 -> 2
}
addon_material_objex_version = 2

# called by OBJEX_PT_material#draw
def handle_material(material, layout):
    data = material.objex_bonus
    v = data.objex_version
    if v == addon_material_objex_version:
        return False
    if v > addon_material_objex_version:
        layout.label('This material was created', icon='ERROR')
        layout.label('with a newer addon version,')
        layout.label('you should update the addon')
        layout.label('used in your installation.')
    if v < addon_material_objex_version:
        layout.label('This material was created', icon='INFO')
        layout.label('with an older addon version,')
        layout.label('and needs to be updated.')
        layout.operator('objex.material_update', text='Update this material')
        layout.operator('objex.material_update', text='Update ALL objex materials').update_all = True
    return True

def assert_material_at_current_version(material, errorClass):
    data = material.objex_bonus
    v = data.objex_version
    if v > addon_material_objex_version:
        raise errorClass(
            'The material %s was created with a newer addon version, '
            'you should update the addon used in your installation.' % material.name)
    if v < addon_material_objex_version:
        raise errorClass(
            'The material %s was created with an older addon version, '
            'and needs to be updated. Update/Update all buttons '
            'can be found in the material tab.' % material.name)
    # v == addon_material_objex_version

class OBJEX_OT_material_update(bpy.types.Operator):

    bl_idname = 'objex.material_update'
    bl_label = 'Update an Objex material'
    bl_options = {'INTERNAL', 'PRESET', 'REGISTER', 'UNDO'}

    update_all = bpy.props.BoolProperty()

    def execute(self, context):
        if self.update_all:
            materials = (
                m for m in bpy.data.materials
                if m.objex_bonus.is_objex_material
                    and m.objex_bonus.objex_version != addon_material_objex_version
            )
        else:
            materials = (context.material,)
        interface.update_node_groups()
        failures = 0
        material_count = 0
        for material in materials:
            material_count += 1
            data = material.objex_bonus
            if data.objex_version > addon_material_objex_version:
                self.report({'WARNING'}, 'Skipped material %s which uses a newer version' % material.name)
                failures += 1
                continue
            while data.objex_version < addon_material_objex_version:
                update_func = update_material_functions.get(data.objex_version)
                if not update_func:
                    self.report({'ERROR'}, 'Skipping material %s which uses unknown version %d' % (material.name, data.objex_version))
                    failures += 1
                    break
                update_func(material, data)
        if failures:
            self.report({'ERROR'}, 'Failed to update %d of %d materials' % (failures, material_count))
        else:
            self.report({'INFO'}, 'Successfully updated %d materials' % material_count)
        return {'FINISHED'}

classes = (
    OBJEX_OT_material_update,
)

def register():
    for clazz in classes:
        bpy.utils.register_class(clazz)

def unregister():
    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
