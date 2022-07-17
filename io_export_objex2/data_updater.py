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

from cgitb import text
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

def nodes_from_5(material, data, log):
    # fix node names
    interface.exec_build_nodes_operator(material,
        init=False, reset=False, create=False,
        update_groups_of_existing=False,
        set_looks=False, set_basic_links=False
    )
    # save links to cycles
    tree = material.node_tree
    nodes = tree.nodes
    cycle_node_names = ('OBJEX_ColorCycle0','OBJEX_ColorCycle1','OBJEX_AlphaCycle0','OBJEX_AlphaCycle1',)
    links = {}
    for cycle_node_name in cycle_node_names:
        cycle_node = nodes.get(cycle_node_name)
        if not cycle_node:
            log.warn('Cycle node {} does not exist, skipping', cycle_node_name)
            continue
        if len(cycle_node.inputs) < 4:
            log.warn('Cycle node {} has only {} inputs (< 4), skipping', cycle_node_name, len(cycle_node.inputs))
            continue
        if len(cycle_node.outputs) == 0:
            log.warn('Cycle node {} has 0 outputs, skipping', cycle_node_name)
            continue
        if len(cycle_node.inputs) > 4:
            log.warn('Cycle node {} has {} inputs (> 4), only using first 4', cycle_node_name, len(cycle_node.inputs))
        if len(cycle_node.outputs) > 1:
            log.warn('Cycle node {} has {} outputs (> 1), only using the first one', cycle_node_name, len(cycle_node.outputs))
        # links between input sockets and other nodes
        inputs_links = {}
        for i in range(4):
            inputs_links[i] = tuple(
                link.from_socket for link in cycle_node.inputs[i].links
                    if link.from_socket.node.name not in cycle_node_names)
        # links between output sockets and other nodes
        outputs_links = {
            0: tuple(link.to_socket for link in cycle_node.outputs[0].links
                        if link.to_socket.node.name not in cycle_node_names)
        }
        # links between cycle nodes
        # only check cycle_node.outputs as cycle_node.inputs (of other nodes) would only have duplicate links
        links_to_cycles_from_output = []
        for link in cycle_node.outputs[0].links:
            to_node_name = link.to_socket.node.name
            if to_node_name not in cycle_node_names:
                continue
            to_socket_index = link.to_socket.node.inputs.find(link.to_socket.name)
            if to_socket_index >= 4:
                log.warn('Skipping link between cycle node {} output and {} input {} because index of the input is {} (>= 4)', cycle_node_name, to_node_name, link.to_socket.name, to_socket_index)
                continue
            links_to_cycles_from_output.append((to_node_name, to_socket_index))
        links[cycle_node_name] = {'in':inputs_links, 'out':outputs_links, 'out-cycles':{0:links_to_cycles_from_output}}
    log.debug('links =\n{!r}', links)
    # recreate cycle nodes
    for node_name, _ in links.items():
        nodes.remove(nodes[node_name])
    interface.exec_build_nodes_operator(material,
        init=False, reset=False, create=True,
        update_groups_of_existing=False,
        set_looks=False, set_basic_links=False
    )
    # restore links
    for node_name, node_links in links.items():
        node = nodes[node_name]
        for input_socket_key, input_socket_links_from in node_links['in'].items():
            to_socket = node.inputs[input_socket_key]
            for from_socket in input_socket_links_from:
                tree.links.new(from_socket, to_socket)
        for output_socket_key, output_socket_links_to in node_links['out'].items():
            from_socket = node.outputs[output_socket_key]
            for to_socket in output_socket_links_to:
                tree.links.new(from_socket, to_socket)
        for output_socket_key, output_socket_links_to_cycle_node in node_links['out-cycles'].items():
            from_socket = node.outputs[output_socket_key]
            for to_node_name, to_socket_key in output_socket_links_to_cycle_node:
                to_socket = nodes[to_node_name].inputs[to_socket_key]
                tree.links.new(from_socket, to_socket)
    # done
    data.objex_version = 6

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
    5: nodes_from_5, # custom cycle input sockets in 2.8x
    6: node_setup_simple_change_update_material_function(7), # add OBJEX_PrimLodFrac
    7: node_groups_internal_change_update_material_function(8)
}
addon_material_objex_version = 8

# called by OBJEX_PT_material#draw
def handle_material(material, layout):
    data = material.objex_bonus
    v = data.objex_version
    if v == addon_material_objex_version:
        return False
    if v > addon_material_objex_version:
        box = layout.box()
        box.label(text='', icon='ERROR')
        box.label(text='This material was created')
        box.label(text='with a newer addon version,')
        box.label(text='you should update the addon')
        box.label(text='used in your installation.')
    if v < addon_material_objex_version:
        box = layout.box()
        box.label(text='', icon='INFO')
        box.label(text='This material was created')
        box.label(text='with an older addon version,')
        box.label(text='and needs to be updated.')
        box.operator('objex.material_update', text='Update this material').update_all = False
        box.operator('objex.material_update', text='Update ALL objex materials').update_all = True
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
                    if m.objex_bonus.is_objex_material and m.objex_bonus.use_display
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
