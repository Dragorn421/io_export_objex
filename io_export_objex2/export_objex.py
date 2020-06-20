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

import bpy
import mathutils
import bpy_extras.io_utils

from progress_report import ProgressReport, ProgressReportSubstep

import json

from . import export_objex_anim


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
    
    def __init__(self, context):
        self.context = context
        self.objects = []
        self.options = {
            'TRIANGULATE': True,
            'EXPORT_EDGES': False,
            'EXPORT_SMOOTH_GROUPS': False,
            'EXPORT_SMOOTH_GROUPS_BITFLAGS': False,
            'EXPORT_NORMALS': True,
            'EXPORT_VERTEX_COLORS': True,
            'EXPORT_UV': True,
            'EXPORT_MTL': True,
            'EXPORT_SKEL': True,
            'EXPORT_ANIM': True,
            'EXPORT_WEIGHTS': True,
            'UNIQUE_WEIGHTS': False, # 421todo default value? (btw, should fix that default values are defined in three different places)
            'APPLY_MODIFIERS': True,
            'APPLY_MODIFIERS_RENDER': False,
            'EXPORT_BLEN_OBS': True,
            'EXPORT_GROUP_BY_OB': False,
            'EXPORT_GROUP_BY_MAT': False,
            'KEEP_VERTEX_ORDER': False,
            'EXPORT_POLYGROUPS': False,
            'EXPORT_CURVE_AS_NURBS': True,
            'GLOBAL_MATRIX': None,
            'PATH_MODE': 'AUTO'
        }
    
    def add_target_objects(self, objects):
        self.objects.extend(objects)
    
    def set_options(self, options):
        self.options.update(options)
    
    def write_header(self):
        fw = self.fw_objex
        
        fw('# Blender v%s Objex File: %r\n' % (bpy.app.version_string, os.path.basename(bpy.data.filepath)))
        fw('# www.blender.org\n')
        
        # Tell the obj file what material/skeleton/animation file to use.
        if self.options['EXPORT_MTL']:
            self.filepath_mtl = os.path.splitext(self.filepath)[0] + ".mtl"
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
                # 421todo support alpha 
                vc_key = loop_colors[l_idx].color
                vc_key = (round(vc_key[0], 6), round(vc_key[1], 6), round(vc_key[2], 6))
                vc_val = vertex_colors_to_idx.get(vc_key)
                if vc_val is None:
                    vc_val = vertex_colors_to_idx[vc_key] = vc_unique_count
                    fw('vc %.6f %.6f %.6f 1.0\n' % vc_key)
                    vc_unique_count += 1
                loops_to_vertex_colors[l_idx] = vc_val
        return loops_to_vertex_colors, vc_unique_count
    
    def write_object(self, progress, ob, ob_mat):
        fw = self.fw_objex
        scene = self.context.scene
        
        with ProgressReportSubstep(progress, 6) as subprogress2:

            # Nurbs curve support
            if self.options['EXPORT_CURVE_AS_NURBS'] and test_nurbs_compat(ob):
                ob_mat = self.options['GLOBAL_MATRIX'] * ob_mat
                self.total_vertex += write_nurb(fw, ob, ob_mat)
                return
            # END NURBS
            
            if self.options['EXPORT_SKEL'] and ob.type == 'ARMATURE':
                if self.options['EXPORT_ANIM']:
                    # 421todo store relevant actions
                    #armatures.append((ob, [bpy.data.actions[action_name] for action_name in ob.objex_bonus.actions]))
                    self.armatures.append((ob, [ob.animation_data.action] if hasattr(ob.animation_data, 'action') and ob.animation_data.action else []))
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

            if self.options['EXPORT_EDGES']:
                edges = me.edges
            else:
                edges = []

            if not (len(face_index_pairs) + len(edges) + len(vertices)):  # Make sure there is something to write
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

            if self.options['EXPORT_BLEN_OBS'] or self.options['EXPORT_GROUP_BY_OB']:
                name1 = ob.name
                name2 = ob.data.name
                if name1 == name2:
                    obnamestring = name_compat(name1)
                else:
                    obnamestring = '%s_%s' % (name_compat(name1), name_compat(name2))

                if self.options['EXPORT_BLEN_OBS']:
                    fw('o %s\n' % obnamestring)  # Write Object name
                else:  # if EXPORT_GROUP_BY_OB:
                    fw('g %s\n' % obnamestring)

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
            # 421todo for weights, we may want to filter out groups not named after bones, those may cause issues
            # 421todo putting the "parent armature" check because zzconvert doesnt like weight otherwise
            is_rigged = ob.parent and ob.parent.type == 'ARMATURE'
            if is_rigged:
                fw('useskel %s\n' % string_to_literal(ob.parent.name))
            if self.options['EXPORT_WEIGHTS'] and vertex_groups and is_rigged:
                # only group of maximum weight, with weight 1
                if self.options['UNIQUE_WEIGHTS']:
                    for v in vertices:
                        groups = vertex_groups[v.index]
                        if groups:
                            group_name, weight = max(groups, key=lambda _g: _g[1])
                            fw('%s %s\n' % (
                                'v %.6f %.6f %.6f' % v.co[:],
                                'weight %s 1' % (string_to_literal(group_name))
                            ))
                        else:
                            # 421todo is this legal? potentially mixing vertices with and without weight set
                            fw('v %.6f %.6f %.6f\n' % v.co[:])
                # all (non-zero) weights
                else:
                    for v in vertices:
                        # 421todo the != 0 check may cause the same issue as 5 lines above, if it turns out to be an issue
                        fw('%s%s\n' % (
                            'v %.6f %.6f %.6f' % v.co[:],
                            ','.join([' weight %s %.3f' % (string_to_literal(group_name), weight) for group_name, weight in vertex_groups[v.index] if weight != 0])
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
            context_material_name = context_texture_name = 0  # Can never be this, so we will label a new material the first chance we get. g written if EXPORT_GROUP_BY_MAT, also used for usemtl directives if EXPORT_MTL
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
                        if self.options['EXPORT_GROUP_BY_MAT']:
                            # can be mat_image or (null)
                            fw("g %s_%s\n" % (name_compat(ob.name), name_compat(ob.data.name)))
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

                        if self.options['EXPORT_GROUP_BY_MAT']:
                            # can be mat_image or (null)
                            fw("g %s_%s_%s\n" % (name_compat(ob.name), name_compat(ob.data.name), mat_data[0]))
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

            # Write edges.
            if self.options['EXPORT_EDGES']:
                for ed in edges:
                    if ed.is_loose:
                        fw('l %d %d\n' % (self.total_vertex + ed.vertices[0], self.total_vertex + ed.vertices[1]))

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
                            print('creating dupli_list on', ob_main.name)
                            ob_main.dupli_list_create(scene)

                            obs += [(dob.object, dob.matrix) for dob in ob_main.dupli_list]

                            # XXX debug print
                            print(ob_main.name, 'has', len(obs) - 1, 'dupli children')

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
                    write_mtl(scene, self.filepath_mtl, self.options['PATH_MODE'], copy_set, self.mtl_dict)
                
                subprogress1.step("Finished exporting materials, now exporting skeletons/animations")

                # save gathered skeletons and animations
                if self.options['EXPORT_SKEL']:
                    print('now exporting skeletons')
                    skelfile = None
                    animfile = None
                    try:
                        skelfile = open(self.filepath_skel, "w", encoding="utf8", newline="\n")
                        skelfile_write = skelfile.write
                        if self.options['EXPORT_ANIM']:
                            print(' ... and animations')
                            animfile = open(self.filepath_anim, "w", encoding="utf8", newline="\n")
                            animfile_write = animfile.write
                        else:
                            animfile_write = lambda _: None # void output
                        export_objex_anim.write_anim(animfile_write, skelfile_write, scene, self.armatures)
                    finally:
                        if skelfile:
                            skelfile.close()
                        if animfile:
                            animfile.close()
                
                # copy all collected files.
                bpy_extras.io_utils.path_reference_copy(copy_set)

            progress.leave_substeps()


def write_mtl(scene, filepath, path_mode, copy_set, mtl_dict):
    from mathutils import Color, Vector

    world = scene.world
    if world:
        world_amb = world.ambient_color
    else:
        world_amb = Color((0.0, 0.0, 0.0))

    source_dir = os.path.dirname(bpy.data.filepath)
    dest_dir = os.path.dirname(filepath)

    with open(filepath, "w", encoding="utf8", newline="\n") as f:
        fw = f.write

        fw('# Blender MTL File: %r\n' % (os.path.basename(bpy.data.filepath) or "None"))
        fw('# Material Count: %i\n' % len(mtl_dict))

        mtl_dict_values = list(mtl_dict.values())
        mtl_dict_values.sort(key=lambda m: m[0])

        # Write material/image combinations we have used.
        # Using mtl_dict.values() directly gives un-predictable order.
        for mtl_mat_name, mat, face_img in mtl_dict_values:
            # Get the Blender data for the material and the image.
            # Having an image named None will make a bug, dont do it :)

            fw('\nnewmtl %s\n' % mtl_mat_name)  # Define a new material: matname_imgname

            if mat:
                use_mirror = mat.raytrace_mirror.use and mat.raytrace_mirror.reflect_factor != 0.0

                # convert from blenders spec to 0 - 1000 range.
                if mat.specular_shader == 'WARDISO':
                    tspec = (0.4 - mat.specular_slope) / 0.0004
                else:
                    tspec = (mat.specular_hardness - 1) / 0.51
                fw('Ns %.6f\n' % tspec)
                del tspec

                # Ambient
                if use_mirror:
                    fw('Ka %.6f %.6f %.6f\n' % (mat.raytrace_mirror.reflect_factor * mat.mirror_color)[:])
                else:
                    fw('Ka %.6f %.6f %.6f\n' % (mat.ambient, mat.ambient, mat.ambient))  # Do not use world color!
                fw('Kd %.6f %.6f %.6f\n' % (mat.diffuse_intensity * mat.diffuse_color)[:])  # Diffuse
                fw('Ks %.6f %.6f %.6f\n' % (mat.specular_intensity * mat.specular_color)[:])  # Specular
                # Emission, not in original MTL standard but seems pretty common, see T45766.
                # XXX Blender has no color emission, it's using diffuse color instead...
                fw('Ke %.6f %.6f %.6f\n' % (mat.emit * mat.diffuse_color)[:])
                if hasattr(mat, "raytrace_transparency") and hasattr(mat.raytrace_transparency, "ior"):
                    fw('Ni %.6f\n' % mat.raytrace_transparency.ior)  # Refraction index
                else:
                    fw('Ni %.6f\n' % 1.0)
                fw('d %.6f\n' % mat.alpha)  # Alpha (obj uses 'd' for dissolve)

                # See http://en.wikipedia.org/wiki/Wavefront_.obj_file for whole list of values...
                # Note that mapping is rather fuzzy sometimes, trying to do our best here.
                if mat.use_shadeless:
                    fw('illum 0\n')  # ignore lighting
                elif mat.specular_intensity == 0:
                    fw('illum 1\n')  # no specular.
                elif use_mirror:
                    if mat.use_transparency and mat.transparency_method == 'RAYTRACE':
                        if mat.raytrace_mirror.fresnel != 0.0:
                            fw('illum 7\n')  # Reflection, Transparency, Ray trace and Fresnel
                        else:
                            fw('illum 6\n')  # Reflection, Transparency, Ray trace
                    elif mat.raytrace_mirror.fresnel != 0.0:
                        fw('illum 5\n')  # Reflection, Ray trace and Fresnel
                    else:
                        fw('illum 3\n')  # Reflection and Ray trace
                elif mat.use_transparency and mat.transparency_method == 'RAYTRACE':
                    fw('illum 9\n')  # 'Glass' transparency and no Ray trace reflection... fuzzy matching, but...
                else:
                    fw('illum 2\n')  # light normaly

            else:
                # Write a dummy material here?
                fw('Ns 0\n')
                fw('Ka %.6f %.6f %.6f\n' % world_amb[:])  # Ambient, uses mirror color,
                fw('Kd 0.8 0.8 0.8\n')
                fw('Ks 0.8 0.8 0.8\n')
                fw('d 1\n')  # No alpha
                fw('illum 2\n')  # light normaly

            # Write images!
            if face_img:  # We have an image on the face!
                filepath = face_img.filepath
                if filepath:  # may be '' for generated images
                    # write relative image path
                    filepath = bpy_extras.io_utils.path_reference(filepath, source_dir, dest_dir,
                                                                  path_mode, "", copy_set, face_img.library)
                    fw('map_Kd %s\n' % filepath)  # Diffuse mapping image
                    del filepath
                else:
                    # so we write the materials image.
                    face_img = None

            if mat:  # No face image. if we havea material search for MTex image.
                image_map = {}
                # backwards so topmost are highest priority
                for mtex in reversed(mat.texture_slots):
                    if mtex and mtex.texture and mtex.texture.type == 'IMAGE':
                        image = mtex.texture.image
                        if image:
                            # texface overrides others
                            if (mtex.use_map_color_diffuse and (face_img is None) and
                                (mtex.use_map_warp is False) and (mtex.texture_coords != 'REFLECTION')):
                                image_map["map_Kd"] = (mtex, image)
                            if mtex.use_map_ambient:
                                image_map["map_Ka"] = (mtex, image)
                            # this is the Spec intensity channel but Ks stands for specular Color
                            '''
                            if mtex.use_map_specular:
                                image_map["map_Ks"] = (mtex, image)
                            '''
                            if mtex.use_map_color_spec:  # specular color
                                image_map["map_Ks"] = (mtex, image)
                            if mtex.use_map_hardness:  # specular hardness/glossiness
                                image_map["map_Ns"] = (mtex, image)
                            if mtex.use_map_alpha:
                                image_map["map_d"] = (mtex, image)
                            if mtex.use_map_translucency:
                                image_map["map_Tr"] = (mtex, image)
                            if mtex.use_map_normal:
                                image_map["map_Bump"] = (mtex, image)
                            if mtex.use_map_displacement:
                                image_map["disp"] = (mtex, image)
                            if mtex.use_map_color_diffuse and (mtex.texture_coords == 'REFLECTION'):
                                image_map["refl"] = (mtex, image)
                            if mtex.use_map_emit:
                                image_map["map_Ke"] = (mtex, image)

                for key, (mtex, image) in sorted(image_map.items()):
                    filepath = bpy_extras.io_utils.path_reference(image.filepath, source_dir, dest_dir,
                                                                  path_mode, "", copy_set, image.library)
                    options = []
                    if key == "map_Bump":
                        if mtex.normal_factor != 1.0:
                            options.append('-bm %.6f' % mtex.normal_factor)
                    if mtex.offset != Vector((0.0, 0.0, 0.0)):
                        options.append('-o %.6f %.6f %.6f' % mtex.offset[:])
                    if mtex.scale != Vector((1.0, 1.0, 1.0)):
                        options.append('-s %.6f %.6f %.6f' % mtex.scale[:])
                    if options:
                        fw('%s %s %s\n' % (key, " ".join(options), repr(filepath)[1:-1]))
                    else:
                        fw('%s %s\n' % (key, repr(filepath)[1:-1]))


def test_nurbs_compat(ob):
    if ob.type != 'CURVE':
        return False

    for nu in ob.data.splines:
        if nu.point_count_v == 1 and nu.type != 'BEZIER':  # not a surface and not bezier
            return True

    return False


def write_nurb(fw, ob, ob_mat):
    tot_verts = 0
    cu = ob.data

    # use negative indices
    for nu in cu.splines:
        if nu.type == 'POLY':
            DEG_ORDER_U = 1
        else:
            DEG_ORDER_U = nu.order_u - 1  # odd but tested to be correct

        if nu.type == 'BEZIER':
            print("\tWarning, bezier curve:", ob.name, "only poly and nurbs curves supported")
            continue

        if nu.point_count_v > 1:
            print("\tWarning, surface:", ob.name, "only poly and nurbs curves supported")
            continue

        if len(nu.points) <= DEG_ORDER_U:
            print("\tWarning, order_u is lower then vert count, skipping:", ob.name)
            continue

        pt_num = 0
        do_closed = nu.use_cyclic_u
        do_endpoints = (do_closed == 0) and nu.use_endpoint_u

        for pt in nu.points:
            fw('v %.6f %.6f %.6f\n' % (ob_mat * pt.co.to_3d())[:])
            pt_num += 1
        tot_verts += pt_num

        fw('g %s\n' % (name_compat(ob.name)))  # name_compat(ob.getData(1)) could use the data name too
        fw('cstype bspline\n')  # not ideal, hard coded
        fw('deg %d\n' % DEG_ORDER_U)  # not used for curves but most files have it still

        curve_ls = [-(i + 1) for i in range(pt_num)]

        # 'curv' keyword
        if do_closed:
            if DEG_ORDER_U == 1:
                pt_num += 1
                curve_ls.append(-1)
            else:
                pt_num += DEG_ORDER_U
                curve_ls = curve_ls + curve_ls[0:DEG_ORDER_U]

        fw('curv 0.0 1.0 %s\n' % (" ".join([str(i) for i in curve_ls])))  # Blender has no U and V values for the curve

        # 'parm' keyword
        tot_parm = (DEG_ORDER_U + 1) + pt_num
        tot_parm_div = float(tot_parm - 1)
        parm_ls = [(i / tot_parm_div) for i in range(tot_parm)]

        if do_endpoints:  # end points, force param
            for i in range(DEG_ORDER_U + 1):
                parm_ls[i] = 0.0
                parm_ls[-(1 + i)] = 1.0

        fw("parm u %s\n" % " ".join(["%.6f" % i for i in parm_ls]))

        fw('end\n')

    return tot_verts


"""
Currently the exporter lacks these features:
* multiple scene export (only active scene is written)
* particles
"""

def save(context,
         filepath,
         *,
         use_triangles=True,
         use_edges=False,
         use_normals=True,
         use_vertex_colors=True,
         use_smooth_groups=False,
         use_smooth_groups_bitflags=False,
         use_uvs=True,
         use_materials=True,
         use_skeletons=True,
         use_animations=True,
         use_weights=True,
         use_unique_weights=False, # 421todo default value?
         use_mesh_modifiers=True,
         use_mesh_modifiers_render=False,
         use_blen_objects=True,
         group_by_object=False,
         group_by_material=False,
         keep_vertex_order=False,
         use_vertex_groups=False,
         use_nurbs=True,
         use_selection=True,
         global_matrix=None,
         path_mode='AUTO'
         ):

    objex_writer = ObjexWriter(context)
    objex_writer.set_options({
        'TRIANGULATE':use_triangles,
        'EXPORT_EDGES':use_edges,
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
        'EXPORT_BLEN_OBS':use_blen_objects,
        'EXPORT_GROUP_BY_OB':group_by_object,
        'EXPORT_GROUP_BY_MAT':group_by_material,
        'KEEP_VERTEX_ORDER':keep_vertex_order,
        'EXPORT_POLYGROUPS':use_vertex_groups,
        'EXPORT_CURVE_AS_NURBS':use_nurbs,
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
