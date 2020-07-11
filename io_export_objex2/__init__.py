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
Removed edge, nurb and "by material" exports
Removed a lot from write_mtl
"""

"""
TODO:
write_mtl is very bare bones
interface: but designing is required first
writing animations flow from write_anim to write_skel, should be the opposite
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


import bpy
from bpy.props import (
        BoolProperty,
        IntProperty,
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

import os
import progress_report

from . import export_objex
from . import interface
from . import logging_util

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
            default=export_objex.ObjexWriter.default_options['APPLY_MODIFIERS'],
            )
    use_mesh_modifiers_render = BoolProperty(
            name='Use Modifiers Render Settings',
            description='Use render settings when applying modifiers to mesh objects',
            default=export_objex.ObjexWriter.default_options['APPLY_MODIFIERS_RENDER'],
            )

    # extra data group
    use_smooth_groups = BoolProperty(
            name='Smooth Groups',
            description='Write sharp edges as smooth groups',
            default=export_objex.ObjexWriter.default_options['EXPORT_SMOOTH_GROUPS'],
            )
    use_smooth_groups_bitflags = BoolProperty(
            name='Bitflag Smooth Groups',
            description='Same as Smooth Groups, but generate smooth groups IDs as bitflags '
                        '(produces at most 32 different smooth groups, usually much less)',
            default=export_objex.ObjexWriter.default_options['EXPORT_SMOOTH_GROUPS_BITFLAGS'],
            )
    use_normals = BoolProperty(
            name='Write Normals',
            description='Export one normal per vertex and per face, to represent flat faces and sharp edges',
            default=export_objex.ObjexWriter.default_options['EXPORT_NORMALS'],
            )
    use_vertex_colors = BoolProperty(
            name='Write Vertex Colors',
            description='Export one color per vertex and per face',
            default=export_objex.ObjexWriter.default_options['EXPORT_VERTEX_COLORS'],
            )
    use_uvs = BoolProperty(
            name='Include UVs',
            description='Write out the active UV coordinates',
            default=export_objex.ObjexWriter.default_options['EXPORT_UV'],
            )
    use_materials = BoolProperty(
            name='Write Materials',
            description='Write out the MTL file',
            default=export_objex.ObjexWriter.default_options['EXPORT_MTL'],
            )
    use_skeletons = BoolProperty(
            name='Write Skeletons',
            description='Write out the SKEL file',
            default=export_objex.ObjexWriter.default_options['EXPORT_SKEL'],
            )
    use_animations = BoolProperty(
            name='Write Animations',
            description='Write out the ANIM file',
            default=export_objex.ObjexWriter.default_options['EXPORT_ANIM'],
            )
    use_weights = BoolProperty(
            name='Write Weights',
            description='Write out the vertex weights',
            default=export_objex.ObjexWriter.default_options['EXPORT_WEIGHTS'],
            )
    use_unique_weights = BoolProperty(
            name='Write one weight per vertex',
            description="Use vertex group with maximum weight, with weight 1.0 (doesn't write any weight if there is no vertex group assigned)",
            default=export_objex.ObjexWriter.default_options['UNIQUE_WEIGHTS'],
            )
    use_triangles = BoolProperty(
            name='Triangulate Faces',
            description='Convert all faces to triangles',
            default=export_objex.ObjexWriter.default_options['TRIANGULATE'],
            )
    use_vertex_groups = BoolProperty(
            name='Polygroups',
            description='',
            default=export_objex.ObjexWriter.default_options['EXPORT_POLYGROUPS'],
            )

    export_packed_images = BoolProperty(
            name='Export packed images',
            description='Save packed images outside the blend file',
            default=export_objex.ObjexWriter.default_options['EXPORT_PACKED_IMAGES'],
            )
    export_packed_images_dir = StringProperty(
            name='Export packed images directory',
            description='Where to save packed images',
            default=export_objex.ObjexWriter.default_options['EXPORT_PACKED_IMAGES_DIR'],
            )

    keep_vertex_order = BoolProperty(
            name='Keep Vertex Order',
            description='',
            default=export_objex.ObjexWriter.default_options['KEEP_VERTEX_ORDER'],
            )

    global_scale = FloatProperty(
            name='Scale',
            soft_min=0.01, soft_max=1000.0,
            default=1.0,
            )

    # logging
    logging_level_console = IntProperty(
            name='Log level',
            description=(
                'Affects logging in the system console.\n'
                'The lower, the more logs.\n'
                '%s'
            ) % logging_util.debug_levels_str,
            default=logging_util.default_level_console,
            min=logging_util.minimum_level,
            max=logging_util.maximum_level,
            )
    logging_level_report = IntProperty(
            name='Report level',
            description=(
                'What logs to report to Blender.\n'
                'When the import is done, warnings and errors, if any, are shown in the UI.\n'
                'The lower, the more logs.\n'
                '%s'
            ) % logging_util.debug_levels_str,
            default=logging_util.default_level_report,
            min=logging_util.minimum_level,
            max=logging_util.maximum_level,
            )
    logging_file_enable = BoolProperty(
            name='Log to file',
            description='Log everything (all levels) to a file',
            default=True, # 421todo better write logs by default during testing
            )
    logging_file_path = StringProperty(
            name='Log file path',
            description=(
                'The file to write logs to.\n'
                'Path can be relative (to export location) or absolute.'
            ),
            default='objex_export_log.txt',
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
                                            'logging_level_console',
                                            'logging_level_report',
                                            'logging_file_enable',
                                            'logging_file_path',
                                            ))

        global_matrix = (Matrix.Scale(self.global_scale, 4) *
                         axis_conversion(to_forward=self.axis_forward,
                                         to_up=self.axis_up,
                                         ).to_4x4())
        
        keywords['global_matrix'] = global_matrix

        log = logging_util.getLogger('OBJEX_OT_export')
        try:
            logging_util.setConsoleLevel(self.logging_level_console)
            if self.logging_file_enable:
                logfile_path = self.logging_file_path
                if not os.path.isabs(logfile_path):
                    export_dir, _ = os.path.split(self.filepath)
                    logfile_path = '%s/%s' % (export_dir, logfile_path)
                log.info('Writing logs to %s' % logfile_path)
                logging_util.setLogFile(logfile_path)
            logging_util.setLogOperator(self, self.logging_level_report)
            def progress_report_print(*args, **kwargs):
                """
                Typical print() arguments called from progress_report:
                
                args = ('Progress:   1.85%\r',)
                kwargs = {'end': ''}
                
                args = ('    (  0.1298 sec |   0.1198 sec) Objex Export Finished\nProgress: 100.00%\r',)
                kwargs = {'end': ''}
                
                args = ('\n',)
                kwargs = {}
                """
                # ignore kwargs['flush'] and kwargs['file']
                message = '%s%s' % (kwargs.get('sep', ' ').join(args), kwargs.get('end','\n'))
                for line in message.split('\n'):
                    if not line:
                        print() # \n
                    elif line[-1] == '\r':
                        print(line, end='')
                    else:
                        log.info(line)
            progress_report.print = progress_report_print

            return export_objex.save(context, **keywords)
        except:
            log.exception('Uncaught exception')
            raise
        finally:
            progress_report.print = print
            logging_util.resetLoggingSettings()


def menu_func_export(self, context):
    self.layout.operator(OBJEX_OT_export.bl_idname, text='Extended OBJ (new WIP) (.objex)')


classes = (
    OBJEX_OT_export,
)


def register():
    logging_util.registerLogging('objex')

    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.INFO_MT_file_export.append(menu_func_export)
    
    interface.register_interface()


def unregister():
    interface.unregister_interface()
    
    bpy.types.INFO_MT_file_export.remove(menu_func_export)

    for cls in classes:
        bpy.utils.unregister_class(cls)

    logging_util.unregisterLogging()


if __name__ == '__main__':
    register()
