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
            if bone.parent:
                pos = pos.copy()
                pos -= bone.parent.head_local
            # 421todo confirm that bone root position is always assumed to be 0 by oot, if yes make sure WYSIWYG applies with the edit-mode location being accounted for in write_action_from_pose_bones
            else:
                # 421fixme better warnings, 
                if pos != mathutils.Vector((0,0,0)):
                    # 421todo instead of warn, automatically solve the problem (add a bone from (0,0,0) ?)
                    print('Warning: root bone does not start at armature origin, in-game results may vary')
            # 421todo use global_matrix, make sure this is correct
            pos = global_matrix * pos
            fw('%s+ %s %.6f %.6f %.6f\n' % (' ' * indent, bone.name, pos.x, pos.y, pos.z))
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
    global_matrix3 = global_matrix.to_3x3()
    global_matrix3_inv = global_matrix3.inverted()
    armature.animation_data.action = action
    
    pose_bones = armature.pose.bones
    root_pose_bone = pose_bones[root_bone.name]
    
    # 421todo this may become useful if we want to take into account object transform on mesh, but directly transforming the armature's child usually visually breaks the armature deform, so let's not?
    """
    mesh = armature.children[0]
    if len(armature.children) != 1:
        # 421todo not sure what to do here
        print('WARNING len(armature.children) != 1 -> using %s' % mesh.name)
    """
    # 421todo some of these warnings may be useless
    # 421todo figure out how to automatically solve the issues
    if armature.location != mathutils.Vector((0,0,0)):
        print('Warning: origin of armature %s %r is not world origin (0,0,0), in-game results may vary' % (armature.name, armature.location))
    for child in armature.children:
        if child.location != armature.location:
            print('Warning: origins of object %s %r and parent armature %s %r mismatch, in-game results may vary' % (child.name, child.location, armature.name, armature.location))
        if child.location != mathutils.Vector((0,0,0)):
            print('Warning: origin of object %s %r (parent armature %s) is not world origin (0,0,0), in-game results may vary' % (child.name, child.location, armature.name))
    
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
        # 421todo use global_matrix, make sure this is correct
        root_loc = global_matrix * root_loc
        fw('loc %.6f %.6f %.6f\n' % (root_loc.x, root_loc.y, root_loc.z))
        for bone in bones_ordered:
            pose_bone = pose_bones[bone.name]
            parent_pose_bone = pose_bone.parent
            
            """
            pose_bone.matrix_channel is the deform matrix in armature space
            We use the deform relative to parent (parent_pose_bone.matrix_channel.inverted() * pose_bone.matrix_channel)
            
            Reference:
                OoT: Matrix_JointPosition source (decomp at 0x800d1340)
                Blender: eulO_to_mat3 source
            """
            
            # 421todo what if armature/object transforms are not identity?
            if parent_pose_bone:
                # we only care about the 3x3 rotation part
                # for rotations, .transposed() is the same as .inverted()
                rot_matrix = parent_pose_bone.matrix_channel.to_3x3().transposed() * pose_bone.matrix_channel.to_3x3()
            else:
                # without a parent, transform can stay relative to armature (as if parent_pose_bone.matrix_channel = Identity)
                rot_matrix = pose_bone.matrix_channel.to_3x3()
            rot_matrix = global_matrix3 * rot_matrix * global_matrix3_inv
            
            # OoT actually uses XYZ Euler angles.
            rotation_euler_zyx = rot_matrix.to_euler('XYZ')
            fw('rot %.3f %.3f %.3f\n' % (rotation_euler_zyx.x, rotation_euler_zyx.y, rotation_euler_zyx.z))
