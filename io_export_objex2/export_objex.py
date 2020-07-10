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

# <pep8 compliant>

# 421todo see if this has any use
if 'bpy' in locals():
	import importlib
	if 'export_objex_anim' in locals():
		importlib.reload(export_objex_anim)

import os
import time

import bpy
import mathutils
import bpy_extras.io_utils

from progress_report import ProgressReport, ProgressReportSubstep

import json

from . import export_objex_anim
from .logging_util import getLogger


# 421todo this is the best easiest method I found, is it robust enough?
def string_to_literal(s):
    return json.dumps(s)

def name_compat(name):
    if name is None:
        return 'None'
    else:
        return name.replace(' ', '_')


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

def findFaceMainVertexGroup(face, vWeightMap):
    """
    Searches the vertexDict to see what groups is assigned to a given face.
    We use a frequency system in order to sort out the name because a given vetex can
    belong to two or more groups at the same time. To find the right name for the face
    we list all the possible vertex group names with their frequency and then sort by
    frequency in descend order. The top element is the one shared by the highest number
    of vertices is the face's group
    """
    weightDict = {}
    for vert_index in face.vertices:
        vWeights = vWeightMap[vert_index]
        for vGroupName, weight in vWeights:
            weightDict[vGroupName] = weightDict.get(vGroupName, 0.0) + weight

    if weightDict:
        return max((weight, vGroupName) for vGroupName, weight in weightDict.items())[1]
    else:
        return '(null)'

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
        'EXPORT_WEIGHTS': True,
        'UNIQUE_WEIGHTS': False,
        'APPLY_MODIFIERS': True,
        'APPLY_MODIFIERS_RENDER': False,
        'KEEP_VERTEX_ORDER': False,
        'EXPORT_POLYGROUPS': False,
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

        fw('version 2.000\n') # 421todo externalize, or use bl_info ?

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
                vc_key = (round(color[0], 3), round(color[1], 3), round(color[2], 3), 1.0)
                # 421todo support alpha for all blender versions (nodes)
                # 421todo confirm this does detect the blender version that supports vertex alpha
                if bpy.app.version == (2,79,7) and bpy.app.build_hash == b'10f724cec5e3':
                    vc_key[3] = round(color[3], 3)
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
                        actions = [item.action for item in objex_data.export_actions if item.action]
                    self.armatures.append((ob, actions))
                else:
                    self.armatures.append((ob, []))
            
            apply_modifiers = self.options['APPLY_MODIFIERS']
            # disable armature deform modifiers
            if apply_modifiers:
                user_show_armature_modifiers = []
                for modifier in ob.modifiers:
                    if modifier.type == 'ARMATURE':
                        # 421todo not sure armature deform could be used for anything other than main animation?
                        # and modifier.object == ob.parent
                        user_show_armature_modifiers.append((modifier, modifier.show_viewport, modifier.show_render))
                        modifier.show_viewport = False
                        modifier.show_render = False
            try:
                me = ob.to_mesh(scene, apply_modifiers, calc_tessface=False,
                                settings='RENDER' if self.options['APPLY_MODIFIERS_RENDER'] else 'PREVIEW')
            except RuntimeError:
                me = None
            finally:
                # restore modifiers properties
                if apply_modifiers:
                    for modifier, user_show_viewport, user_show_render in user_show_armature_modifiers:
                        modifier.show_viewport = user_show_viewport
                        modifier.show_render = user_show_render
            del apply_modifiers
            
            if me is None:
                return

            # _must_ do this before applying transformation, else tessellation may differ
            if self.options['TRIANGULATE']:
                # _must_ do this first since it re-allocs arrays
                mesh_triangulate(me)
            
            # 421todo apply ob_mat in animations if object is animated
            # 421fixme (assuming has parent armature = animated ...)
            # 421fixme scale should still be applied here as it cannot be part of animation data
            """
            421todo
            apply scale here
            apply translation to root_bone in loc
            apply rotation to bones in rot
            """
            # 421fixme is self.options['EXPORT_ANIM'] the right check? animations may come from some other source
            """
            options['DEFORMED_MESH_STRATEGY']
            -> 'WRITE_WORLD' write world coordinates for every mesh including ones deformed by armature (may break animations if world space != object space)
            -> 'WRITE_OBJECT_TRANSFORM_IN_ANIMATION' write object coordinates for animated meshs and apply transforms in animation data (would result in world space used as model space, aka WYSIWYG)
            -> 'WRITE_OBJECT_IGNORE_TRANSFORM' write object coordinates for animated meshs and ignore transform (would result in object space used as model space, may be useful for several animated meshs in one scene, so they are not stacked at world origin but still use 0,0,0 as origin when drawn in-game)
            ?
            -> 2 checkboxes? first "always apply object transform when writing mesh data of an animated mesh" (default unchecked) if unchecked 2nd appears "apply object transform to animations instead" (default checked)
            """
            if self.options['EXPORT_ANIM'] and ob.find_armature():
                log.info('Writing mesh data for {} in object space as it seems animated', ob.name)
                me.transform(self.options['GLOBAL_MATRIX'])
            else:
                me.transform(self.options['GLOBAL_MATRIX'] * ob_mat)
            # If negative scaling, we have to invert the normals...
            if ob_mat.determinant() < 0.0:
                me.flip_normals()

            if self.options['EXPORT_UV']:
                has_uvs = len(me.uv_textures) > 0
                if has_uvs:
                    uv_texture = me.uv_textures.active.data[:]
                    #uv_layer = me.uv_layers.active.data[:]
            else:
                has_uvs = False
            
            vertices = me.vertices[:]

            # Make our own list so it can be sorted to reduce context switching
            face_index_pairs = [(face, index) for index, face in enumerate(me.polygons)]
            # faces = [ f for f in me.tessfaces ]

            if not (len(face_index_pairs) + len(vertices)):  # Make sure there is something to write
                # clean up
                bpy.data.meshes.remove(me)
                return  # dont bother with this mesh.

            if self.options['EXPORT_NORMALS'] and face_index_pairs:
                me.calc_normals_split()
                # No need to call me.free_normals_split later, as this mesh is deleted anyway!

            #loops = me.loops

            if (self.options['EXPORT_SMOOTH_GROUPS'] or self.options['EXPORT_SMOOTH_GROUPS_BITFLAGS']) and face_index_pairs:
                smooth_groups, smooth_groups_tot = me.calc_smooth_groups(self.options['EXPORT_SMOOTH_GROUPS_BITFLAGS'])
                if smooth_groups_tot <= 1:
                    smooth_groups, smooth_groups_tot = (), 0
            else:
                smooth_groups, smooth_groups_tot = (), 0

            materials = me.materials[:]
            material_names = [m.name if m else None for m in materials]

            # avoid bad index errors
            if not materials:
                materials = [None]
                material_names = [name_compat(None)]

            # Sort by Material, then images
            # so we dont over context switch in the obj file.
            if self.options['KEEP_VERTEX_ORDER']:
                pass
            else:
                if has_uvs:
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

            obnamestring = name_compat(ob.name)
            fw('g %s\n' % obnamestring)
            del obnamestring

            subprogress2.step()

            # XXX
            has_polygroups = self.options['EXPORT_POLYGROUPS']
            if has_polygroups or self.options['EXPORT_WEIGHTS']:
                # Retrieve the list of vertex groups
                vertGroupNames = ob.vertex_groups.keys()
                vertex_groups = None
                if vertGroupNames:
                    # Create a dictionary keyed by vertex id and listing, for each vertex, the name of the vertex groups it belongs to, and its associated weight
                    vertex_groups = [[] for _i in range(len(vertices))]
                    for v_idx, v_ls in enumerate(vertex_groups):
                        v_ls[:] = [(vertGroupNames[g.group], g.weight) for g in vertices[v_idx].groups]
                else:
                    has_polygroups = False
                del vertGroupNames

            # Vert
            is_rigged = ob.parent and ob.parent.type == 'ARMATURE'
            if is_rigged:
                fw('useskel %s\n' % string_to_literal(ob.parent.name))
            if self.options['EXPORT_WEIGHTS'] and vertex_groups and is_rigged:
                # only write vertex groups named after actual bones
                armature = ob.parent
                bone_names = [bone.name for bone in armature.data.bones]
                bone_vertex_groups = [
                    [(group_name, weight) for group_name, weight in vertex_vertex_groups if group_name in bone_names]
                    for vertex_vertex_groups in vertex_groups
                ]
                # only group of maximum weight, with weight 1
                if self.options['UNIQUE_WEIGHTS']:
                    for v in vertices:
                        groups = bone_vertex_groups[v.index] # list of (group_name, group_weight) tuples for that vertex
                        if groups:
                            group_name, weight = max(groups, key=lambda _g: _g[1])
                            fw('%s %s\n' % (
                                'v %.6f %.6f %.6f' % v.co[:],
                                'weight %s 1' % (string_to_literal(group_name))
                            ))
                        else:
                            fw('v %.6f %.6f %.6f\n' % v.co[:])
                # all (non-zero) weights
                else:
                    for v in vertices:
                        fw('%s%s\n' % (
                            'v %.6f %.6f %.6f' % v.co[:],
                            ','.join([' weight %s %.3f' % (string_to_literal(group_name), weight) for group_name, weight in bone_vertex_groups[v.index] if weight != 0])
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
            
            if not has_uvs:
                f_image = None

            subprogress2.step()

            # those context_* variables are used to keep track of the last g/usemtl/s directive written, according to options
            # Set the default mat to no material and no image.
            context_vertex_group = '' # g written if EXPORT_POLYGROUPS (has_polygroups)
            context_material_name = context_texture_name = 0  # Can never be this, so we will label a new material the first chance we get. used for usemtl directives if EXPORT_MTL
            context_smooth = None  # Will either be true or false,  set bad to force initialization switch. with EXPORT_SMOOTH_GROUPS or EXPORT_SMOOTH_GROUPS_BITFLAGS, has effects on writing the s directive

            for f, f_index in face_index_pairs:
                f_smooth = f.use_smooth
                if f_smooth and smooth_groups:
                    f_smooth = smooth_groups[f_index]
                f_mat = min(f.material_index, len(materials) - 1)

                if has_uvs:
                    tface = uv_texture[f_index]
                    f_image = tface.image

                # Write the vertex group
                if has_polygroups:
                    # find what vertext group the face belongs to
                    vgroup_of_face = findFaceMainVertexGroup(f, vertex_groups)
                    if vgroup_of_face != context_vertex_group:
                        context_vertex_group = vgroup_of_face
                        fw('g %s\n' % vgroup_of_face)
                    del vgroup_of_face

                # make current context
                current_material_name = material_names[f_mat]
                if has_uvs and f_image:
                    current_texture_name = f_image.name
                else:
                    current_texture_name = None  # No image, use None instead.

                # CHECK FOR CONTEXT SWITCH
                if current_material_name == context_material_name and current_texture_name == context_texture_name:
                    pass  # Context already switched, dont do anything
                else:
                    if current_material_name is None and current_texture_name is None:
                        # Write a null material, since we know the context has changed.
                        if self.options['EXPORT_MTL']:
                            fw("usemtl (null)\n")  # mat, image

                    else:
                        current_key = (current_material_name,current_texture_name)
                        mat_data = self.mtl_dict.get(current_key)
                        if not mat_data:
                            # First add to global dict so we can export to mtl
                            # Then write mtl

                            # Make a new names from the mat and image name,
                            # converting any spaces to underscores with name_compat.

                            # If none image dont bother adding it to the name
                            # Try to avoid as much as possible adding texname (or other things)
                            # to the mtl name (see [#32102])...
                            mtl_name = "%s" % name_compat(current_material_name)
                            if self.mtl_rev_dict.get(mtl_name, None) not in {current_key, None}:
                                if current_texture_name is None:
                                    tmp_ext = "_NONE"
                                else:
                                    tmp_ext = "_%s" % name_compat(current_texture_name)
                                i = 0
                                while self.mtl_rev_dict.get(mtl_name + tmp_ext, None) not in {current_key, None}:
                                    i += 1
                                    tmp_ext = "_%3d" % i
                                mtl_name += tmp_ext
                            mat_data = self.mtl_dict[current_key] = mtl_name, materials[f_mat], f_image
                            self.mtl_rev_dict[mtl_name] = current_key

                        if self.options['EXPORT_MTL']:
                            fw("usemtl %s\n" % mat_data[0])  # can be mat_image or (null)

                context_material_name = current_material_name
                context_texture_name = current_texture_name
                
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
            bpy.data.meshes.remove(me)
    
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
                    # (material.name, image.name):matname_imagename # matname_imagename has gaps removed.
                    self.mtl_dict = {}
                    # Used to reduce the usage of matname_texname materials, which can become annoying in case of
                    # repeated exports/imports, yet keeping unique mat names per keys!
                    # mtl_name: (material.name, image.name)
                    self.mtl_rev_dict = {}

                    copy_set = set()

                    self.armatures = []
                    
                    # Get all meshes
                    subprogress1.enter_substeps(len(self.objects))
                    for ob_main in self.objects:
                        # 421todo I don't know what this dupli stuff is about
                        # ignore dupli children
                        if ob_main.parent and ob_main.parent.dupli_type in {'VERTS', 'FACES'}:
                            # XXX
                            subprogress1.step("Ignoring %s, dupli child..." % ob_main.name)
                            continue

                        obs = [(ob_main, ob_main.matrix_world)]
                        if ob_main.dupli_type != 'NONE':
                            # XXX
                            log.info('creating dupli_list on {}', ob_main.name)
                            ob_main.dupli_list_create(scene)

                            obs += [(dob.object, dob.matrix) for dob in ob_main.dupli_list]

                            # XXX
                            log.debug('{} has {:d} dupli children', ob_main.name, len(obs) - 1)

                        subprogress1.enter_substeps(len(obs))
                        for ob, ob_mat in obs:
                            self.write_object(subprogress1, ob, ob_mat)

                        if ob_main.dupli_type != 'NONE':
                            ob_main.dupli_list_clear()

                        subprogress1.leave_substeps("Finished writing geometry of '%s'." % ob_main.name)
                    subprogress1.leave_substeps()

                del self.fw_objex
                
                subprogress1.step("Finished exporting geometry, now exporting materials")

                # Now we have all our materials, save them
                if self.options['EXPORT_MTL']:
                    def append_header_mtl(fw_mtl):
                        fw_mtl(self.export_id_line)
                    write_mtl(scene, self.filepath_mtl, append_header_mtl, self.options, copy_set, self.mtl_dict)
                
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
                        if self.options['EXPORT_ANIM']:
                            log.info(' ... and animations')
                            animfile = open(self.filepath_anim, "w", encoding="utf8", newline="\n")
                            animfile_write = animfile.write
                            animfile_write(self.export_id_line)
                        else:
                            animfile_write = None
                        export_objex_anim.write_armatures(skelfile_write, animfile_write, scene, self.options['GLOBAL_MATRIX'], self.armatures)
                    finally:
                        if skelfile:
                            skelfile.close()
                        if animfile:
                            animfile.close()
                
                # copy all collected files.
                bpy_extras.io_utils.path_reference_copy(copy_set)

            progress.leave_substeps()


class ObjexMaterialNodeTreeExplorer():
    def __init__(self, tree):
        self.log = getLogger('ObjexMaterialNodeTreeExplorer')
        self.tree = tree
        self.colorCycles = []
        self.alphaCycles = []
        self.flagSockets = {}
        self.defaulFlagColorCycle = 'G_CCMUX_0'
        self.defaulFlagAlphaCycle = 'G_ACMUX_0'

    def buildFromColorCycle(self, cc):
        log = self.log
        if cc in (cc for cc,flags,prev_alpha_cycle_node in self.colorCycles):
            log.error('Looping: already visited color cycle node {!r}', cc)
            return
        flags = []
        prev_color_cycle_node = None
        prev_alpha_cycle_node = None
        for i in range(4):
            if not cc.inputs[i].links:
                flags.append(self.defaulFlagColorCycle)
                continue
            socket = cc.inputs[i].links[0].from_socket
            if socket.bl_idname != 'OBJEX_NodeSocket_CombinerOutput':
                log.error('What is this socket? not combiner output! {!r}', socket)
            flag = socket.flagColorCycle
            if not flag:
                log.error('Unsupported flag {} for input {} of {!r}', flag, 'ABCD'[i], cc)
            flags.append(flag)
            if flag == 'G_CCMUX_COMBINED':
                if prev_color_cycle_node and prev_color_cycle_node != socket.node:
                    log.error('Different color cycle nodes used for combine {!r} {!r}', prev_color_cycle_node, socket.node)
                prev_color_cycle_node = socket.node
            elif flag == 'G_CCMUX_COMBINED_ALPHA':
                if socket.node not in self.alphaCycles:
                    log.error('Color cycle {!r} is combining alpha from alpha cycle node {!r} which was not used in alpha cycles', cc, ac)
                if prev_alpha_cycle_node and prev_alpha_cycle_node != socket.node:
                    log.error('Different alpha cycle nodes used for combine {!r} {!r}', prev_alpha_cycle_node, socket.node)
                prev_alpha_cycle_node = socket.node
            else:
                storedFlagSocket = self.flagSockets.get(flag)
                if storedFlagSocket and socket != storedFlagSocket:
                    log.error('Flag {} is used by two different sockets {!r} {!r}', flag, storedFlagSocket, socket)
                self.flagSockets[flag] = socket
        self.colorCycles.append((cc, flags, prev_alpha_cycle_node))
        if prev_color_cycle_node:
            self.buildFromColorCycle(prev_color_cycle_node)

    def buildFromAlphaCycle(self, ac):
        log = self.log
        if ac in (ac for ac,flags in self.alphaCycles):
            log.error('Looping: already visited alpha cycle node {!r}', ac)
            return
        flags = []
        prev_alpha_cycle_node = None
        for i in range(4):
            if not ac.inputs[i].links:
                flags.append(self.defaulFlagAlphaCycle)
                continue
            socket = ac.inputs[i].links[0].from_socket
            if socket.bl_idname != 'OBJEX_NodeSocket_CombinerOutput':
                log.error('What is this socket? not combiner output! {!r}', socket)
            flag = socket.flagAlphaCycle
            if not flag:
                log.error('Unsupported flag {} for input {} of {!r}', flag, 'ABCD'[i], ac)
            flags.append(flag)
            if flag == 'G_ACMUX_COMBINED':
                if prev_alpha_cycle_node and prev_alpha_cycle_node != socket.node:
                    log.error('Different cycle nodes used for combine {!r} {!r}', prev_alpha_cycle_node, socket.node)
                prev_alpha_cycle_node = socket.node
            else:
                storedFlagSocket = self.flagSockets.get(flag)
                if storedFlagSocket and socket != storedFlagSocket:
                    log.error('Flag {} is used by two different sockets {!r} {!r}', flag, storedFlagSocket, socket)
                self.flagSockets[flag] = socket
        self.alphaCycles.append((ac, flags))
        if prev_alpha_cycle_node:
            self.buildFromAlphaCycle(prev_alpha_cycle_node)

    def buildCyclesFromOutput(self, output):
        log = self.log
        # 421todo a lot of checks
        # build alpha cycles first because color cycle 1 may use alpha cycle 0
        self.buildFromAlphaCycle(output.inputs[1].links[0].from_node)
        self.buildFromColorCycle(output.inputs[0].links[0].from_node)
        # check the cycles make sense
        self.colorCycles.reverse()
        self.alphaCycles.reverse()
        if len(self.colorCycles) != len(self.alphaCycles):
            log.error('Not the same amount of color ({:d}) and alpha ({:d}) cycles', len(self.colorCycles), len(self.alphaCycles))
        flags = []
        for i in range(len(self.colorCycles)):
            cc,colorFlags,prev_alpha_cycle_node = self.colorCycles[i]
            ac,alphaFlags = self.alphaCycles[i]
            if i == 0 and prev_alpha_cycle_node:
                log.error('First color cycle node {!r} is combining with alpha cycle {!r} (but the first cycle cannot use combine)', cc, prev_alpha_cycle_node)
            if i > 0 and prev_alpha_cycle_node and prev_alpha_cycle_node != self.alphaCycles[i-1][0]:
                log.error('Color cycle {:d} {!r} combines non-previous alpha cycle {!r} instead of previous alpha cycle (based on order) {!r}', i, cc, self.alphaCycles[i-1][0], prev_alpha_cycle_node)
            flags += colorFlags
            flags += alphaFlags
        self.combinerFlags = flags

    def build(self):
        log = self.log
        output = None
        for n in self.tree.nodes:
            if n.bl_idname == 'ShaderNodeOutput':
                if output:
                    log.error('Several output nodes found {!r} {!r}', output, n)
                output = n
        if not output:
            log.error('No Output node found')
        self.buildCyclesFromOutput(output)
        self.buildCombinerInputs()

    def buildCombinerInputs(self):
        log = self.log
        inputs = {
            # color registers
            'primitiveRGB': (('G_CCMUX_PRIMITIVE',),self.buildColorInputRGB),
            'primitiveA': (('G_CCMUX_PRIMITIVE_ALPHA','G_ACMUX_PRIMITIVE',),self.buildColorInputA),
            'environmentRGB': (('G_CCMUX_ENVIRONMENT',),self.buildColorInputRGB),
            'environmentA': (('G_CCMUX_ENV_ALPHA','G_ACMUX_ENVIRONMENT',),self.buildColorInputA),
            # texels
            'texel0RGB': (('G_CCMUX_TEXEL0',),self.buildTexelDataFromColorSocket),
            'texel0A': (('G_CCMUX_TEXEL0_ALPHA','G_ACMUX_TEXEL0',),self.buildTexelDataFromAlphaSocket),
            'texel1RGB': (('G_CCMUX_TEXEL1',),self.buildTexelDataFromColorSocket),
            'texel1A': (('G_CCMUX_TEXEL1_ALPHA','G_ACMUX_TEXEL1',),self.buildTexelDataFromAlphaSocket),
            # vertex colors (or nothing)
            'shadeRGB': (('G_CCMUX_SHADE',),self.buildShadingDataFromColorSocket),
            'shadeA': (('G_CCMUX_SHADE_ALPHA','G_ACMUX_SHADE',),self.buildShadingDataFromAlphaSocket),
        }
        self.data = {}
        log.debug('per-flag used sockets: {!r}', self.flagSockets)
        for k,(flags,socketReader) in inputs.items():
            sockets = set(self.flagSockets[flag] for flag in flags if flag in self.flagSockets)
            if len(sockets) > 1:
                log.error('Different sockets {!r} are used by different flags {!r} but these flags should refer to the same data {}', sockets, flags, k)
            if sockets:
                socket = next(iter(sockets))
                log.debug('getting {} from {!r}', k, socket)
                socketReader(k, socket)
        # FIXME
        def mergeRGBA(rgb, a):
            return (rgb[0], rgb[1], rgb[2], a)
        def mergeRGBA1(rgb):
            return (rgb[0], rgb[1], rgb[2], 1)
        def mergeRGBA2(a):
            return (1,1,1,a)
        def mergeSame(d1, d2):
            if d1 != d2:
                raise ValueError('Merging mismatching data\nd1 = {!r}\nd2 = {!r}'.format(d1,d2))
            return d1
        id = lambda x:x
        merge = {
            'primitive': (('primitiveRGB','primitiveA',),mergeRGBA,mergeRGBA1,mergeRGBA2),
            'environment': (('environmentRGB','environmentA',),mergeRGBA,mergeRGBA1,mergeRGBA2),
            # FIXME check texel0RGB and texel0A are the same, and other checks
            'texel0': (('texel0RGB','texel0A',),mergeSame,id,id),
            'texel1': (('texel1RGB','texel1A',),mergeSame,id,id),
            'shade': (('shadeRGB','shadeA',),mergeSame,id,id),
        }
        data = self.data
        log.debug('data before merge: {!r}', data)
        mergedData = {}
        # FIXME ugly
        for k2,(ks,dataMerger,dataMerger1,dataMerger2) in merge.items():
            if ks[0] in data:
                if ks[1] in data:
                    try:
                        mergedData[k2] = dataMerger(data[ks[0]], data[ks[1]])
                        log.debug('Merged {} {!r} and {} {!r} into {} {!r}', ks[0], data[ks[0]], ks[1], data[ks[1]], k2, mergedData[k2])
                    except ValueError as e:
                        log.exception('Could not merge {} {!r} and {} {!r} into {}', ks[0], data[ks[0]], ks[1], data[ks[1]], k2)
                else:
                    mergedData[k2] = dataMerger1(data[ks[0]])
            else:
                if ks[1] in data:
                    mergedData[k2] = dataMerger2(data[ks[1]])
        self.data = mergedData
        # FIXME uv_layer must be merged from texel01 data

    def buildColorInputRGB(self, k, socket):
        log = self.log
        # OBJEX_NodeSocket_RGBA_Color <- OBJEX_NodeSocket_CombinerInput in node group OBJEX_rgba_pipe
        socket = socket.node.inputs[0]
        # should be linked to a ShaderNodeRGB node
        if socket.links:
            socket = socket.links[0].from_socket
            if socket.node.bl_idname != 'ShaderNodeRGB':
                log.error('(data key: {}) socket {!r} is not linked to a ShaderNodeRGB node, instead it is linked to {!r} ({})', k, socket, socket.node, socket.node.bl_idname)
        else:
            log.error('(data key: {}) socket {!r} is not linked (it should, to a ShaderNodeRGB node)', k, socket)
        self.data[k] = socket.default_value

    def buildColorInputA(self, k, socket):
        log = self.log
        # NodeSocketFloat <- OBJEX_NodeSocket_CombinerInput in node group OBJEX_rgba_pipe
        socket = socket.node.inputs[1]
        if socket.links:
            log.error('(data key: {}) alpha socket {!r} should not be linked', k, socket)
        self.data[k] = socket.default_value

    def buildTexelDataFromColorSocket(self, k, socket):
        # FIXME
        textureNode = socket.node.inputs[0].links[0].from_node
        self.data[k] = self.buildTexelDataFromTextureNode(textureNode)

    def buildTexelDataFromAlphaSocket(self, k, socket):
        # FIXME
        # use alpha input link instead 
        textureNode = socket.node.inputs[1].links[0].from_node
        self.data[k] = self.buildTexelDataFromTextureNode(textureNode)

    def buildTexelDataFromTextureNode(self, textureNode):
        # FIXME
        scaleUVnode = textureNode.inputs[0].links[0].from_node
        return {
            'texture': textureNode.texture,
            'uv_scale_u': scaleUVnode.inputs[1].default_value,
            'uv_scale_v': scaleUVnode.inputs[2].default_value,
            'uv_wrap_u': scaleUVnode.inputs[3].default_value,
            'uv_wrap_v': scaleUVnode.inputs[4].default_value,
            'uv_mirror_u': scaleUVnode.inputs[5].default_value,
            'uv_mirror_v': scaleUVnode.inputs[6].default_value,
            'uv_layer': scaleUVnode.inputs[0].links[0].from_node.uv_layer,
        }

    def buildShadingDataFromColorSocket(self, k, socket):
        # FIXME
        n = socket.node.inputs[0].links[0].from_node
        if n.bl_idname == 'ShaderNodeGeometry':
            self.data[k] = {'type':'vertex_colors','vertex_color_layer':n.color_layer}
        else:
            self.data[k] = {'type':'normals'}

    def buildShadingDataFromAlphaSocket(self, k, socket):
        # FIXME
        n = socket.node.inputs[1].links[0].from_node
        if n.bl_idname == 'ShaderNodeGeometry':
            self.data[k] = {'type':'vertex_colors','vertex_color_layer':n.color_layer}
        else:
            self.data[k] = {'type':'normals'}

# fixme this is going to end up finding uv/vcolor layers from node (or default to active I guess), if several layers, may write the wrong layer in .objex ... should call write_mtl and get uvs/vcolor data this way before writing the .objex?
def write_mtl(scene, filepath, append_header, options, copy_set, mtl_dict):
    log = getLogger('export_objex')

    source_dir = os.path.dirname(bpy.data.filepath)
    dest_dir = os.path.dirname(filepath)
    path_mode = options['PATH_MODE']
    export_packed_images = options['EXPORT_PACKED_IMAGES']
    export_packed_images_dir = options['EXPORT_PACKED_IMAGES_DIR']

    with open(filepath, "w", encoding="utf8", newline="\n") as f:
        fw = f.write

        fw('# Blender MTL File: %r\n' % (os.path.basename(bpy.data.filepath) or "None"))
        fw('# Material Count: %i\n' % len(mtl_dict))

        # used for writing exportid
        append_header(fw)

        # maps a file path to a texture name, to avoid duplicate newtex declarations
        # 421fixme is this still expected behavior?
        texture_names = {}

        def writeTexture(image, name):
            image_filepath = image.filepath
            texture_name = texture_names.get(image_filepath)
            if not texture_name:
                texture_name = name
                # make sure texture_name is not already used
                i = 0
                while texture_name in texture_names.values():
                    i += 1
                    texture_name = '%s_%d' % (name, i)
                if i != 0:
                    log.debug('Texture name {} was already used, using {} instead', name, texture_name)
                texture_names[image_filepath] = texture_name
                fw('newtex %s\n' % texture_name)
                if image.packed_files:
                    if export_packed_images:
                        # save externally a packed image
                        image_filepath = '%s/%s' % (export_packed_images_dir, texture_name)
                        image_filepath = bpy.path.abspath(image_filepath)
                        log.info('Saving packed image {!r} to {}', image, image_filepath)
                        image.save_render(image_filepath)
                    else:
                        log.warning('Image {!r} is packed, assuming it exists at {}', image, image_filepath)
                filepath = bpy_extras.io_utils.path_reference(image_filepath, source_dir, dest_dir,
                                                              path_mode, "", copy_set, image.library)
                fw('map %s\n' % filepath)
                # texture objex data
                tod = image.objex_bonus
                if tod.pointer:
                    fw('pointer %s%s\n' % (
                        '' if tod.pointer.startswith('0x') else '0x',
                        tod.pointer
                    ))
                if tod.format != 'AUTO':
                    # zzconvert requires lower case format name
                    fw('format %s\n' % tod.format.lower())
                    if tod.format[:2] == 'CI' and tod.palette != 0:
                        fw('palette %d\n' % tod.palette)
                if tod.priority != 0:
                    fw('priority %d\n' % tod.priority)
                if tod.force_write == 'FORCE_WRITE':
                    fw('forcewrite\n')
                elif tod.force_write == 'DO_NOT_WRITE':
                    fw('forcenowrite\n')
                if tod.texture_bank:
                    fw('texturebank %s\n'
                        % bpy_extras.io_utils.path_reference(
                            tod.texture_bank, source_dir, dest_dir,
                            path_mode, '', copy_set
                    ))
            else:
                log.trace('Skipped writing texture {} using file {}', texture_name, image_filepath)
            # texture_name is input name if new texture,
            # or the name used for writing the image path
            return texture_name

        for material_name, material, face_img in mtl_dict.values():
            log.trace('Writing material_name={!r} material={!r} face_img={!r}', material_name, material, face_img)
            objex_data = material.objex_bonus if material else None
            if objex_data and objex_data.is_objex_material:
                if not material.use_nodes:
                    log.error('Material {!r} is_objex_material but not use_nodes (was "Use Nodes" unchecked after adding objex nodes to it?)', material)
                explorer = ObjexMaterialNodeTreeExplorer(material.node_tree)
                explorer.build()
                if len(explorer.combinerFlags) != 16:
                    log.error('Unexpected combiner flags amount {:d} (are both cycles used?), flags: {!r}', len(explorer.combinerFlags), explorer.combinerFlags)
                data = explorer.data
                texel0data = texel1data = None
                if 'texel0' in data:
                    texel0data = data['texel0']
                    # todo check texture.type == 'IMAGE'
                    tex = texel0data['texture']
                    texel0data['texture_name'] = writeTexture(tex.image, tex.name)
                if 'texel1' in data:
                    texel1data = data['texel1']
                    tex = texel1data['texture']
                    texel1data['texture_name'] = writeTexture(tex.image, tex.name)
                fw('newmtl %s\n' % material_name)
                if texel0data:
                    fw('texel0 %s\n' % texel0data['texture_name'])
                if texel1data:
                    fw('texel1 %s\n' % texel1data['texture_name'])
                scaleS = max(0, min(0xFFFF/0x10000, objex_data.scaleS))
                scaleT = max(0, min(0xFFFF/0x10000, objex_data.scaleT))
                fw('gbi gsSPTexture(qu016(%f), qu016(%f), 0, G_TX_RENDERTILE, G_ON)\n' % (scaleS, scaleT))
                fw('gbi gsDPPipeSync()\n')
                # fixme do not hardcode flags, and what about blender settings, and G_RM_AA_ZB_OPA_SURF2 ?
                otherModeLowerHalfFlags = [
                    'AA_EN', # anti-aliasing ?
                    'Z_CMP', # use zbuffer
                    'Z_UPD', # update zbuffer
                    'IM_RD', # ?
                    'CVG_DST_CLAMP', # ?
                    'ALPHA_CVG_SEL', # ?
                ]
                if objex_data.rendermode_zmode == 'AUTO':
                    otherModeLowerHalfFlags.append('ZMODE_XLU' if material.use_transparency else 'ZMODE_OPA')
                else:
                    otherModeLowerHalfFlags.append('ZMODE_%s' % objex_data.rendermode_zmode)
                if (objex_data.rendermode_forceblending == 'YES'
                    or (objex_data.rendermode_forceblending == 'AUTO'
                        and material.use_transparency)
                ):
                    otherModeLowerHalfFlags.append('FORCE_BL')
                """
from gbi.h :
count  P              A              M              B            comment
2      0              0              0              0            "NOOP"
1      G_BL_CLR_FOG   G_BL_A_FOG     G_BL_CLR_IN    G_BL_1MA     only defined for cycle 1 in G_RM_FOG_PRIM_A
1      G_BL_CLR_FOG   G_BL_A_SHADE   G_BL_CLR_IN    G_BL_1MA     only defined for cycle 1 in G_RM_FOG_SHADE_A
11     G_BL_CLR_IN    G_BL_0         G_BL_CLR_IN    G_BL_1       defined for cycle 1 by G_RM_PASS, used for both cycles
2      G_BL_CLR_IN    G_BL_0         G_BL_CLR_BL    G_BL_A_MEM   by G_RM_VISCVG, G_RM_VISCVG2
2      G_BL_CLR_IN    G_BL_A_FOG     G_BL_CLR_MEM   G_BL_1       by G_RM_ADD, G_RM_ADD2
46     G_BL_CLR_IN    G_BL_A_IN      G_BL_CLR_MEM   G_BL_1MA     all XLU use this
30     G_BL_CLR_IN    G_BL_A_IN      G_BL_CLR_MEM   G_BL_A_MEM   most OPA use this
                """
                rm_bl_c0 = objex_data.rendermode_blending_cycle0
                rm_bl_c1 = objex_data.rendermode_blending_cycle1
                if rm_bl_c0 == 'AUTO':
                    rm_bl_c0 = 'PASS' if material.use_transparency else 'FOG_SHADE'
                if rm_bl_c1 == 'AUTO':
                    rm_bl_c1 = 'XLU' if material.use_transparency else 'OPA'
                presets = {
                    'FOG_PRIM': ('G_BL_CLR_FOG','G_BL_A_FOG',  'G_BL_CLR_IN', 'G_BL_1MA'),
                    'FOG_SHADE':('G_BL_CLR_FOG','G_BL_A_SHADE','G_BL_CLR_IN', 'G_BL_1MA'),
                    'PASS':     ('G_BL_CLR_IN', 'G_BL_0',      'G_BL_CLR_IN', 'G_BL_1'),
                    'OPA':      ('G_BL_CLR_IN', 'G_BL_A_IN',   'G_BL_CLR_MEM','G_BL_A_MEM'),
                    'XLU':      ('G_BL_CLR_IN', 'G_BL_A_IN',   'G_BL_CLR_MEM','G_BL_1MA'),
                }
                if rm_bl_c0 == 'CUSTOM':
                    blendCycle0flags = (getattr(objex_data, 'rendermode_blending_cycle0_custom_%s' % v) for v in ('P','A','M','B'))
                else:
                    blendCycle0flags = presets[rm_bl_c0]
                if rm_bl_c1 == 'CUSTOM':
                    blendCycle1flags = (getattr(objex_data, 'rendermode_blending_cycle1_custom_%s' % v) for v in ('P','A','M','B'))
                else:
                    blendCycle1flags = presets[rm_bl_c1]
                fw('gbi gsSPSetOtherModeLo(G_MDSFT_RENDERMODE, G_MDSIZ_RENDERMODE, %s | GBL_c1(%s) | GBL_c2(%s))\n' % (
                    # ' | ' instead of '|' is required by zzconvert because "Just laziness on my part. :skawoUHHUH:"
                    ' | '.join(otherModeLowerHalfFlags),
                    ', '.join(blendCycle0flags),
                    ', '.join(blendCycle1flags),
                ))
                """
                (P * A + M - B) / (A + B)
                
                GBL_c1(G_BL_CLR_FOG, G_BL_A_SHADE, G_BL_CLR_IN, G_BL_1MA) :
                (G_BL_CLR_FOG * G_BL_A_SHADE + G_BL_CLR_IN - G_BL_1MA) / (G_BL_A_SHADE + G_BL_1MA)
                (fogColor * shadeAlpha + pixelColor - (1-pixelAlpha)) / (shadeAlpha + (1-pixelAlpha))
                ???
                
                GBL_c2(G_BL_CLR_IN,G_BL_A_IN,G_BL_CLR_MEM,G_BL_A_MEM) :
                (G_BL_CLR_IN * G_BL_A_IN + G_BL_CLR_MEM - G_BL_A_MEM) / (G_BL_A_IN + G_BL_A_MEM)
                (firstCycleNumerator * pixelAlpha + frameBufferColor - frameBufferAlpha) / (pixelAlpha + frameBufferAlpha)
                
                and G_RM_AA_ZB_OPA_SURF2 is a preset for the same kind of stuff
                
                
                according to angrylion:
                
                (P * (A / 8) + M * (B / 8 + 1)) / 32 (0-255 integer range)
                for simplicity, assume P * A + M * B (0-1 range)
                G_BL_CLR_FOG * G_BL_A_SHADE + G_BL_CLR_IN * G_BL_1MA
                fogColor * shadeAlpha + pixelColor * (1 - pixelAlpha)
                
                G_BL_CLR_IN * G_BL_A_IN + G_BL_CLR_MEM * G_BL_A_MEM
                firstCycle * pixelAlpha + frameBufferColor * frameBufferAlpha
                
                (fogColor * shadeAlpha + pixelColor * (1 - pixelAlpha)) * pixelAlpha + frameBufferColor * frameBufferAlpha
                """
                # todo better G_?CMUX_ prefix stripping
                fw('gbi gsDPSetCombineLERP(%s)\n' % (', '.join(flag[len('G_?CMUX_'):] for flag in explorer.combinerFlags)))
                if texel0data or texel1data:
                    fw('gbi gsDPSetTileSize(G_TX_RENDERTILE, 0, 0, '
                        'qu102(_texel{0}width-1), qu102(_texel{0}height-1))\n'
                        .format('0' if texel0data else '1')
                    ) # 421fixme ?
                def rgba32(rgba):
                    return tuple(int(c*255) for c in rgba)
                if 'primitive' in data and objex_data.write_primitive_color:
                    fw('gbi gsDPSetPrimColor(0, qu08(0.5), %d, %d, %d, %d)\n' % rgba32(data['primitive'])) # 421fixme minlevel, lodfrac
                if 'environment' in data and objex_data.write_environment_color:
                    fw('gbi gsDPSetEnvColor(%d, %d, %d, %d)\n' % rgba32(data['environment']))
                # 421todo more geometry mode flags
                geometryModeFlagsClear = []
                geometryModeFlagsSet = []
                if 'shade' in data:
                    shadeData = data['shade']
                    (geometryModeFlagsSet
                        if shadeData['type'] == 'normals'
                        else geometryModeFlagsClear
                    ).append('G_LIGHTING')
                (geometryModeFlagsSet
                    if objex_data.backface_culling
                    else geometryModeFlagsClear
                ).append('G_CULL_BACK')
                (geometryModeFlagsSet
                    if objex_data.use_texgen
                    else geometryModeFlagsClear
                ).extend(('G_TEXTURE_GEN','G_TEXTURE_GEN_LINEAR'))
                if len(geometryModeFlagsClear) == 0:
                    geometryModeFlagsClear = ('0',)
                if len(geometryModeFlagsSet) == 0:
                    geometryModeFlagsSet = ('0',)
                # todo make sure setting geometry mode in one call is not an issue
                fw('gbi gsSPGeometryMode(%s, %s)\n' % (' | '.join(geometryModeFlagsClear),' | '.join(geometryModeFlagsSet)))
                def getUVflags(wrap, mirror):
                    return ('G_TX_WRAP' if wrap else 'G_TX_CLAMP', 'G_TX_MIRROR' if mirror else 'G_TX_NOMIRROR')
                for i,texelData in (('0',texel0data),('1',texel1data)):
                    if texelData:
                        fw('gbivar cms%s "%s"\n' % (i, ' | '.join(getUVflags(texelData['uv_wrap_u'], texelData['uv_mirror_u']))))
                        fw('gbivar cmt%s "%s"\n' % (i, ' | '.join(getUVflags(texelData['uv_wrap_v'], texelData['uv_mirror_v']))))
                        fw('gbivar shifts%s %d\n' % (i, texelData['uv_scale_u']))
                        fw('gbivar shiftt%s %d\n' % (i, texelData['uv_scale_v']))
                if texel0data or texel1data:
                    fw('gbi _loadtexels\n')
            else:
                image = None
                # Write images!
                # face_img.filepath may be '' for generated images
                if face_img and face_img.filepath: # We have an image on the face!
                    image = face_img
                elif material:  # No face image. if we have a material search for MTex image.
                    # backwards so topmost are highest priority (421todo ... sure about that?)
                    for mtex in reversed(material.texture_slots):
                        if mtex and mtex.texture and mtex.texture.type == 'IMAGE':
                            image = mtex.texture.image
                            if image and (mtex.use_map_color_diffuse and
                                (mtex.use_map_warp is False) and (mtex.texture_coords != 'REFLECTION')):
                                """
                                what about mtex.offset, mtex.scale? see original code
                                
                                if mtex.offset != Vector((0.0, 0.0, 0.0)):
                                    options.append('-o %.6f %.6f %.6f' % mtex.offset[:])
                                if mtex.scale != Vector((1.0, 1.0, 1.0)):
                                    options.append('-s %.6f %.6f %.6f' % mtex.scale[:])
                                """
                                break
                            else:
                                image = None

                if image:
                    texture_name = 'texture_%d' % len(texture_names)
                    texture_name = writeTexture(image, texture_name)
                else:
                    texture_name = None
                fw('newmtl %s\n' % material_name)
                if texture_name:
                    fw('texel0 %s\n' % texture_name)


"""
Currently the exporter lacks these features:
* multiple scene export (only active scene is written)
* particles
"""

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
         use_weights=None,
         use_unique_weights=None,
         use_mesh_modifiers=None,
         use_mesh_modifiers_render=None,
         keep_vertex_order=None,
         use_vertex_groups=None,
         export_packed_images=None,
         export_packed_images_dir=None,
         use_selection=None,
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
        'EXPORT_WEIGHTS':use_weights,
        'UNIQUE_WEIGHTS':use_unique_weights,
        'APPLY_MODIFIERS':use_mesh_modifiers,
        'APPLY_MODIFIERS_RENDER':use_mesh_modifiers_render,
        'KEEP_VERTEX_ORDER':keep_vertex_order,
        'EXPORT_POLYGROUPS':use_vertex_groups,
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
    else:
        objects = context.scene.objects
    objex_writer.add_target_objects(objects)

    # EXPORT THE FILE.
    objex_writer.write(filepath)
    
    return {'FINISHED'}
