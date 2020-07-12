import bpy
import mathutils

from . import util
from .logging_util import getLogger


def write_skeleton(file_write_skel, global_matrix, object_transform, armature, armature_name_q, bones_ordered):
    log = getLogger('anim')
    fw = file_write_skel
    objex_data = armature.data.objex_bonus
    fw('newskel %s' % armature_name_q)
    if objex_data.type != 'NONE':
        fw(' %s' % objex_data.type)
    fw('\n')
    if objex_data.segment:
        fw('segment %s%s%s\n' % (
            '' if objex_data.segment.startswith('0x') else '0x',
            objex_data.segment,
            ' local' if objex_data.segment_local else ''
        ))
    if objex_data.pbody:
        fw('pbody')
        if objex_data.pbody_parent_object:
            # 421todo escape, make sure name written here is same as in target's newskel
            fw(' parent %s %s' % (objex_data.pbody_parent_object.name, objex_data.pbody_parent_bone))
        fw('\n')
    indent = 0
    stack = [None]
    for bone in bones_ordered:
        #print('indent=%d bone=%s parent=%s stack=%r' % (indent, bone.name, bone.parent.name if bone.parent else 'None', stack))
        while bone.parent != stack[-1]:
            indent -= 1
            fw('%s-\n' % (' ' * indent))
            stack.pop()
        pos = global_matrix * object_transform * bone.head_local
        if bone.parent:
            pos = pos.copy()
            pos -= global_matrix * object_transform * bone.parent.head_local
        # 421todo this warning looks very outdated now that we use object transform
        # 421todo confirm that bone root position is always assumed to be 0 by oot, if yes make sure WYSIWYG applies with the edit-mode location being accounted for in write_action_from_pose_bones
        else:
            # 421fixme better warnings, 
            if bone.head_local != mathutils.Vector((0,0,0)):
                # 421todo instead of warn, automatically solve the problem (add a bone from (0,0,0) ?)
                log.warning('root bone {} at {!r} does not start at armature origin, in-game results may vary', bone.name, pos)
        fw('%s+ %s %.6f %.6f %.6f\n' % (' ' * indent, util.quote(bone.name), pos.x, pos.y, pos.z))
        indent += 1
        stack.append(bone)
    while indent > 0:
        indent -= 1
        fw('%s-\n' % (' ' * indent))
    fw('\n')

def order_bones(armature):
    log = getLogger('anim')
    """
    find root bone in armature
    list bones in hierarchy order, preserving the armature order
    """
    bones = armature.data.bones
    root_bone = None
    bones_ordered = []
    skipped_bones = []
    for bone in bones:
        # 421todo skip bones assigned to no vertex if they're root
        # 421todo do not skip non-root bones if parent isnt skipped
        if not bone.use_deform:
            log.info('Skipping non-deform bone {} (intended for eg IK bones)', bone.name)
            skipped_bones.append(bone)
            continue
        bone_parents = bone.parent_recursive
        for skipped_bone in skipped_bones:
            # 421todo does "in" work with bone objects?
            if skipped_bone in bone_parents:
                log.error('bone {} has bone {} in its parents, but that bone was skipped', bone.name, skipped_bone.name)
        # make sure there is only one root bone
        root_parent_bone = bone_parents[-1] if bone_parents else bone
        if root_bone and root_parent_bone.name != root_bone.name:
            # 421todo
            log.debug('bone_parents={!r} root_bone={!r} root_parent_bone={!r}', bone_parents, root_bone, root_parent_bone)
            log.error('armature {} has multiple root bones, at least {} and {}', armature.name, root_bone.name, root_parent_bone.name)
        root_bone = root_parent_bone
        
        # preserve ordering from armature
        if bone_parents:
            # from top parent to closest parent
            for parent in reversed(bone_parents):
                if parent not in bones_ordered:
                    bones_ordered.append(parent)
        bones_ordered.append(bone)
    
    return root_bone, bones_ordered

def write_armatures(file_write_skel, file_write_anim, scene, global_matrix, armatures):
    log = getLogger('anim')

    # user_ variables store parameters (potentially) used by the script and to be restored later
    user_frame_current = scene.frame_current
    user_frame_subframe = scene.frame_subframe
    
    # 421todo force 20 fps somewhere?
    scene_fps = scene.render.fps / scene.render.fps_base
    if scene_fps != 20:
        log.warning('animations are being viewed at {:.1f} fps (change this in render settings), but will be used at 20 fps', scene_fps)

    # armatures is built in ObjexWriter#write_object in export_objex.py (look for self.armatures)
    for armature_name_q, armature, object_transform, armature_actions in armatures:
        if armature.animation_data:
            user_armature_action = armature.animation_data.action
        
        root_bone, bones_ordered = order_bones(armature)
        
        if not bones_ordered:
            # 421todo abort?
            log.error('armature {} has no bones', armature.name)
        
        if file_write_skel:
            write_skeleton(file_write_skel, global_matrix, object_transform, armature, armature_name_q, bones_ordered)
        
        if file_write_anim:
            if armature.animation_data:
                write_animations(file_write_anim, scene, global_matrix, object_transform, armature, armature_name_q, root_bone, bones_ordered, armature_actions)
            else:
                log.warning(
                    'Skipped exporting actions {!r} with armature {} because the armature did not have animation_data '
                    '(consider unchecking "Export all actions" under Objex armature properties; '
                    'if you do want actions to be exported with this armature, animation_data can be initialized by creating a dummy action by adding a keyframe in pose mode)'
                    , armature_actions, armature.name
                )
        
        if armature.animation_data:
            armature.animation_data.action = user_armature_action
    
    scene.frame_set(user_frame_current, user_frame_subframe)

def write_animations(file_write_anim, scene, global_matrix, object_transform, armature, armature_name_q, root_bone, bones_ordered, actions):
    fw = file_write_anim
    fw('# %s\n' % armature.name)
    for action in actions:
        frame_start, frame_end = action.frame_range
        frame_count = int(frame_end - frame_start + 1) # 421fixme is this correct?
        fw('newanim %s %s %d\n' % (armature_name_q, util.quote(action.name), frame_count))
        write_action(fw, scene, global_matrix, object_transform, armature, root_bone, bones_ordered, action, frame_start, frame_count)
        fw('\n')
    fw('\n')

def write_action(fw, scene, global_matrix, object_transform, armature, root_bone, bones_ordered, action, frame_start, frame_count):
    log = getLogger('anim')
    transform = global_matrix * object_transform
    transform3 = transform.to_3x3()
    transform3_inv = transform3.inverted()

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
        log.warning('origin of armature {} {!r} is not world origin (0,0,0), in-game results may vary', armature.name, armature.location)
    for child in armature.children:
        if child.location != armature.location:
            log.warning('origins of object {} {!r} and parent armature {} {!r} mismatch, in-game results may vary', child.name, child.location, armature.name, armature.location)
        if child.location != mathutils.Vector((0,0,0)):
            log.warning('origin of object {} {!r} (parent armature {}) is not world origin (0,0,0), in-game results may vary', child.name, child.location, armature.name)
    
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
        root_loc = root_pose_bone.head # armature space
        root_loc = transform * root_loc
        fw('loc %.6f %.6f %.6f\n' % (root_loc.x, root_loc.y, root_loc.z)) # 421todo what about "ms"
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
            rot_matrix = transform3 * rot_matrix * transform3_inv

            # OoT actually uses XYZ Euler angles.
            rotation_euler_zyx = rot_matrix.to_euler('XYZ')
            # 5 digits: precision of s16 angles in radians is 2pi/2^16 ~ ‭0.000096
            fw('rot %.5f %.5f %.5f\n' % (rotation_euler_zyx.x, rotation_euler_zyx.y, rotation_euler_zyx.z))
