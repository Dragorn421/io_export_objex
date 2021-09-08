#  Copyright 2020 Campbell Barton, Bastien Montagne
#  Copyright 2020-2021 Dragorn421, z64me, Sauraen
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

from . import blender_version_compatibility

import os
import time

import bpy
import mathutils
import bpy_extras.io_utils

try:
    from progress_report import ProgressReport, ProgressReportSubstep
except ImportError:
    from bpy_extras.wm_utils.progress_report import ProgressReport, ProgressReportSubstep

from .export_collect import collect_display_mesh
from .export_collect import collect_armature
from . import export_objex_mtl
from . import export_objex_anim
from . import util
from .logging_util import getLogger


def mesh_triangulate(me):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()

def roundVect3d(v, digits):
    return round(v.x, digits), round(v.y, digits), round(v.z, digits)

def roundVect2d(v, digits):
    return round(v[0], digits), round(v[1], digits)

class ObjexWriter():
    default_options = {
        'TRIANGULATE': True,
        'EXPORT_NORMALS': True,
        'EXPORT_VERTEX_COLORS': True,
        'EXPORT_UV': True,
        'EXPORT_MTL': True,
        'EXPORT_SKEL': True,
        'EXPORT_ANIM': True,
        'EXPORT_LINK_ANIM_BIN': False,
        'LINK_BIN_SCALE': 1000.0,
        'EXPORT_WEIGHTS': True,
        'UNIQUE_WEIGHTS': False,
        'APPLY_MODIFIERS': True,
        'APPLY_MODIFIERS_RENDER': False,
        'APPLY_UNUSED_ARMATURE_DEFORM':False,
        'APPLY_MODIFIERS_AFTER_ARMATURE_DEFORM': False,
        'EXPORT_PACKED_IMAGES': False,
        'EXPORT_PACKED_IMAGES_DIR': '//objex_textures',
        'GLOBAL_MATRIX': None,
        'PATH_MODE': 'AUTO'
    }
    
    def __init__(self, context):
        self.log = getLogger('ObjexWriter')
        self.context = context
        self.objects = []
        self.options = ObjexWriter.default_options.copy()
    
    def add_target_objects(self, objects):
        self.objects.extend(objects)
    
    def set_options(self, options):
        for k,v in options.items():
            if v is not None:
                self.options[k] = v
    
    def write_header(self):
        fw = self.fw_objex
        
        fw('# Blender v%s Objex File: %r\n' % (bpy.app.version_string, os.path.basename(bpy.data.filepath)))
        fw('# www.blender.org\n')

        two, major, minor = util.get_addon_version()
        fw('# io_export_objex2 v%d.%d.%d\n' % (two, major, minor))
        fw('version %d.%d\n' % (two, major))

        self.export_id_line = 'exportid %f\n' % time.time()
        fw(self.export_id_line)

        scene = self.context.scene
        fw('softinfo animation_framerate %g\n' % (scene.render.fps / scene.render.fps_base))

        # Tell the obj file what material/skeleton/animation file to use.
        if self.options['EXPORT_MTL']:
            self.filepath_mtl = os.path.splitext(self.filepath)[0] + ".mtlex"
            # filepath can contain non utf8 chars, use repr
            fw('mtllib %s\n' % repr(os.path.basename(self.filepath_mtl))[1:-1])
        
        if self.options['EXPORT_SKEL']:
            self.filepath_skel = os.path.splitext(self.filepath)[0] + ".skel"
            fw('skellib %s\n' % repr(os.path.basename(self.filepath_skel))[1:-1])
            if self.options['EXPORT_ANIM']:
                self.filepath_anim = os.path.splitext(self.filepath)[0] + ".anim"
                fw('animlib %s\n' % repr(os.path.basename(self.filepath_anim))[1:-1])
                if self.options['EXPORT_LINK_ANIM_BIN']:
                    self.filepath_linkbase = os.path.splitext(self.filepath)[0] + '_'

    def collect_object_try_display_mesh(self, progress, ob, ob_mat):
        log = self.log
        scene = self.context.scene

        rigged_to_armature = ob.find_armature()

        apply_modifiers = self.options['APPLY_MODIFIERS']
        using_depsgraph = hasattr(self.context, 'evaluated_depsgraph_get') # True in 2.80+
        # disable armature deform modifiers
        user_show_armature_modifiers = []
        if apply_modifiers:
            found_armature_deform = False
            for modifier in ob.modifiers:
                disable_modifier = False
                if found_armature_deform and not self.options['APPLY_MODIFIERS_AFTER_ARMATURE_DEFORM']:
                    log.info('Skipped modifier {} which is down of the armature deform modifier', modifier.name)
                    disable_modifier = True
                if modifier.type == 'ARMATURE':
                    if rigged_to_armature:
                        # don't apply armature deform (aka disable modifier) if armature is exported,
                        # or if the armature deform should be applied for armatures that aren't exported ("UNUSED")
                        if rigged_to_armature in self.objects or not self.options['APPLY_UNUSED_ARMATURE_DEFORM']:
                            if modifier.object == rigged_to_armature:
                                if found_armature_deform:
                                    log.warning('Found several armature deform modifiers on object {} using armature {}',
                                        ob.name, rigged_to_armature.name)
                                found_armature_deform = True
                                disable_modifier = True
                            else:
                                log.warning('Object {} was found to be rigged to {} but it also has an armature deform modifier using {}',
                                    ob.name, rigged_to_armature.name, modifier.object.name if modifier.object else None)
                        else:
                            if rigged_to_armature not in self.objects:
                                log.debug("Leaving armature deform modifier {!r} as is, object {!r} is rigged to {!r} but that armature is not exported",
                                    modifier, ob, rigged_to_armature)
                    else:
                        log.debug("Leaving armature deform modifier {!r} as is, object {!r} is not rigged", modifier, ob)
                modifier_show = None
                if disable_modifier:
                    modifier_show = False
                elif using_depsgraph:
                    modifier_show = modifier.show_render if self.options['APPLY_MODIFIERS_RENDER'] else modifier.show_viewport
                if modifier_show is not None:
                    user_show_armature_modifiers.append((modifier, modifier.show_viewport, modifier.show_render))
                    modifier.show_viewport = modifier_show
                    modifier.show_render = modifier_show
                    log.trace("Set modifier {!r} on object {!r} to " + ("active" if modifier_show else "disabled"), modifier, ob)
                else:
                    log.trace("Leaving modifier {!r} on object {!r} as is", modifier, ob)

        if using_depsgraph: # 2.80+
            ob_for_convert = ob.evaluated_get(self.context.evaluated_depsgraph_get()) if apply_modifiers else ob.original
        else:
            ob_for_convert = None

        try:
            if not ob_for_convert: # < 2.80
                me = ob.to_mesh(scene, apply_modifiers, calc_tessface=False,
                                settings='RENDER' if self.options['APPLY_MODIFIERS_RENDER'] else 'PREVIEW')
            else: # 2.80+
                # 421fixme should preserve_all_data_layers=True be used?
                me = ob_for_convert.to_mesh()
        except RuntimeError:
            me = None
        finally:
            # restore modifiers properties
            for modifier, user_show_viewport, user_show_render in user_show_armature_modifiers:
                modifier.show_viewport = user_show_viewport
                modifier.show_render = user_show_render

        if me is None:
            return

        # _must_ do this before applying transformation, else tessellation may differ
        if self.options['TRIANGULATE']:
            if not all(len(polygon.vertices) == 3 for polygon in me.polygons):
                notes = []
                if any(modifier.type == 'TRIANGULATE' for modifier in ob.modifiers):
                    notes.append('mesh has a triangulate modifier')
                    if apply_modifiers:
                        notes.append('even after applying modifiers')
                    else:
                        notes.append('modifiers are not being applied (check export options)')
                    if rigged_to_armature and not self.options['APPLY_MODIFIERS_AFTER_ARMATURE_DEFORM']:
                        notes.append('mesh is rigged and only modifiers before armature deform are used\n'
                            '(move the triangulate modifier up, or check export options)')
                else:
                    notes.append('mesh has no triangulate modifier')
                log.warning('Mesh {} is not triangulated and will be triangulated automatically (for exporting only).\n'
                    'Preview accuracy (UVs, shading, vertex colors) is improved by using a triangulated mesh.'
                    '{}', ob.name, ''.join('\nNote: %s' % note for note in notes))
                # _must_ do this first since it re-allocs arrays
                mesh_triangulate(me)
            else:
                log.debug('Skipped triangulating {}, mesh only has triangles', ob.name)

        me.transform(blender_version_compatibility.matmul(self.options['GLOBAL_MATRIX'], ob_mat))
        # If negative scaling, we have to invert the normals...
        if ob_mat.determinant() < 0.0:
            me.flip_normals()

        # FIXME warnings and checks that became outdated with the material collecting,
        # but would still be nice to put them somewhere
        """
                # FIXME this should be moved to collision-specific export stuff
                objectUseCollision = ob.name.startswith('collision.')
                # 421fixme
                # if the export is done right after material initialization, material properties
                # are for some reason still reading the old values. They update at least
                # when modifying objex_bonus properties in the UI or renaming the material
                # context.view_layer.update() doesn't help
                if objectUseCollision and not material.objex_bonus.is_objex_material:
                    raise util.ObjexExportAbort(
                        'Object {} is for collision (has "collision." prefix) '
                        'but material {} used by this object is not for collision '
                        '(not even initialized as an objex material)'
                        .format(ob.name, material.name)
                    )
                if objectUseCollision and not material.objex_bonus.use_collision:
                    raise util.ObjexExportAbort(
                        'Object {} is for collision (has "collision." prefix) '
                        'but material {} used by this object is not for collision'
                        .format(ob.name, material.name)
                    )
                if not objectUseCollision and material.objex_bonus.use_collision:
                    raise util.ObjexExportAbort(
                        'Object {} is not for collision (does not have "collision." prefix) '
                        'but material {} used by this object is for collision'
                        .format(ob.name, material.name)
                    )



        # assume non-objex materials using nodes are a rarity before 2.8x
        if objex_data and material.use_nodes and not objex_data.is_objex_material and bpy.app.version < (2, 80, 0):
            log.warning('Material {!r} use_nodes but not is_objex_material\n'
                '(did you copy-paste nodes from another material instead of clicking the "Init..." button?),\n'
                'nodes will be ignored and the face image will be used\n'
                '(for now, to use the current nodes you can make a temporary duplicate of the material,\n'
                'click the "Init..." button on the original material, delete all the generated nodes\n'
                'and paste the actual nodes from the duplicate)'
                , material)



        """

        if self.options['EXPORT_NORMALS']:
            me.calc_normals_split()
            # No need to call me.free_normals_split later, as this mesh is deleted anyway!

        cd_mesh = self.display_collector.collect_display_mesh(
            me,
            collect_materials=self.options['EXPORT_MTL'],
            collect_uvs=self.options['EXPORT_UV'],
            collect_vertex_colors=self.options['EXPORT_VERTEX_COLORS']
        )

        cd_mesh.transform = ob_mat
        cd_mesh.location = ob.location.copy().freeze()
        cd_mesh.name = ob.name
        cd_mesh.name_q = util.quote(cd_mesh.name)

        if ob.type == 'MESH':
            cd_mesh.mesh_objex_bonus = ob.data.objex_bonus
        else:
            cd_mesh.mesh_objex_bonus = None

        cd_mesh.rigged_to_armature = rigged_to_armature
        cd_mesh.rigged_to_armature_name = None if rigged_to_armature is None else rigged_to_armature.name
        cd_mesh.vertex_groups_names = list(ob.vertex_groups.keys())

        # clean up
        if not ob_for_convert: # < 2.80
            bpy.data.meshes.remove(me)
        else: # 2.80+
            ob_for_convert.to_mesh_clear()

        self.collected_display_meshes.append(cd_mesh)

    def collect_object_armature(self, progress, ob, ob_mat):
        # FIXME collect
        if self.options['EXPORT_ANIM']:
            objex_data = ob.data.objex_bonus
            if objex_data.export_all_actions:
                actions = bpy.data.actions
            else:
                if blender_version_compatibility.no_ID_PointerProperty:
                    actions = [bpy.data.actions[item.action] for item in objex_data.export_actions if item.action]
                else:
                    actions = [item.action for item in objex_data.export_actions if item.action]
        else:
            actions = []

        # 421todo force 20 fps somewhere?
        scene_fps = self.context.scene.render.fps / self.context.scene.render.fps_base
        if scene_fps != 20 and actions and not self.already_warned_not_20fps:
            self.already_warned_not_20fps = True
            self.log.warning('animations are being viewed at {:.1f} fps (change this in render settings), but will be used at 20 fps', scene_fps)

        transform = blender_version_compatibility.matmul(self.options["GLOBAL_MATRIX"], ob_mat)

        collected_armature = collect_armature.collect_armature(self.context.scene, ob, transform, actions)

        collected_armature.name = ob.name
        collected_armature.name_q = util.quote(collected_armature.name)

        collected_armature.objex_bonus = ob.data.objex_bonus

        self.collected_armatures_dict[ob] = collected_armature
        self.collected_armatures.append(collected_armature)

    def collect_object(self, progress, ob, ob_mat):
        if ob.type == 'ARMATURE':
            if self.options['EXPORT_SKEL']:
                self.collect_object_armature(progress, ob, ob_mat)
        else:
            self.collect_object_try_display_mesh(progress, ob, ob_mat)

    def write_display_mesh(self, progress, cd_mesh):
        log = self.log
        fw = self.fw_objex

        with ProgressReportSubstep(progress, 6) as subprogress2:

            if not (cd_mesh.vertices or cd_mesh.faces):  # Make sure there is something to write
                return  # dont bother with this mesh.

            # Sort by material, so we dont over context switch in the obj file.
            i = 0
            for materials in (
                self.display_collector.collected_materials,
                self.display_collector.face_image_materials,
            ):
                for cd_material in materials.values():
                    cd_material.contextSortIndex = i
                    i += 1
            cd_mesh.faces.sort(key=lambda cd_face: (cd_face.material.contextSortIndex if cd_face.material else -1))

            util.detect_zztag(log, cd_mesh.name)
            fw('g {}\n'.format(cd_mesh.name_q))

            # rig_is_exported is used to avoid referencing a skeleton or bones which aren't exported
            rig_is_exported = self.options['EXPORT_SKEL'] and (cd_mesh.armature_collected is not None)

            if cd_mesh.mesh_objex_bonus is not None:
                objex_data = cd_mesh.mesh_objex_bonus # ObjexMeshProperties
                if objex_data.priority != 0:
                    fw('priority %d\n' % objex_data.priority)
                if objex_data.write_origin == 'YES' or (
                    objex_data.write_origin == 'AUTO'
                    and objex_data.attrib_billboard != 'NONE'
                ):
                    fw('origin {0.x} {0.y} {0.z}\n'
                        .format(blender_version_compatibility.matmul(self.options['GLOBAL_MATRIX'], cd_mesh.location)))
                if objex_data.attrib_billboard != 'NONE':
                    fw('attrib %s\n' % objex_data.attrib_billboard)
                for attrib in ('POSMTX', 'PROXY'):
                    if getattr(objex_data, 'attrib_%s' % attrib):
                        fw('attrib %s\n' % attrib)
                # export those attributes when the properties are shown in the ui, that is when the mesh is rigged
                if cd_mesh.rigged_to_armature_name is not None:
                    for attrib in ('LIMBMTX', 'NOSPLIT', 'NOSKEL'):
                        if getattr(objex_data, 'attrib_%s' % attrib):
                            if rig_is_exported:
                                fw('attrib %s\n' % attrib)
                            else:
                                log.warning('Mesh {} is rigged to armature {} and sets {},\n'
                                    'but that armature is not being exported. Skipped exporting the attribute.\n'
                                    '(you are likely exporting Selection Only, unchecked Used armatures, and did not select the armature)',
                                    cd_mesh.name, cd_mesh.rigged_to_armature_name, attrib)

            subprogress2.step()

            if self.options['EXPORT_WEIGHTS']:
                vertex_groups_names = cd_mesh.vertex_groups_names
                vertex_groups_names_q = [
                    util.quote(vertex_group_name) for vertex_group_name in vertex_groups_names
                ]

            # Vert
            if rig_is_exported:
                fw('useskel {}\n'.format(cd_mesh.armature_collected.name_q))
            if self.options['EXPORT_WEIGHTS'] and vertex_groups_names and rig_is_exported:
                # only write vertex groups named after actual bones
                bone_names = [bone.name for bone in cd_mesh.armature_collected.bones_ordered]
                # only group of maximum weight, with weight 1
                if self.options['UNIQUE_WEIGHTS']:
                    for cd_vertex in cd_mesh.vertices:
                        fw('v {0.x} {0.y} {0.z}'.format(cd_vertex.coords))
                        if cd_vertex.groups:
                            group_index, weight = max(
                                (item for item in cd_vertex.groups if vertex_groups_names[item[0]] in bone_names),
                                key=lambda item: item[1]
                            )
                            fw(' weight {} 1'.format(vertex_groups_names_q[group_index]))
                        fw('\n')
                # all (non-zero) weights
                else:
                    for cd_vertex in cd_mesh.vertices:
                        fw('v {0.x} {0.y} {0.z}'.format(cd_vertex.coords))
                        fw(','.join(
                            ' weight {} {}'.format(vertex_groups_names_q[group_index], weight)
                            for group_index, weight in cd_vertex.groups
                            if weight != 0
                        ))
                        fw('\n')
            # no weights
            else:
                for cd_vertex in cd_mesh.vertices:
                    # FIXME z64convert uses sscanf which should be able to read the scientific notation this
                    # formatting may use (eg `1e-07`), but it would be better to actually test it
                    # https://github.com/z64me/z64convert/blob/857e20bde09db17436001faa081326cc762d861f/src/objex.c#L2446
                    fw('v {0.x} {0.y} {0.z}\n'.format(cd_vertex.coords))
            i = 0
            for cd_vertex in cd_mesh.vertices:
                cd_vertex.index = i
                i += 1
            vertex_unique_count = len(cd_mesh.vertices)

            subprogress2.step()

            if self.options['EXPORT_UV']:
                # FIXME avoid duplicate vt lines (see vn, may want to wrap the code to reuse it)
                uv_unique_count = 0
                for cd_vertex in cd_mesh.vertices:
                    if cd_vertex.uv_coords is None:
                        cd_vertex.index_uv = None
                    else:
                        fw('vt {0.x} {0.y}\n'.format(cd_vertex.uv_coords))
                        cd_vertex.index_uv = uv_unique_count
                        uv_unique_count += 1
                has_uvs = True
            else:
                uv_unique_count = 0
                has_uvs = False

            subprogress2.step()

            if self.options['EXPORT_NORMALS']:
                normal_unique_count = 0
                indices_normal = dict()
                for cd_vertex in cd_mesh.vertices:
                    if cd_vertex.normal is None:
                        cd_vertex.index_normal = None
                    else:
                        index_normal = indices_normal.get(cd_vertex.normal)
                        if index_normal is None:
                            fw('vn {0.x} {0.y} {0.z}\n'.format(cd_vertex.normal))
                            index_normal = normal_unique_count
                            indices_normal[cd_vertex.normal] = index_normal
                            normal_unique_count += 1
                        cd_vertex.index_normal = index_normal
                has_normals = True
            else:
                normal_unique_count = 0
                has_normals = False
            
            if self.options['EXPORT_VERTEX_COLORS']:
                vertex_color_unique_count = 0
                for cd_vertex in cd_mesh.vertices:
                    if cd_vertex.color is None:
                        cd_vertex.index_vertex_color = None
                    else:
                        fw('vc {}\n'.format(' '.join(cd_vertex.color)))
                        cd_vertex.index_vertex_color = vertex_color_unique_count
                        vertex_color_unique_count += 1
                has_vertex_colors = True
            else:
                vertex_color_unique_count = 0
                has_vertex_colors = False

            subprogress2.step()

            # used to keep track of the last g/usemtl directive written, according to options
            # Can never be 0, so we will label a new material the first chance we get. used for usemtl directives if EXPORT_MTL
            context_cd_material = 0  

            for cd_face in cd_mesh.faces:
                if self.options['EXPORT_MTL']:
                    # if context hasn't changed, do nothing
                    if context_cd_material == cd_face.material:
                        pass
                    else:
                        # update context
                        context_cd_material = cd_face.material

                        # clear context
                        if context_cd_material is None:
                            fw('clearmtl\n')
                        # new context
                        else:
                            fw('usemtl {}\n'.format(context_cd_material.name_q))

                fw('f')
                for cd_vertex in cd_face.vertices:
                    vt = has_uvs and cd_vertex.index_uv is not None
                    vn = has_normals and cd_vertex.index_normal is not None
                    vc = has_vertex_colors and cd_vertex.index_vertex_color is not None

                    f_v_data = []

                    f_v_data.append(self.total_vertex + cd_vertex.index)

                    if vt:
                        f_v_data.append(self.total_uv + cd_vertex.index_uv)
                    elif vn or vc:
                        f_v_data.append(None)

                    if vn:
                        f_v_data.append(self.total_normal + cd_vertex.index_normal)
                    elif vc:
                        f_v_data.append(None)

                    if vc:
                        f_v_data.append(self.total_vertex_color + cd_vertex.index_vertex_color)

                    # v[/vt[/vn[/vc]]] coordinates/uv/normal/color
                    fw(' {}'.format('/'.join('' if i is None else str(i) for i in f_v_data)))
                fw('\n')

            subprogress2.step()

            # Make the indices global rather then per mesh
            self.total_vertex += vertex_unique_count
            self.total_uv += uv_unique_count
            self.total_normal += normal_unique_count
            self.total_vertex_color += vertex_color_unique_count

    def write(self, filepath):
        """
        This function starts the exporting. It defines a few "globals" as class members, notably the total_* variables
        It loops through objects, writing each to .objex (with the write_object method), and collecting materials/armatures/animations as it goes.
        Once the .objex is finished being written, write_mtl is called to write the .mtl and same thing with write_anim which writes .anim and itself calls .skel which writes .skel
        """
        log = self.log
        self.filepath = filepath
        self.already_warned_not_20fps = False

        with ProgressReport(self.context.window_manager) as progress:
            scene = self.context.scene

            # Exit edit mode before exporting, so current object states are exported properly.
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode='OBJECT')

            # user_ variables store parameters (potentially) used by the script and to be restored later
            user_frame_current = scene.frame_current
            user_frame_subframe = scene.frame_subframe
            
            progress.enter_substeps(1)
            
            with ProgressReportSubstep(progress, 6, "Objex Export path: %r" % filepath, "Objex Export Finished") as subprogress1:

                # Initialize totals, these are updated each object
                self.total_vertex = self.total_uv = self.total_normal = self.total_vertex_color = 1

                self.display_collector = collect_display_mesh.DisplayMeshCollector()

                copy_set = set()

                #
                # Step 1 - Collect: copy data from Blender data to addon classes
                #

                # collect objects
                subprogress1.enter_substeps(len(self.objects))

                self.collected_display_meshes = []
                self.collected_armatures = []
                self.collected_armatures_dict = dict()

                for ob_main in self.objects:
                    # 421todo I don't know what this dupli stuff is about
                    # ("instancer" stuff in 2.80+)
                    use_old_dupli = hasattr(ob_main, 'dupli_type') # True in < 2.80
                    # ignore dupli children
                    if (ob_main.parent
                        and (ob_main.parent.dupli_type if use_old_dupli else ob_main.parent.instance_type)
                                in {'VERTS', 'FACES'}
                    ):
                        subprogress1.step("Ignoring %s, dupli child..." % ob_main.name)
                        continue

                    obs = [(ob_main, ob_main.matrix_world)]
                    added_dupli_children = True
                    if use_old_dupli and ob_main.dupli_type != 'NONE':
                        # XXX
                        log.info('creating dupli_list on {}', ob_main.name)
                        ob_main.dupli_list_create(scene)

                        obs += [(dob.object, dob.matrix) for dob in ob_main.dupli_list]
                    elif not use_old_dupli and ob_main.is_instancer:
                        obs += [(dup.instance_object.original, dup.matrix_world.copy())
                                for dup in self.context.evaluated_depsgraph_get().object_instances
                                if dup.parent and dup.parent.original == ob_main]
                    else:
                        added_dupli_children = False
                    if added_dupli_children:
                        log.debug('{} has {} dupli children', ob_main.name, len(obs) - 1)

                    subprogress1.enter_substeps(len(obs))
                    for ob, ob_mat in obs:
                        self.collect_object(subprogress1, ob, ob_mat)
                        subprogress1.step("Finished collecting object {}.".format(ob.name))
                    subprogress1.leave_substeps("Finished collecting all instances of object {}.".format(ob_main.name))
                subprogress1.leave_substeps()

                if self.options['EXPORT_MTL']:
                    for materials in (
                        self.display_collector.collected_materials,
                        self.display_collector.face_image_materials,
                    ):
                        # collected_materials: source is a Material
                        # face_image_materials: source is an Image
                        for source, cd_material in materials.items():
                            cd_material.already_discovered = True
                            name = source.name
                            i = 0
                            while name in (
                                other_cd_material.name for other_cd_material in self.display_collector.collected_materials.values()
                                if hasattr(other_cd_material, 'name')
                            ):
                                name = '{} {}'.format(source.name, i)
                                i += 1
                            cd_material.name = name
                            cd_material.name_q = util.quote(name)

                # map the rigged_to_armature armature object to the collected armature
                for cd_mesh in self.collected_display_meshes:
                    if cd_mesh.rigged_to_armature is not None:
                        cd_mesh.armature_collected = self.collected_armatures_dict[cd_mesh.rigged_to_armature]
                    else:
                        cd_mesh.armature_collected = None
                    del cd_mesh.rigged_to_armature
                del self.collected_armatures_dict

                # cleanup
                subprogress1.enter_substeps(len(self.objects))
                for ob_main in self.objects:
                    if use_old_dupli and ob_main.dupli_type != 'NONE':
                        ob_main.dupli_list_clear()
                    elif not use_old_dupli:
                        pass # no clean-up needed
                subprogress1.leave_substeps()

                #
                # Step 2 - Write: write the data stored in addon classes to .objex and other files
                #

                # write .objex
                with open(filepath, "w", encoding="utf8", newline="\n") as f:
                    self.fw_objex = f.write

                    # write leading comments, mtllib/animlib/skellib directives, and defines filepath_* to write .mtl/... to
                    self.write_header()

                    subprogress1.enter_substeps(len(self.collected_display_meshes))
                    for cd_mesh in self.collected_display_meshes:
                        self.write_display_mesh(subprogress1, cd_mesh)
                    subprogress1.leave_substeps()

                    del self.fw_objex

                subprogress1.step("Finished exporting geometry, now exporting materials")

                # write .mtlex
                if self.options['EXPORT_MTL']:
                    def append_header_mtl(fw_mtl):
                        fw_mtl(self.export_id_line)
                    export_objex_mtl.write_mtl(
                        scene, self.filepath_mtl, append_header_mtl, self.options, copy_set,
                        self.display_collector.collected_materials,
                        self.display_collector.face_image_materials,
                    )

                subprogress1.step("Finished exporting materials, now exporting skeletons/animations")

                # write .skel and .anim
                if self.options['EXPORT_SKEL']:
                    log.info('now exporting skeletons')
                    skelfile = None
                    animfile = None
                    try:
                        skelfile = open(self.filepath_skel, "w", encoding="utf8", newline="\n")
                        skelfile_write = skelfile.write
                        skelfile_write(self.export_id_line)
                        link_anim_basepath = None
                        if self.options['EXPORT_ANIM']:
                            log.info(' ... and animations')
                            animfile = open(self.filepath_anim, "w", encoding="utf8", newline="\n")
                            animfile_write = animfile.write
                            animfile_write(self.export_id_line)
                            if self.options['EXPORT_LINK_ANIM_BIN']:
                                log.info(' ... and Link animation binaries')
                                link_anim_basepath = self.filepath_linkbase
                        else:
                            animfile_write = None
                        export_objex_anim.write_armatures(skelfile_write, animfile_write, 
                            self.collected_armatures,
                            link_anim_basepath, self.options['LINK_BIN_SCALE'])
                    finally:
                        if skelfile:
                            skelfile.close()
                        if animfile:
                            animfile.close()
                
                # copy all collected files.
                bpy_extras.io_utils.path_reference_copy(copy_set)

            scene.frame_set(user_frame_current, subframe=user_frame_subframe)

            progress.leave_substeps()


def save(context,
         filepath,
         *,
         use_triangles=None,
         use_normals=None,
         use_vertex_colors=None,
         use_uvs=None,
         use_materials=None,
         use_skeletons=None,
         use_animations=None,
         link_anim_bin=None,
         link_bin_scale=None,
         use_weights=None,
         use_unique_weights=None,
         use_mesh_modifiers=None,
         use_mesh_modifiers_render=None,
         apply_unused_armature_deform=None,
         apply_modifiers_after_armature_deform=None,
         export_packed_images=None,
         export_packed_images_dir=None,
         use_selection=None,
         use_collection=None,
         include_armatures_from_selection=True,
         global_matrix=None,
         path_mode=None
         ):

    writer = ObjexWriter(context)
    writer.set_options({
        'TRIANGULATE':use_triangles,
        'EXPORT_NORMALS':use_normals,
        'EXPORT_VERTEX_COLORS':use_vertex_colors,
        'EXPORT_UV':use_uvs,
        'EXPORT_MTL':use_materials,
        'EXPORT_SKEL':use_skeletons,
        'EXPORT_ANIM':use_animations,
        'EXPORT_LINK_ANIM_BIN':link_anim_bin,
        'LINK_BIN_SCALE':link_bin_scale,
        'EXPORT_WEIGHTS':use_weights,
        'UNIQUE_WEIGHTS':use_unique_weights,
        'APPLY_MODIFIERS':use_mesh_modifiers,
        'APPLY_MODIFIERS_RENDER':use_mesh_modifiers_render,
        'APPLY_UNUSED_ARMATURE_DEFORM':apply_unused_armature_deform,
        'APPLY_MODIFIERS_AFTER_ARMATURE_DEFORM':apply_modifiers_after_armature_deform,
        'EXPORT_PACKED_IMAGES':export_packed_images,
        'EXPORT_PACKED_IMAGES_DIR':export_packed_images_dir,
        'GLOBAL_MATRIX':global_matrix,
        'PATH_MODE':path_mode
    })
    
    # Exit edit mode before exporting, so current object states are exported properly.
    if bpy.ops.object.mode_set.poll():
        bpy.ops.object.mode_set(mode='OBJECT')

    if use_selection:
        objects = context.selected_objects
        if include_armatures_from_selection:
            writer.add_target_objects(
                armature for armature in (
                    obj.find_armature() for obj in objects
                ) if armature and armature not in objects
            )
    elif use_collection: # 2.80+
        objects = use_collection.all_objects
    else:
        objects = context.scene.objects
    writer.add_target_objects(objects)

    # EXPORT THE FILE.
    writer.write(filepath)
    
    return {'FINISHED'}
