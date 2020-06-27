# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8-80 compliant>

"""
Based on the io_scene_obj addon shipped with Blender 2.79b
Removed import feature
By default: triangulate, no edges, and other default values changed
Removed use_animation 'Write out an OBJ for each frame'
Added vertex colors support
WIP interface
Added writing skeletons and animations
Added writing weights, and option to only write maximum weight for each vertex
Refactor, cut the giant write-obj function into a few pieces into the ObjexWriter class, hopefully made the code more readable
"""

"""
TODO:
write_mtl for writing the .mtl is still the untouched obj version
interface: but designing is required first
writing animations flow from write_anim to write_skel, should be the opposite
write_anim sucks
ctrl+f "421todo" for less important details
"""

bl_info = {
    'name': 'Objex Exporter for N64 romhacking',
    'author': 'Campbell Barton, Bastien Montagne, OoT modding community',
    'version': (1, 0, 0),
    'blender': (2, 79, 0),
    'location': 'File > Export',
    'description': 'Allows to export to objex and provides new features for further customization',
    'warning': '',
    'wiki_url': 'TODO manual',
    'support': 'COMMUNITY',
    'category': 'Import-Export'}

if 'bpy' in locals():
	import importlib
	if 'export_objex' in locals():
		importlib.reload(export_objex)
	if 'interface' in locals():
		importlib.reload(interface)


import bpy
from bpy.props import (
        BoolProperty,
        FloatProperty,
        StringProperty,
        EnumProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        orientation_helper_factory,
        path_reference_mode,
        axis_conversion,
        )

from . import export_objex
from . import interface

IOOBJOrientationHelper = orientation_helper_factory('IOOBJOrientationHelper', axis_forward='-Z', axis_up='Y')


class OBJEX_OT_export(bpy.types.Operator, ExportHelper, IOOBJOrientationHelper):
    """Save an OBJEX File"""

    bl_idname = 'objex.export'
    bl_label = 'Export OBJEX'
    bl_options = {'PRESET'}

    filename_ext = '.objex'
    filter_glob = StringProperty(
            default='*.objex;*.mtl',
            options={'HIDDEN'},
            )

    # context group
    use_selection = BoolProperty(
            name='Selection Only',
            description='Export selected objects only',
            default=False,
            )

    # object group
    use_mesh_modifiers = BoolProperty(
            name='Apply Modifiers',
            description='Apply modifiers',
            default=True,
            )
    use_mesh_modifiers_render = BoolProperty(
            name='Use Modifiers Render Settings',
            description='Use render settings when applying modifiers to mesh objects',
            default=False,
            )

    # extra data group
    use_edges = BoolProperty(
            name='Include Edges',
            description='',
            default=False,
            )
    use_smooth_groups = BoolProperty(
            name='Smooth Groups',
            description='Write sharp edges as smooth groups',
            default=False,
            )
    use_smooth_groups_bitflags = BoolProperty(
            name='Bitflag Smooth Groups',
            description='Same as Smooth Groups, but generate smooth groups IDs as bitflags '
                        '(produces at most 32 different smooth groups, usually much less)',
            default=False,
            )
    use_normals = BoolProperty(
            name='Write Normals',
            description='Export one normal per vertex and per face, to represent flat faces and sharp edges',
            default=True,
            )
    use_vertex_colors = BoolProperty(
            name='Write Vertex Colors',
            description='Export one color per vertex and per face',
            default=True,
            )
    use_uvs = BoolProperty(
            name='Include UVs',
            description='Write out the active UV coordinates',
            default=True,
            )
    use_materials = BoolProperty(
            name='Write Materials',
            description='Write out the MTL file',
            default=True,
            )
    use_skeletons = BoolProperty(
            name='Write Skeletons',
            description='Write out the SKEL file',
            default=True,
            )
    use_animations = BoolProperty(
            name='Write Animations',
            description='Write out the ANIM file',
            default=True,
            )
    use_weights = BoolProperty(
            name='Write Weights',
            description='Write out the vertex weights',
            default=True,
            )
    use_unique_weights = BoolProperty(
            name='Only write one weight per vertex',
            description='Use vertex group with maximum weight, with weight 1.0',
            default=False, # 421todo True by default? for OoT maybe
            )
    use_triangles = BoolProperty(
            name='Triangulate Faces',
            description='Convert all faces to triangles',
            default=True,
            )
    use_nurbs = BoolProperty(
            name='Write Nurbs',
            description='Write nurbs curves as OBJ nurbs rather than '
                        'converting to geometry',
            default=False,
            )
    use_vertex_groups = BoolProperty(
            name='Polygroups',
            description='',
            default=False,
            )

    # grouping group
    use_blen_objects = BoolProperty(
            name='Objects as OBJ Objects',
            description='',
            default=True,
            )
    group_by_object = BoolProperty(
            name='Objects as OBJ Groups ',
            description='',
            default=False,
            )
    group_by_material = BoolProperty(
            name='Material Groups',
            description='',
            default=False,
            )
    keep_vertex_order = BoolProperty(
            name='Keep Vertex Order',
            description='',
            default=False,
            )

    global_scale = FloatProperty(
            name='Scale',
            min=0.01, max=1000.0, # 421todo use softmin/max not hard
            default=1.0,
            )

    path_mode = path_reference_mode

    check_extension = True

    def execute(self, context):
        from mathutils import Matrix
        keywords = self.as_keywords(ignore=('axis_forward',
                                            'axis_up',
                                            'global_scale',
                                            'check_existing',
                                            'filter_glob',
                                            ))

        global_matrix = (Matrix.Scale(self.global_scale, 4) *
                         axis_conversion(to_forward=self.axis_forward,
                                         to_up=self.axis_up,
                                         ).to_4x4())
        
        keywords['global_matrix'] = global_matrix
        return export_objex.save(context, **keywords)


def menu_func_export(self, context):
    self.layout.operator(OBJEX_OT_export.bl_idname, text='Extended OBJ (new WIP) (.objex)')


classes = (
    OBJEX_OT_export,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.INFO_MT_file_export.append(menu_func_export)
    
    interface.register_interface()
    print('objex init register ok')


def unregister():
    interface.unregister_interface()
    
    bpy.types.INFO_MT_file_export.remove(menu_func_export)

    for cls in classes:
        bpy.utils.unregister_class(cls)


if __name__ == '__main__':
    register()
