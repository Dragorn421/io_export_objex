from . import blender_version_compatibility

import bpy

from . import interface
from . import logging_util

# materials

def material_from_0(material, data, log):
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

def material_from_2(material, data, log):
    """
    2 -> 3
    recreate OBJEX_TransformUV0, OBJEX_TransformUV1 nodes
    """
    nodes = material.node_tree.nodes
    names = ('OBJEX_TransformUV0', 'OBJEX_TransformUV1',)
    copy_inputs = ('U Scale Exponent','V Scale Exponent','Wrap U','Wrap V','Mirror U','Mirror V',)
    socket_data = dict()
    for name in names:
        if name not in nodes:
            log.warn('Could not find node {}, skipping node', name)
            continue
        node = nodes[name]
        socket_data[name] = input_values = dict()
        for input_socket_name in copy_inputs:
            if input_socket_name not in node.inputs:
                log.warn('Could not find "{}" on {}, skipping socket', input_socket_name, name)
                continue
            input_values[input_socket_name] = node.inputs[input_socket_name].default_value
        nodes.remove(node)
    interface.exec_build_nodes_operator(material)
    for name, input_values in socket_data.items():
        node = nodes[name]
        for input_socket_name, default_value in input_values.items():
            node.inputs[input_socket_name].default_value = default_value
    data.objex_version = 3

# update_material_function factory for when a material version bump is only due to a node group version bump
# if socket inputs/outputs change something like material_from_2 would be more appropriate, this is only for purely group-internal changes
def node_groups_internal_change_update_material_function(to_version):
    def update_material_function(material, data, log):
        interface.exec_build_nodes_operator(material, create=False, set_looks=False, set_basic_links=False)
        data.objex_version = to_version
    return update_material_function

# same as node_groups_internal_change_update_material_function but create nodes
def node_setup_simple_change_update_material_function(to_version):
    def update_material_function(material, data, log):
        interface.exec_build_nodes_operator(material, create=True, set_looks=False, set_basic_links=False)
        data.objex_version = to_version
    return update_material_function

"""
- versions are integers in ascending order
- addon_material_objex_version is the current version
- version should be bumped when properties, node setup or node groups change
- an update function makes material go from version a to any version b
  (a < b <= addon_material_objex_version), and sets objex_version accordingly
- update functions expect (material, material.objex_bonus, log) as arguments
  with material using the intended version
  and log being a logger object such as logging_util.getLogger('')
- node groups as created by update_node_groups are expected to be up-to-date
  (material nodes can still be using _old-like groups)
"""
update_material_functions = {
    0: material_from_0,
    1: node_groups_internal_change_update_material_function(2), # OBJEX_UV_pipe 1 -> 2
    2: material_from_2,
    3: node_setup_simple_change_update_material_function(5), # add Vertex Color node to tree (2.80+)
    4: node_setup_simple_change_update_material_function(5), # fix version 4's update_material_function using create=False
}
addon_material_objex_version = 5

# called by OBJEX_PT_material#draw
def handle_material(material, layout):
    data = material.objex_bonus
    v = data.objex_version
    if v == addon_material_objex_version:
        return False
    if v > addon_material_objex_version:
        layout.label(text='This material was created', icon='ERROR')
        layout.label(text='with a newer addon version,')
        layout.label(text='you should update the addon')
        layout.label(text='used in your installation.')
    if v < addon_material_objex_version:
        layout.label(text='This material was created', icon='INFO')
        layout.label(text='with an older addon version,')
        layout.label(text='and needs to be updated.')
        layout.operator('objex.material_update', text='Update this material').update_all = False
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
        log = logging_util.getLogger(self.bl_idname)
        logging_util.setLogOperator(self, user_friendly_formatter=True)
        try:
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
                    log.warn('Skipped material {} which uses a newer version', material.name)
                    failures += 1
                    continue
                while data.objex_version < addon_material_objex_version:
                    update_func = update_material_functions.get(data.objex_version)
                    if not update_func:
                        log.error('Skipping material {} which uses unknown version {}', material.name, data.objex_version)
                        failures += 1
                        break
                    update_func(material, data, log)
            if failures:
                log.error('Failed to update {} of {} materials', failures, material_count)
            else:
                log.info('Successfully updated {} materials', material_count)
            return {'FINISHED'}
        finally:
            logging_util.setLogOperator(None)

classes = (
    OBJEX_OT_material_update,
)

def register():
    for clazz in classes:
        blender_version_compatibility.make_annotations(clazz)
        bpy.utils.register_class(clazz)

def unregister():
    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
