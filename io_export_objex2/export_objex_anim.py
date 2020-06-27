import bpy
import mathutils

import re
import ast

def write_skel(file_write_skel, global_matrix, skeletons):
    fw = file_write_skel
    for armature, bones_ordered in skeletons:
        # 421todo
        # extra is optional
        # quote and escape strings
        # segment, pbody
        fw('newskel %s %s\n' % (armature.name, armature.data.objex_bonus.type))
        indent = 0
        stack = [None]
        for bone in bones_ordered:
            #print('indent=%d bone=%s parent=%s stack=%r' % (indent, bone.name, bone.parent.name if bone.parent else 'None', stack))
            while bone.parent != stack[-1]:
                indent -= 1
                fw('%s-\n' % (' ' * indent))
                stack.pop()
            # 421todo make sure this is correct, each bone relative to parent in object space axes
            pos = bone.head_local
            # skeleton has no impact on how (wrong) the carpenter looks
            """
            421fixme
            write vertices in bone space
            write skeleton in object space relative to parent
            write location as loc of root
            write rot such that:
            matrix_parent * Translation(skel[bone]) * Rotation(rot) == pose_bone.matrix_channel * Translation(bone.head_local)
            """
            #"""
            if bone.parent:
                pos = pos.copy()
                pos -= bone.parent.head_local
            # 421todo confirm that bone root position is always assumed to be 0 by oot, if yes make sure WYSIWYG applies with the edit-mode location being accounted for in write_action_from_pose_bones
            else:
                pos = mathutils.Vector((0,0,0))
            #"""
            # 421todo use global_matrix, make sure this is correct
            pos = global_matrix * pos
            fw('%s+ %s %.6f %.6f %.6f\n' % (' ' * indent, bone.name, pos.x, pos.y, pos.z))
            # x z -y is correct
            #fw('%s+ %s %.6f %.6f %.6f\n' % (' ' * indent, bone.name, pos.x, pos.z, -pos.y))
            indent += 1
            stack.append(bone)
        while indent > 0:
            indent -= 1
            fw('%s-\n' % (' ' * indent))
        fw('\n')

def order_bones(armature):
    """
    find root bone in armature
    list bones in hierarchy order, preserving the armature order
    """
    bones = armature.data.bones
    root_bone = None
    bones_ordered = []
    for bone in bones:
        # make sure there is only one root bone
        bone_parents = bone.parent_recursive
        root_parent_bone = bone_parents[-1] if bone_parents else bone
        if root_bone and root_parent_bone.name != root_bone.name:
            # 421todo
            print('bone_parents=%r root_bone=%r root_parent_bone=%r' % (bone_parents,root_bone,root_parent_bone))
            print('Error: armature %s has multiple root bones, at least %s and %s' % (armature_name, root_bone.name, root_parent_bone.name))
        root_bone = root_parent_bone
        
        # preserve ordering from armature
        if bone_parents:
            # from top parent to closest parent
            for parent in reversed(bone_parents):
                if parent not in bones_ordered:
                    bones_ordered.append(parent)
        bones_ordered.append(bone)
    
    return root_bone, bones_ordered

# 421todo make write_skel the main call instead of write_anim since .anim depends on .skel but .skel doesn't depend on .anim
def write_anim(file_write_anim, file_write_skel, scene, global_matrix, armatures):
    fw = file_write_anim
    
    print('global_matrix =')
    print(global_matrix)
    
    # user_ variables store parameters (potentially) used by the script and to be restored later
    user_frame_current = scene.frame_current
    user_frame_subframe = scene.frame_subframe
    
    """
    421todo force 20 fps somewhere?
    bpy.context.scene.render.fps = 20 # fps
    bpy.context.scene.render.fps_base = 1.0 # frame duration? (real_fps = fps/fps_base https://github.com/blender/blender/blob/89b6a7bae9160d762f085eff8e927bdac1a60801/release/scripts/startup/bl_operators/screen_play_rendered_anim.py#L85 )
    """
    scene_fps = scene.render.fps / scene.render.fps_base
    if scene_fps != 20:
        # 421todo better error/warning reporting
        print('Warning: animations are being viewed at %.1f fps, but will be used at 20 fps' % scene_fps)
    
    skeletons = []
    
    for armature, armature_actions in armatures:
        
        # no, just let the script crash if armature.animation_data doesn't exist but we still use it when writing an action
        """
        # unlikely but who knows? (animation_data_create doesn't create any action)
        if not armature.animation_data:
            armature.animation_data_create()
        """
        if armature.animation_data:
            user_armature_action = armature.animation_data.action
        
        armature_name = armature.name
        root_bone, bones_ordered = order_bones(armature)
        
        if root_bone is None:
            # 421todo abort?
            print('Error: armature %s has no bones' % armature_name)
        
        bones_idx = {bone.name: bone_idx for bone_idx, bone in enumerate(bones_ordered)}
        skeletons.append((armature, bones_ordered))
        
        # write animations
        fw('# %s\n' % armature_name)
        for action in armature_actions:
            frame_start, frame_end = action.frame_range
            frame_count = int(frame_end - frame_start + 1)
            fw('newanim %s %s %d\n' % (armature_name, action.name, frame_count))
            write_action_from_pose_bones(fw, scene, global_matrix, armature, root_bone, bones_ordered, bones_idx, action, frame_start, frame_count)
            fw('\n')
        fw('\n')
        
        if armature.animation_data:
            armature.animation_data.action = user_armature_action
    
    write_skel(file_write_skel, global_matrix, skeletons)
    
    scene.frame_set(user_frame_current, user_frame_subframe)

def write_action_from_pose_bones(fw, scene, global_matrix, armature, root_bone, bones_ordered, bones_idx, action, frame_start, frame_count):
    armature.animation_data.action = action
    
    pose_bones = armature.pose.bones
    root_pose_bone = pose_bones[root_bone.name]
    
    # 421todo remove this
    # empty input buffer
    #while input('Type smth to continue') == '':
    #    pass
    print('global_matrix =')
    print(global_matrix)
    
    arma = armature
    mesh = armature.children[0]
    if len(armature.children) != 1:
        # 421todo not sure what to do here
        print('WARNING len(armature.children) != 1 -> using %s' % mesh.name)
    
    for frame_current_offset in range(frame_count):
        frame_current = frame_start + frame_current_offset
        scene.frame_set(frame_current)
        # 421todo what if root_bone.head != 0
        """
        > In .anim are the coordinates in loc x y z absolute or relative to the position of the root bone as defined in .skel ?
        > > I think it may be the case that loc x y z is relative to the world origin.
        so that's a TODO - check what happens with non-zero root bone
        if the root bone skeleton position is discarded it should be added in loc
        """
        """
        now we use #head and not #location (which was assumed to be a displacement in armature coordinates but it's not)
        the root bone loc will always be relative to armature
        so if root bone is not at 0,0,0 in edit mode (aka root_bone.head != 0) it may cause issues if loc and root_bone.head are summed
        """
        # 421fixme I have no idea what axes .location uses, definitely not armature coordinates though, unlike .head
        #root_loc = root_pose_bone.location
        root_loc = root_pose_bone.head
        print('frame:',frame_current)
        #print('%d %s %r' % (frame_current, root_bone.name, root_loc))
        # 421todo use global_matrix, make sure this is correct
        root_loc = global_matrix * root_loc
        fw('loc %.6f %.6f %.6f\n' % (root_loc.x, root_loc.y, root_loc.z))
        # x z -y is correct
        #fw('loc %.6f %.6f %.6f\n' % (root_loc.x, root_loc.z, -root_loc.y))
        #bones_matrix_pose = {}
        #bones_quaternion = {}
        #bones_matrix_inipose = {}
        bones_quaternion = {}
        bones_matrix = {}
        for bone in bones_ordered:
            bone_name = bone.name
            pose_bone = pose_bones[bone_name]
            """
            matrix = pose_bone.matrix
            matrix = global_matrix * matrix
            bones_matrix[bone_name] = matrix.copy()
            if bone.parent:
                parent_matrix = bones_matrix[bone.parent.name]
                # 421fixme mult order?
                # I assume this order from right-to-left evaluation ...
                #matrix = matrix * parent_matrix.inverted() # ok with child_rotate, not ok with rotations
                # ... however this order makes (matrix.to_translation() == global_matrix * (bone.head_local - bone.parent.head_local)) hold true so let's go with that
                matrix = parent_matrix.inverted() * matrix # ok with child_rotate, not ok with rotations
                #rotation_quaternion = parent_rotation_quaternion.inverted() * rotation_quaternion
            # 421todo make sure zyx is correct
            rotation_euler_zyx = matrix.to_euler('ZYX')
            rotation_euler_xyz = matrix.to_euler('XYZ')
            # 421todo I think matrix.to_translation() should match bone.head_local - bone.parent.head_local here?
            pass#print(bone_name)
            #print(matrix)
            pass#print(matrix.to_translation())
            if bone.parent:
                pass#print(global_matrix * (bone.head_local - bone.parent.head_local))
            else:
                pass#print(global_matrix * (bone.head_local))
            pass#print(rotation_euler_zyx)
            #rotation_euler_zyx = rotation_quaternion.to_euler('XYZ')
            #print('%d %s %r' % (frame_current, bone_name, rotation_euler_zyx))
            fw('rot %.3f %.3f %.3f\n' % (rotation_euler_zyx.x, rotation_euler_zyx.y, rotation_euler_zyx.z)) # nope
            #fw('rot %.3f %.3f %.3f\n' % (rotation_euler_xyz.x, rotation_euler_xyz.y, rotation_euler_xyz.z)) # nope
            #"""
            
            """
            b = pose_bone
            rotation_euler_zyx = mathutils.Matrix((b.x_axis, b.y_axis, b.z_axis)).transposed().to_euler('ZYX')
            print(mathutils.Matrix((b.x_axis, b.y_axis, b.z_axis)))
            print(rotation_euler_zyx)
            fw('rot %.3f %.3f %.3f\n' % (rotation_euler_zyx.x, rotation_euler_zyx.y, rotation_euler_zyx.z)) # nope
            """
            
            """
            
            this isn't working.
            
            I need to understand and put down what each variable is math-wise and then do calculations
            
            on cherche la rotation de chaque os dans le repère du précédent
            
            list:
            Bone#head
            Bone#tail
            Bone#head_local
            Bone#tail_local
            EditBone#head
            EditBone#tail
            PoseBone#head
            PoseBone#tail
            
            Bone#x/y/z_axis
            EditBone#x/y/z_axis
            PoseBone#x/y/z_axis
            
            Bone#matrix
            Bone#matrix_local
            EditBone#matrix
            PoseBone#matrix
            PoseBone#matrix_basis
            """
            
            # this looks like only going into oot coords is missing
            """
            gm = global_matrix.to_3x3()
            pb = pose_bone
            b = armature.data.bones[bone.name] # = bone iirc
            # this looks to be correct (or at least to do what I want) but not in the right (oot) coordinates
            # introducing gm in different spots didn't help
            m = mathutils.Matrix((pb.x_axis, pb.y_axis, pb.z_axis)).transposed() * b.matrix.inverted()
            #bones_matrix[b.name] = m.copy()
            q = m.to_quaternion()
            bones_quaternion[b.name] = q.copy()
            if b.parent:
                # 421todo again, this or the other way around idk
                #m = bones_matrix[b.parent.name].inverted() * m
                q = bones_quaternion[b.parent.name].inverted() * q
            #rotation_euler_zyx = m.to_euler('ZYX')
            #rotation_euler_zyx = q.to_euler('ZYX')
            #fw('rot %.3f %.3f %.3f\n' % (rotation_euler_zyx.x, rotation_euler_zyx.y, rotation_euler_zyx.z))
            # wtf?
            rotation_euler_stuff = q.to_euler('XZY')
            fw('rot %.3f %.3f %.3f\n' % (rotation_euler_stuff.x, rotation_euler_stuff.z, -rotation_euler_stuff.y))
            #"""
            
            """
            gm = global_matrix.to_3x3()
            pb = pose_bone
            b = armature.data.bones[bone.name] # = bone iirc
            def ax(b):
                m = mathutils.Matrix((b.x_axis, b.y_axis, b.z_axis))
                m.transpose()
                return m
            if b.parent:
                m_ini_parent = bones_matrix_inipose[b.parent.name].copy()
                m_ini = m_ini_parent * ax(b)
                bones_matrix_inipose[b.name] = m_ini.copy()
                m_deform = ax(pb)
                m = m_deform * m_ini.inverted()
                bones_matrix_pose[b.name] = m.copy()
                # order?
                m = bones_matrix_pose[b.parent.name].inverted() * m
            else:
                m_ini = ax(b) # global_matrix here?
                bones_matrix_inipose[b.name] = m_ini.copy()
                m_deform = ax(pb)
                m = m_deform * m_ini.inverted()
                bones_matrix_pose[b.name] = m.copy()
                # global_matrix here?
                #m = m
            rotation_euler_stuff = m.to_euler('XZY')
            fw('rot %.3f %.3f %.3f\n' % (rotation_euler_stuff.x, rotation_euler_stuff.z, -rotation_euler_stuff.y))
            """
            
            # 421fixme bones with roll fuck this
            """
            pb = pose_bone
            b = armature.data.bones[bone.name] # = bone iirc
            def dir(b):
                m = mathutils.Matrix((b.x_axis, b.y_axis, b.z_axis))
                m.transpose()
                return m.to_quaternion()
            
            # but, that cannot work, the edit-mode-pose orientation has rightfully no effect on the animation, it only has an effect on the next bone's position
            #q = dir(b) # orientation in edit-mode-pose relative to parent bone
            #q.rotate(dir(pb)) # orientation relative to edit-mode-pose
            
            q = pb.rotation_quaternion
            rotation_euler_zyx = q.to_euler('XYZ')#421FIXME XYZ
            fw('rot %.3f %.3f %.3f\n' % (rotation_euler_zyx.x, rotation_euler_zyx.y, rotation_euler_zyx.z))
            """
            
            # about
            # "but, that cannot work, the edit-mode-pose orientation has rightfully no effect on the animation, it only has an effect on the next bone's position"
            # edit mode position does have an effect, I don't understand how though
            
            # 421todo try global_matrix
            # 421fixme do NOT use global_matrix at all
            
            """
            C = bpy.context
            post_mat = mesh.matrix_world.inverted() * arma.matrix_world
            #post_mat = global_matrix * post_mat
            pre_mat = post_mat.inverted()
            bone_deform = pose_bone.matrix_channel
            deform_mesh = post_mat * bone_deform * pre_mat
            """
            # deform_mesh goes from vertex location in edit mode in object space to vertex location in object mode in object space
            # how can I not figure out how to get rotations from this?
            """
            post_mat = mesh.matrix_world.inverted() * arma.matrix_world
            deform_mesh = post_mat * pose_bone.matrix_channel * post_mat.inverted()
            """
            
            #deform_mesh = global_matrix * deform_mesh
            """
            q = deform_mesh.to_quaternion()
            bones_quaternion[bone.name] = q.copy()
            if bone.parent:
                q_parent = bones_quaternion[bone.parent.name]
                q = q * q_parent.inverted()
            
            rotation_euler_zyx = q.to_euler('ZYX')
            fw('rot %.3f %.3f %.3f\n' % (rotation_euler_zyx.x, rotation_euler_zyx.y, rotation_euler_zyx.z))
            """
            
            parent_bone = bone.parent
            parent_pose_bone = pose_bone.parent
            # parent_pose_bone.matrix_channel * Translation(skel[bone]) * Rotation(rot) == pose_bone.matrix_channel * Translation(bone.head_local)
            if parent_bone:
                """
                (
                    bone.parent == armature for root bone sounds good, may be wrong
                    root_bone.parent.head_local = (0,0,0)
                    root_pose_bone.parent.matrix_channel = identity (or armature.matrix_world I guess, armature.matrix_world == identity in tests so far, for simplicity)
                )
                assuming we wrote skeleton[bone] = bone.head_local - bone.parent.head_local
                and vertex coordinates co_bone relative to weighted bone in object space
                # co_object is the vertex coordinates relative to object:
                co_object = mathutils.Matrix.Translation(bone.head_local) * co_bone
                # co_object_deform is the vertex coordinates in deformed mesh relative to object (421todo: is that true? relative to object or to world? if world, introduce armature.matrix_world)
                co_object_deform = pose_bone.matrix_channel * co_object
                # co_object_parent is the vertex coordinates in initial mesh relative to object, as if the deform was only due to the vertex's own weighted bone, and that parent bones didn't induce any deform
                co_object_parent = parent_pose_bone.matrix_channel.inverted() * co_object_deform
                
                # todo what follows is false, translation is by bone.head_local not bone.parent.head_local, should that be the case? (no see below, so what)
                # co_bone_parent is the vertex coordinates relative to weighted bone of parent in object space, with deforms from current bone only
                co_bone_parent = mathutils.Matrix.Translation(bone.head_local).inverted() * co_object_parent
                # co_bone_parent is a co_bone for the bone's parent!
                """
                #rot_matrix = mathutils.Matrix.Translation(bone.head_local).inverted() * parent_pose_bone.matrix_channel.inverted() * pose_bone.matrix_channel * mathutils.Matrix.Translation(bone.head_local) # works
                #rot_matrix = parent_pose_bone.matrix_channel.inverted() * pose_bone.matrix_channel # works too (makes sense...)
                rot_matrix = global_matrix * parent_pose_bone.matrix_channel.inverted() * pose_bone.matrix_channel * global_matrix.inverted()
                # with bone.parent.head_local : not a rotation matrix (has translation component)
                #rot_matrix = mathutils.Matrix.Translation(bone.parent.head_local).inverted() * parent_pose_bone.matrix_channel.inverted() * pose_bone.matrix_channel * mathutils.Matrix.Translation(bone.head_local)
                
                """
                co_init, co_deform in object space (or world space idk, see above, doesnt matter without object transform)
                
                game does
                co_deform = translate(loc_root_bone) * rot_matrix[root_bone] * translate(skel[bone]) * rot_matrix[bone] * ... * translate(skel[bone]) * rot_matrix[bone] * CONST[bone] * co_init
                
                where CONST[bone] can be chosen arbitrarily for each bone when writing vertices to .objex, can't change every frame
                in blender co_deform = pose_bone.matrix_channel * co_init
                
                assuming everything works:
                co_deform = pose_bone.matrix_channel * co_init
                co_deform = translate(loc_root_bone) * rot_matrix[root_bone] * translate(skel[bone]) * rot_matrix[bone] * ... * translate(skel[bone]) * rot_matrix[bone] * CONST[bone] * co_init
                co_deform = pose_bone.parent.matrix_channel * translate(skel[bone]) * rot_matrix[bone] * CONST[bone] * co_init
                
                pose_bone.matrix_channel = pose_bone.parent.matrix_channel * translate(skel[bone]) * rot_matrix[bone] * CONST[bone]
                
                rot_matrix[bone] = 1/translate(skel[bone]) * 1/pose_bone.parent.matrix_channel * pose_bone.matrix_channel * 1/CONST[bone]
                
                rot_matrix[bone].to_translation() must be 0 (?)
                rot_matrix[bone].transposed()*rot_matrix[bone] must be identity (fixme: maybe? idk how the translation part behaves, probably not regular matrix math):
                identity = rot_matrix[bone].transposed()*rot_matrix[bone]
                         = (1/translate(skel[bone]) * 1/pose_bone.parent.matrix_channel * pose_bone.matrix_channel * 1/CONST[bone]).transposed() * (1/translate(skel[bone]) * 1/pose_bone.parent.matrix_channel * pose_bone.matrix_channel * 1/CONST[bone])
                         = 1/CONST[bone].transposed() * pose_bone.matrix_channel.transposed() * 1/pose_bone.parent.matrix_channel.transposed() * 1/translate(skel[bone]).transposed() * 1/translate(skel[bone]) * 1/pose_bone.parent.matrix_channel * pose_bone.matrix_channel * 1/CONST[bone]
                CONST[bone].transposed() * CONST[bone] = pose_bone.matrix_channel.transposed() * 1/pose_bone.parent.matrix_channel.transposed() * 1/translate(skel[bone]).transposed() * 1/translate(skel[bone]) * 1/pose_bone.parent.matrix_channel * pose_bone.matrix_channel
                    doesnt look very constant...
                """
                # todo check if this varies between frames I guess... not too much hope to have
                print('const^T*const ?\n', pose_bone.matrix_channel.transposed() * pose_bone.parent.matrix_channel.inverted().transposed() * mathutils.Matrix.Translation(bone.head_local - bone.parent.head_local).inverted().transposed() * mathutils.Matrix.Translation(bone.head_local - bone.parent.head_local).inverted() * pose_bone.parent.matrix_channel.inverted() * pose_bone.matrix_channel)
            else:
                # ? not sure about root bone
                # guess we dont have the inverted part to the left because we stay in object space at the "end"
                #rot_matrix = pose_bone.matrix_channel * mathutils.Matrix.Translation(bone.head_local)
                rot_matrix = global_matrix * pose_bone.matrix_channel * global_matrix.inverted()
            print(bone_name)
            print(rot_matrix)
            
            """
            rotation_euler_zyx = rot_matrix.to_euler('ZYX')
            # 421fixme oot and blender seem to do math differently so either rot_matrix is computed wrong (should use oot math) or not euler ZYX or to_euler('ZYX') is lying idk
            #rotation_euler_zyx = rot_matrix.transposed().to_euler('XYZ')
            fw('rot %.3f %.3f %.3f\n' % (rotation_euler_zyx.x, rotation_euler_zyx.y, rotation_euler_zyx.z))
            """
            # 421todo .transposed() is the same for rotations, prob quicker
            # should check matrix is rotation at some point
            rotation_euler_zyx = rot_matrix.inverted().to_euler('ZYX')
            # -x -y -z works with global_matrix = identity
            fw('rot %.3f %.3f %.3f\n' % (-rotation_euler_zyx.x, -rotation_euler_zyx.y, -rotation_euler_zyx.z))
        #input() # 421todo remove "breakpoint"
