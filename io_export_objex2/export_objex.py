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
        'EXPORT_SMOOTH_GROUPS': False,
        'EXPORT_SMOOTH_GROUPS_BITFLAGS': False,
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
        'KEEP_VERTEX_ORDER': False,
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
    
    def write_uvs(self, mesh, face_index_pairs):
        fw = self.fw_objex
        
        uv_unique_count = 0
        loops = mesh.loops
        uv_layer = mesh.uv_layers.active.data[:]
        
        # in case removing some of these dont get defined.
        uv = f_index = uv_index = uv_key = uv_val = uv_ls = None

        uv_face_mapping = [None] * len(face_index_pairs)

        uv_dict = {}
        uv_get = uv_dict.get
        for f, f_index in face_index_pairs:
            uv_ls = uv_face_mapping[f_index] = []
            for uv_index, l_index in enumerate(f.loop_indices):
                uv = uv_layer[l_index].uv
                # include the vertex index in the key so we don't share UV's between vertices,
                # allowed by the OBJ spec but can cause issues for other importers, see: T47010.

                # this works too, shared UV's for all verts
                #~ uv_key = veckey2d(uv)
                uv_key = loops[l_index].vertex_index, roundVect2d(uv, 6)

                uv_val = uv_get(uv_key)
                if uv_val is None:
                    uv_val = uv_dict[uv_key] = uv_unique_count
                    fw('vt %.6f %.6f\n' % uv[:])
                    uv_unique_count += 1
                uv_ls.append(uv_val)
        
        return uv_face_mapping, uv_unique_count
    
    def write_normals(self, mesh, face_index_pairs):
        fw = self.fw_objex
        
        no_unique_count = 0
        loops = mesh.loops
        
        no_key = no_val = None
        normals_to_idx = {}
        no_get = normals_to_idx.get
        loops_to_normals = [0] * len(loops)
        for f, f_index in face_index_pairs:
            for l_idx in f.loop_indices:
                no_key = roundVect3d(loops[l_idx].normal, 4)
                no_val = no_get(no_key)
                if no_val is None:
                    no_val = normals_to_idx[no_key] = no_unique_count
                    fw('vn %.4f %.4f %.4f\n' % no_key)
                    no_unique_count += 1
                loops_to_normals[l_idx] = no_val
        return loops_to_normals, no_unique_count
    
    def write_vertex_colors(self, mesh, face_index_pairs):
        if not len(mesh.vertex_colors):
            return None, 0
        
        fw = self.fw_objex
        
        vc_unique_count = 0
        loops = mesh.loops
        loop_colors = mesh.vertex_colors.active.data[:] # 421todo allow choosing a layer
        
        vc_key = vc_val = None
        vertex_colors_to_idx = {}
        loops_to_vertex_colors = [0] * len(loops)
        for f, f_index in face_index_pairs:
            for l_idx in f.loop_indices:
                color = loop_colors[l_idx].color
                # 3 digits: 1/256 ~ 0.0039
                if len(color) == 3:
                    # default to alpha = 1 (opaque)
                    vc_key = (round(color[0], 3), round(color[1], 3), round(color[2], 3), 1.0)
                else: # 4 (alpha)
                    vc_key = (round(color[0], 3), round(color[1], 3), round(color[2], 3), round(color[3], 3))
                vc_val = vertex_colors_to_idx.get(vc_key)
                if vc_val is None:
                    vc_val = vertex_colors_to_idx[vc_key] = vc_unique_count
                    fw('vc %.3f %.3f %.3f %.3f\n' % vc_key)
                    vc_unique_count += 1
                loops_to_vertex_colors[l_idx] = vc_val
        return loops_to_vertex_colors, vc_unique_count
    
    def write_object(self, progress, ob, ob_mat):
        log = self.log
        fw = self.fw_objex
        scene = self.context.scene
        
        with ProgressReportSubstep(progress, 6) as subprogress2:

            if self.options['EXPORT_SKEL'] and ob.type == 'ARMATURE':
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
                self.armatures.append((util.quote(ob.name), ob, ob_mat, actions))

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
                    if modifier.type == 'ARMATURE' and rigged_to_armature and (
                        # don't apply armature deform (aka disable modifier) if armature is exported,
                        # or if the armature deform should be applied for armatures that aren't exported ("UNUSED")
                        rigged_to_armature in self.objects or not self.options['APPLY_UNUSED_ARMATURE_DEFORM']
                    ):
                        if modifier.object == rigged_to_armature:
                            if found_armature_deform:
                                log.warning('Found several armature deform modifiers on object {} using armature {}',
                                    ob.name, rigged_to_armature.name)
                            found_armature_deform = True
                            disable_modifier = True
                        else:
                            log.warning('Object {} was found to be rigged to {} but it also has an armature deform modifier using {}',
                                ob.name, rigged_to_armature.name, modifier.object.name if modifier.object else None)
                    modifier_show = None
                    if disable_modifier:
                        modifier_show = False
                    elif using_depsgraph:
                        modifier_show = modifier.show_render if self.options['APPLY_MODIFIERS_RENDER'] else modifier.show_viewport
                    if modifier_show is not None:
                        user_show_armature_modifiers.append((modifier, modifier.show_viewport, modifier.show_render))
                        modifier.show_viewport = modifier_show
                        modifier.show_render = modifier_show

            if using_depsgraph: # 2.80+
                depsgraph = self.context.evaluated_depsgraph_get()
                ob_for_convert = ob.evaluated_get(depsgraph) if apply_modifiers else ob.original
                del depsgraph
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

            if self.options['EXPORT_UV']:
                if hasattr(me, 'uv_textures'): # < 2.80
                    has_uvs = len(me.uv_textures) > 0
                    has_uv_textures = has_uvs
                    if has_uv_textures:
                        uv_texture = me.uv_textures.active.data[:]
                else: # 2.80+
                    has_uvs = len(me.uv_layers) > 0
                    has_uv_textures = False
            else:
                has_uvs = False
            
            vertices = me.vertices[:]

            # Make our own list so it can be sorted to reduce context switching
            face_index_pairs = [(face, index) for index, face in enumerate(me.polygons)]
            # faces = [ f for f in me.tessfaces ]

            if not (len(face_index_pairs) + len(vertices)):  # Make sure there is something to write
                # clean up
                if not ob_for_convert: # < 2.80
                    bpy.data.meshes.remove(me)
                else: # 2.80+
                    ob_for_convert.to_mesh_clear()
                return  # dont bother with this mesh.

            if self.options['EXPORT_NORMALS'] and face_index_pairs:
                me.calc_normals_split()
                # No need to call me.free_normals_split later, as this mesh is deleted anyway!

            if self.options['EXPORT_SMOOTH_GROUPS'] and face_index_pairs:
                smooth_groups, smooth_groups_tot = me.calc_smooth_groups(self.options['EXPORT_SMOOTH_GROUPS_BITFLAGS'])
                if smooth_groups_tot <= 1:
                    smooth_groups, smooth_groups_tot = (), 0
            else:
                smooth_groups, smooth_groups_tot = (), 0

            materials = me.materials[:]
            use_materials = materials and self.options['EXPORT_MTL']

            # Sort by Material, then images
            # so we dont over context switch in the obj file.
            if self.options['KEEP_VERTEX_ORDER']:
                pass
            else:
                if has_uv_textures:
                    if smooth_groups:
                        sort_func = lambda a: (a[0].material_index,
                                               hash(uv_texture[a[1]].image),
                                               smooth_groups[a[1]] if a[0].use_smooth else False)
                    else:
                        sort_func = lambda a: (a[0].material_index,
                                               hash(uv_texture[a[1]].image),
                                               a[0].use_smooth)
                elif len(materials) > 1:
                    if smooth_groups:
                        sort_func = lambda a: (a[0].material_index,
                                               smooth_groups[a[1]] if a[0].use_smooth else False)
                    else:
                        sort_func = lambda a: (a[0].material_index,
                                               a[0].use_smooth)
                else:
                    # no materials
                    if smooth_groups:
                        sort_func = lambda a: smooth_groups[a[1] if a[0].use_smooth else False]
                    else:
                        sort_func = lambda a: a[0].use_smooth

                face_index_pairs.sort(key=sort_func)

                del sort_func

            util.detect_zztag(log, ob.name)
            fw('g %s\n' % util.quote(ob.name))

            # rig_is_exported is used to avoid referencing a skeleton or bones which aren't exported
            rig_is_exported = self.options['EXPORT_SKEL'] and (rigged_to_armature in self.objects)

            if ob.type == 'MESH':
                objex_data = ob.data.objex_bonus # ObjexMeshProperties
                if objex_data.priority != 0:
                    fw('priority %d\n' % objex_data.priority)
                if objex_data.write_origin == 'YES' or (
                    objex_data.write_origin == 'AUTO'
                    and objex_data.attrib_billboard != 'NONE'
                ):
                    fw('origin %.6f %.6f %.6f\n'
                        % tuple(blender_version_compatibility.matmul(self.options['GLOBAL_MATRIX'], ob.location)))
                if objex_data.attrib_billboard != 'NONE':
                    fw('attrib %s\n' % objex_data.attrib_billboard)
                for attrib in ('POSMTX', 'PROXY'):
                    if getattr(objex_data, 'attrib_%s' % attrib):
                        fw('attrib %s\n' % attrib)
                # export those attributes when the properties are shown in the ui, that is when the mesh is rigged
                if rigged_to_armature:
                    for attrib in ('LIMBMTX', 'NOSPLIT', 'NOSKEL'):
                        if getattr(objex_data, 'attrib_%s' % attrib):
                            if rig_is_exported:
                                fw('attrib %s\n' % attrib)
                            else:
                                log.warning('Mesh {} is rigged to armature {} and sets {},\n'
                                    'but that armature is not being exported. Skipped exporting the attribute.\n'
                                    '(you are likely exporting Selection Only, unchecked Used armatures, and did not select the armature)',
                                    ob.name, rigged_to_armature.name, attrib)

            subprogress2.step()

            if self.options['EXPORT_WEIGHTS']:
                # Retrieve the list of vertex groups
                vertGroupNames = ob.vertex_groups.keys()
                vertex_groups = None
                if vertGroupNames:
                    # Create a dictionary keyed by vertex id and listing, for each vertex, the name of the vertex groups it belongs to, and its associated weight
                    vertex_groups = [[] for _i in range(len(vertices))]
                    for v_idx, v_ls in enumerate(vertex_groups):
                        v_ls[:] = [(vertGroupNames[g.group], util.quote(vertGroupNames[g.group]), g.weight) for g in vertices[v_idx].groups]
                del vertGroupNames

            # Vert
            if rigged_to_armature and rig_is_exported:
                fw('useskel %s\n' % util.quote(rigged_to_armature.name))
            if self.options['EXPORT_WEIGHTS'] and vertex_groups and rigged_to_armature and rig_is_exported:
                # only write vertex groups named after actual bones
                bone_names = [bone.name for bone in rigged_to_armature.data.bones]
                bone_vertex_groups = [
                    [(group_name_q, weight) for group_name, group_name_q, weight in vertex_vertex_groups if group_name in bone_names]
                    for vertex_vertex_groups in vertex_groups
                ]
                # only group of maximum weight, with weight 1
                if self.options['UNIQUE_WEIGHTS']:
                    for v in vertices:
                        groups = bone_vertex_groups[v.index] # list of (group_name_q, group_weight) tuples for that vertex
                        if groups:
                            group_name_q, weight = max(groups, key=lambda _g: _g[1])
                            fw('%s %s\n' % (
                                'v %.6f %.6f %.6f' % v.co[:],
                                'weight %s 1' % group_name_q
                            ))
                        else:
                            fw('v %.6f %.6f %.6f\n' % v.co[:])
                # all (non-zero) weights
                else:
                    for v in vertices:
                        fw('%s%s\n' % (
                            'v %.6f %.6f %.6f' % v.co[:],
                            ','.join([' weight %s %.3f' % (group_name_q, weight) for group_name_q, weight in bone_vertex_groups[v.index] if weight != 0])
                        ))
            # no weights
            else:
                for v in vertices:
                    fw('v %.6f %.6f %.6f\n' % v.co[:])

            subprogress2.step()

            # UV
            if has_uvs:
                uv_face_mapping, uv_unique_count = self.write_uvs(me, face_index_pairs)
            else:
                uv_unique_count = 0
            
            subprogress2.step()

            # NORMAL, Smooth/Non smoothed.
            if self.options['EXPORT_NORMALS']:
                loops_to_normals, no_unique_count = self.write_normals(me, face_index_pairs)
                has_normals = True
            else:
                no_unique_count = 0
                has_normals = False
            
            if self.options['EXPORT_VERTEX_COLORS']:
                loops_to_vertex_colors, vc_unique_count = self.write_vertex_colors(me, face_index_pairs)
                has_vertex_colors = loops_to_vertex_colors is not None
            else:
                has_vertex_colors = False
                vc_unique_count = 0

            subprogress2.step()

            # those context_* variables are used to keep track of the last g/usemtl/s directive written, according to options
            # Set the default mat to no material and no image.
            context_material = context_face_image = 0  # Can never be this, so we will label a new material the first chance we get. used for usemtl directives if EXPORT_MTL
            context_smooth = None  # Will either be true or false,  set bad to force initialization switch. with EXPORT_SMOOTH_GROUPS, has effects on writing the s directive

            for f, f_index in face_index_pairs:
                f_smooth = f.use_smooth
                if f_smooth and smooth_groups:
                    f_smooth = smooth_groups[f_index]

                face_material = materials[f.material_index] if use_materials else None
                face_image = uv_texture[f_index].image if has_uv_textures else None

                # we do not need to switch context when the face image changes if
                # the (objex) material doesn't change, as the face image is completely ignored
                # when using objex materials
                if face_material and face_material.objex_bonus.is_objex_material:
                    face_image = None

                # if context hasn't changed, do nothing
                if context_material == face_material and context_face_image == face_image:
                    pass
                else:
                    # update context
                    context_material = face_material
                    context_face_image = face_image

                    # clear context
                    if face_material is None and face_image is None:
                        if self.options['EXPORT_MTL']:
                            fw('clearmtl\n')
                    # new context
                    else:
                        # mtl_dict is {(material, image): (name, name_q, material, face_image)}
                        data = self.mtl_dict.get((face_material, face_image))
                        if data:
                            name_q = data[1]
                        else:
                            # new (material, image) pair, find a new unique name for it
                            name_base = face_material.name if face_material else 'None'
                            if face_image:
                                name_base = '%s %s' % (name_base, face_image.name)
                            name = name_base
                            i = 0
                            while name in (_name for (_name, _name_q, _material, _face_image) in self.mtl_dict.values()):
                                i += 1
                                name = '%s %d' % (name_base, i)
                            name_q = util.quote(name)
                            # remember the pair
                            self.mtl_dict[(face_material, face_image)] = name, name_q, face_material, face_image

                            if self.options['EXPORT_MTL']:
                                objectUseCollision = ob.name.startswith('collision.')
                                # 421fixme
                                # if the export is done right after material initialization, material properties
                                # are for some reason still reading the old values. They update at least
                                # when modifying objex_bonus properties in the UI or renaming the material
                                # context.view_layer.update() doesn't help
                                if objectUseCollision and not face_material.objex_bonus.is_objex_material:
                                    raise util.ObjexExportAbort(
                                        'Object {} is for collision (has "collision." prefix) '
                                        'but material {} used by this object is not for collision '
                                        '(not even initialized as an objex material)'
                                        .format(ob.name, face_material.name)
                                    )
                                if objectUseCollision and not face_material.objex_bonus.use_collision:
                                    raise util.ObjexExportAbort(
                                        'Object {} is for collision (has "collision." prefix) '
                                        'but material {} used by this object is not for collision'
                                        .format(ob.name, face_material.name)
                                    )
                                if not objectUseCollision and face_material.objex_bonus.use_collision:
                                    raise util.ObjexExportAbort(
                                        'Object {} is not for collision (does not have "collision." prefix) '
                                        'but material {} used by this object is for collision'
                                        .format(ob.name, face_material.name)
                                    )

                        if self.options['EXPORT_MTL']:
                            fw('usemtl %s\n' % name_q)

                if f_smooth != context_smooth:
                    if f_smooth:  # on now off
                        if smooth_groups:
                            f_smooth = smooth_groups[f_index]
                            fw('s %d\n' % f_smooth)
                        else:
                            fw('s 1\n')
                    else:  # was off now on
                        fw('s off\n')
                    context_smooth = f_smooth

                f_v = [(vi, vertices[v_idx], l_idx)
                       for vi, (v_idx, l_idx) in enumerate(zip(f.vertices, f.loop_indices))]

                fw('f')
                for vi, v, li in f_v:
                    f_v_data = []
                    f_v_data.append(self.total_vertex + v.index)
                    if has_uvs:
                        f_v_data.append(self.total_uv + uv_face_mapping[f_index][vi])
                    if has_normals:
                        f_v_data += [None] * (2 - len(f_v_data))
                        f_v_data.append(self.total_normal + loops_to_normals[li])
                    if has_vertex_colors:
                        f_v_data += [None] * (3 - len(f_v_data))
                        f_v_data.append(self.total_vertex_color + loops_to_vertex_colors[li])
                    # v[/vt[/vn[/vc]]] coordinates/uv/normal/color
                    fw(' %s' % '/'.join(['' if _i is None else ('%d' % _i) for _i in f_v_data]))
                fw('\n')

            subprogress2.step()

            # Make the indices global rather then per mesh
            self.total_vertex += len(vertices)
            self.total_uv += uv_unique_count
            self.total_normal += no_unique_count
            self.total_vertex_color += vc_unique_count
            
            # clean up
            if not ob_for_convert: # < 2.80
                bpy.data.meshes.remove(me)
            else: # 2.80+
                ob_for_convert.to_mesh_clear()
    
    def write(self, filepath):
        """
        This function starts the exporting. It defines a few "globals" as class members, notably the total_* variables
        It loops through objects, writing each to .objex (with the write_object method), and collecting materials/armatures/animations as it goes.
        Once the .objex is finished being written, write_mtl is called to write the .mtl and same thing with write_anim which writes .anim and itself calls .skel which writes .skel
        """
        log = self.log
        self.filepath = filepath
        with ProgressReport(self.context.window_manager) as progress:
            scene = self.context.scene

            # Exit edit mode before exporting, so current object states are exported properly.
            if bpy.ops.object.mode_set.poll():
                bpy.ops.object.mode_set(mode='OBJECT')

            # EXPORT THE FILE.
            progress.enter_substeps(1)
            
            with ProgressReportSubstep(progress, 3, "Objex Export path: %r" % filepath, "Objex Export Finished") as subprogress1:
                with open(filepath, "w", encoding="utf8", newline="\n") as f:
                    self.fw_objex = f.write

                    # write leading comments, mtllib/animlib/skellib directives, and defines filepath_* to write .mtl/... to
                    self.write_header()

                    # Initialize totals, these are updated each object
                    self.total_vertex = self.total_uv = self.total_normal = self.total_vertex_color = 1

                    # A Dict of Materials
                    # "materials" here refer to a material + face image pair, where either or both may be unset
                    # (material, image): (name, name_q, material, face_image)
                    # name_q = util.quote(name)
                    self.mtl_dict = {}

                    copy_set = set()

                    self.armatures = []
                    
                    # Get all meshes
                    subprogress1.enter_substeps(len(self.objects))
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
                            # evaluated_depsgraph_get may be called in-between this line executing,
                            # ie in write_object when evaluating mesh data, so call it again every time here
                            depsgraph = self.context.evaluated_depsgraph_get()
                            obs += [(dup.instance_object.original, dup.matrix_world.copy())
                                    for dup in depsgraph.object_instances
                                    if dup.parent and dup.parent.original == ob_main]
                            del depsgraph
                        else:
                            added_dupli_children = False
                        if added_dupli_children:
                            log.debug('{} has {:d} dupli children', ob_main.name, len(obs) - 1)

                        subprogress1.enter_substeps(len(obs))
                        for ob, ob_mat in obs:
                            self.write_object(subprogress1, ob, ob_mat)

                        if use_old_dupli and ob_main.dupli_type != 'NONE':
                            ob_main.dupli_list_clear()
                        elif not use_old_dupli:
                            pass # no clean-up needed

                        subprogress1.leave_substeps("Finished writing geometry of '%s'." % ob_main.name)
                    subprogress1.leave_substeps()

                del self.fw_objex
                
                subprogress1.step("Finished exporting geometry, now exporting materials")

                # Now we have all our materials, save them
                if self.options['EXPORT_MTL']:
                    def append_header_mtl(fw_mtl):
                        fw_mtl(self.export_id_line)
                    export_objex_mtl.write_mtl(scene, self.filepath_mtl, append_header_mtl, self.options, copy_set, self.mtl_dict)
                
                subprogress1.step("Finished exporting materials, now exporting skeletons/animations")

                # save gathered skeletons and animations
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
                            scene, self.options['GLOBAL_MATRIX'], self.armatures, 
                            link_anim_basepath, self.options['LINK_BIN_SCALE'])
                    finally:
                        if skelfile:
                            skelfile.close()
                        if animfile:
                            animfile.close()
                
                # copy all collected files.
                bpy_extras.io_utils.path_reference_copy(copy_set)

            progress.leave_substeps()


def save(context,
         filepath,
         *,
         use_triangles=None,
         use_normals=None,
         use_vertex_colors=None,
         use_smooth_groups=None,
         use_smooth_groups_bitflags=None,
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
         keep_vertex_order=None,
         use_vertex_groups=None,
         export_packed_images=None,
         export_packed_images_dir=None,
         use_selection=None,
         use_collection=None,
         include_armatures_from_selection=True,
         global_matrix=None,
         path_mode=None
         ):

    objex_writer = ObjexWriter(context)
    objex_writer.set_options({
        'TRIANGULATE':use_triangles,
        'EXPORT_SMOOTH_GROUPS':use_smooth_groups,
        'EXPORT_SMOOTH_GROUPS_BITFLAGS':use_smooth_groups_bitflags,
        'EXPORT_NORMALS':use_normals,
        'EXPORT_VERTEX_COLORS':use_vertex_colors,
        'EXPORT_UV':use_uvs,
        'EXPORT_MTL':use_materials,
        'EXPORT_SKEL':use_skeletons,
        'EXPORT_ANIM':use_animations,
        'EXPORT_LINK_ANIM_BIN':link_anim_bin,
        'EXPORT_WEIGHTS':use_weights,
        'UNIQUE_WEIGHTS':use_unique_weights,
        'APPLY_MODIFIERS':use_mesh_modifiers,
        'APPLY_MODIFIERS_RENDER':use_mesh_modifiers_render,
        'APPLY_UNUSED_ARMATURE_DEFORM':apply_unused_armature_deform,
        'APPLY_MODIFIERS_AFTER_ARMATURE_DEFORM':apply_modifiers_after_armature_deform,
        'KEEP_VERTEX_ORDER':keep_vertex_order,
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
            objex_writer.add_target_objects(
                armature for armature in (
                    obj.find_armature() for obj in objects
                ) if armature and armature not in objects
            )
    elif use_collection: # 2.80+
        objects = use_collection.all_objects
    else:
        objects = context.scene.objects
    objex_writer.add_target_objects(objects)

    # EXPORT THE FILE.
    objex_writer.write(filepath)
    
    return {'FINISHED'}
