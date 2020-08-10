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
Added a bunch of export options
Added addon preferences
Added a draw function to export operator
"""

bl_info = {
    'name': 'Objex Exporter for N64 romhacking',
    'author': 'Campbell Barton, Bastien Montagne, OoT modding community',
    'version': (1, 0, 0),
    'blender': (2, 80, 0),
    'location': 'File > Export',
    'description': 'Allows to export to objex and provides new features for further customization',
    'warning': '',
    'wiki_url': 'TODO manual',
    'support': 'COMMUNITY',
    'category': 'Import-Export'}


import bpy

if bpy.app.version < (2, 80, 0):
    bl_info['blender'] = (2, 79, 0)

from bpy.props import (
        BoolProperty,
        IntProperty,
        FloatProperty,
        StringProperty,
        )
from bpy_extras.io_utils import (
        ExportHelper,
        path_reference_mode,
        axis_conversion,
        )

try:
    # < 2.80
    from bpy_extras.io_utils import orientation_helper_factory
    def orientation_helper(clazz, axis_forward=None, axis_up=None):
        return clazz
except ImportError:
    # 2.80+
    def orientation_helper_factory(name, axis_forward=None, axis_up=None):
        return object
    from bpy_extras.io_utils import orientation_helper

import os
try:
    import progress_report
except ImportError:
    import bpy_extras.wm_utils.progress_report as progress_report

# reload files
import importlib
loc = locals()
for n in (
    'export_objex', 'export_objex_mtl', 'export_objex_anim',
    'properties', 'interface', 'const_data', 'util', 'logging_util',
    'rigging_helpers', 'data_updater', 'view3d_copybuffer_patch',
    'addon_updater', 'addon_updater_ops', 'blender_version_compatibility',
):
    if n in loc:
        importlib.reload(loc[n])
del importlib

from . import blender_version_compatibility

from . import export_objex
from . import properties
from . import data_updater
from . import interface
from . import logging_util
from . import rigging_helpers
from . import view3d_copybuffer_patch
from . import addon_updater_ops

axis_forward = '-Z'
axis_up='Y'

IOOBJOrientationHelper = orientation_helper_factory('IOOBJOrientationHelper', axis_forward=axis_forward, axis_up=axis_up)

@orientation_helper(axis_forward=axis_forward, axis_up=axis_up)
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
    include_armatures_from_selection = BoolProperty(
            name='Used armatures',
            description='Also export any armature used by the selection, even if it is not selected',
            default=True,
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
    apply_unused_armature_deform = BoolProperty(
            name='Apply unused deform',
            description='Apply armature deform modifiers when the armature is not being exported',
            default=export_objex.ObjexWriter.default_options['APPLY_UNUSED_ARMATURE_DEFORM'],
            )
    apply_modifiers_after_armature_deform = BoolProperty(
            name='Apply modifiers after deform',
            description='Apply modifiers after the armature deform modifier.\n'
                        'If they are applied, it would be as if the armature deform was '
                        'last in the stack, since it would only be "applied" later (for example, '
                        'in-game) when the mesh is displayed animated.',
            default=export_objex.ObjexWriter.default_options['APPLY_MODIFIERS_AFTER_ARMATURE_DEFORM'],
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
            description='Write out the MTLEX file',
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

    def draw(self, context):
        self.layout.prop(self, 'global_scale')
        if self.use_selection:
            box = self.layout.box()
            box.prop(self, 'use_selection')
            box.prop(self, 'include_armatures_from_selection')
        else:
            self.layout.prop(self, 'use_selection')
        if self.use_mesh_modifiers:
            box = self.layout.box()
            box.prop(self, 'use_mesh_modifiers')
            box.prop(self, 'use_mesh_modifiers_render')
            box.prop(self, 'apply_unused_armature_deform')
            box.prop(self, 'apply_modifiers_after_armature_deform')
        else:
            self.layout.prop(self, 'use_mesh_modifiers')
        self.layout.prop(self, 'use_uvs')
        self.layout.prop(self, 'use_normals')
        self.layout.prop(self, 'use_vertex_colors')
        if self.use_smooth_groups:
            box = self.layout.box()
            box.prop(self, 'use_smooth_groups')
            box.prop(self, 'use_smooth_groups_bitflags')
        else:
            self.layout.prop(self, 'use_smooth_groups')
        self.layout.prop(self, 'use_materials')
        if self.use_skeletons:
            box = self.layout.box()
            box.prop(self, 'use_skeletons')
            box.prop(self, 'use_animations')
            if self.use_weights:
                box2 = box.box()
                box2.prop(self, 'use_weights')
                box2.prop(self, 'use_unique_weights')
            else:
                box.prop(self, 'use_weights')
        else:
            self.layout.prop(self, 'use_skeletons')
        self.layout.prop(self, 'axis_forward')
        self.layout.prop(self, 'axis_up')
        self.layout.prop(self, 'keep_vertex_order')
        self.layout.prop(self, 'use_triangles')
        if self.export_packed_images:
            box = self.layout.box()
            box.prop(self, 'export_packed_images')
            box.prop(self, 'export_packed_images_dir')
        else:
            self.layout.prop(self, 'export_packed_images')
        box = self.layout.box()
        box.prop(self, 'logging_level_console')
        box.prop(self, 'logging_level_report')
        box.prop(self, 'logging_file_enable')
        if self.logging_file_enable:
            box.prop(self, 'logging_file_path')
        self.layout.prop(self, 'path_mode')

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

        global_matrix = blender_version_compatibility.matmul(
                         Matrix.Scale(self.global_scale, 4),
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
                log.info('Writing logs to {}', logfile_path)
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

            if any(material.objex_bonus.is_objex_material for material in bpy.data.materials):
                for area in bpy.context.screen.areas:
                    if area.type == 'VIEW_3D':
                        for space in area.spaces:
                            shading_type = space.viewport_shade if hasattr(space, 'viewport_shade') else space.shading.type
                            if space.type == 'VIEW_3D' and shading_type != 'MATERIAL':
                                log.warning('There is a 3d view area in the current screen which is using {} '
                                    'shading and not MATERIAL shading. MATERIAL shading is required to correctly '
                                    'preview objex-enabled materials', shading_type)

            return export_objex.save(context, **keywords)
        except util.ObjexExportAbort as abort:
            log.error('Export abort: {}', abort.reason)
            return {'CANCELLED'}
        except:
            log.exception('Uncaught exception')
            raise
        finally:
            progress_report.print = print
            logging_util.resetLoggingSettings()


def menu_func_export(self, context):
    self.layout.operator(OBJEX_OT_export.bl_idname, text='Extended OBJ (new WIP) (.objex)')


class OBJEX_AddonPreferences(bpy.types.AddonPreferences, addon_updater_ops.AddonUpdaterPreferences):
    bl_idname = __package__

    # see view3d_copybuffer_patch.py
    monkeyPatch_view3d_copybuffer = bpy.props.EnumProperty(
        items=[
            ('AUTO','Auto','Default to "Wrap copying - delete" (for now)',1),
            ('NOTHING','Do nothing','Do not disable "Ctrl+C" (or any other or change anything else',2),
            ('DISABLE','Disable Ctrl+C','Disable "Ctrl+C", the key combo will do nothing',3),
            ('WRAPPER_DELETE','Wrap copying - delete',
                'Disable vanilla copy operator shortcut (usually Ctrl+C) and remap it to '
                'an operator that deletes the data causing issues before copying',4),
            # 421todo cf comments in OBJEX_OT_view3d_copybuffer_wrapper in view3d_copybuffer_patch.py
            #('WRAPPER_PACK','Wrap copying - pack','Disable vanilla copy operator shortcut (usually Ctrl+C) and remap it to an operator that encodes the data causing issues before copying, and also wrap the paste operator to decode that data',5),
        ],
        name='"Fix" copy',
        # Specifically, the addon-defined sockets *seem* to be at fault
        description='Method to use for "fixing" (read: circumventing an issue) "Ctrl+C" (or any shortcut mapped to the copy operator view3d.copybuffer) which crashed Blender when copying objects using Objex-enabled materials',
        default='AUTO',
        update=view3d_copybuffer_patch.monkeyPatch_view3d_copybuffer_update
    )
    # what were the user settings for view3d.copybuffer before the addon changed it
    monkeyPatch_view3d_copybuffer_active_user = bpy.props.EnumProperty(
        items=[
            ('None', '','',1), # settings not overwritten by addon
            ('True', '','',2),
            ('False','','',3),
        ],
        default='None'
    )

    def draw(self, context):
        addon_updater_ops.check_for_update_background()
        self.layout.prop(self, 'monkeyPatch_view3d_copybuffer')
        addon_updater_ops.update_settings_ui(self, context)
        addon_updater_ops.update_notice_box_ui(self, context)


classes = (
    OBJEX_OT_export,
    OBJEX_AddonPreferences,
)


def register():
    addon_updater_ops.register(bl_info)

    logging_util.registerLogging('objex')

    for cls in classes:
        blender_version_compatibility.make_annotations(cls)
        bpy.utils.register_class(cls)

    _MT_file_export = bpy.types.INFO_MT_file_export if hasattr(bpy.types, 'INFO_MT_file_export') else bpy.types.TOPBAR_MT_file_export
    _MT_file_export.append(menu_func_export)

    rigging_helpers.register()
    properties.register_properties()
    data_updater.register()
    interface.register_interface()
    view3d_copybuffer_patch.register()


def unregister():
    view3d_copybuffer_patch.unregister()
    interface.unregister_interface()
    data_updater.unregister()
    properties.unregister_properties()
    rigging_helpers.unregister()

    _MT_file_export = bpy.types.INFO_MT_file_export if hasattr(bpy.types, 'INFO_MT_file_export') else bpy.types.TOPBAR_MT_file_export
    _MT_file_export.remove(menu_func_export)

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    logging_util.unregisterLogging()

    addon_updater_ops.unregister()


if __name__ == '__main__':
    register()
