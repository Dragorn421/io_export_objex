import bpy
import mathutils

import re
import ast

def write_skel(file_write_skel, skeletons):
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
            # 421todo bone.tail?
            pos = bone.tail
            fw('%s+ %s %.6f %.6f %.6f\n' % (' ' * indent, bone.name, pos.x, pos.y, pos.z))
            indent += 1
            stack.append(bone)
        while indent > 0:
            indent -= 1
            fw('%s-\n' % (' ' * indent))
        fw('\n')

# depth-first traversal of the skeleton
def order_bones(root_bone):
    bones_ordered = []
    stack = [root_bone]
    while stack:
        bone = stack.pop()
        bones_ordered.append(bone)
        if bone.children:
            stack.extend(bone.children)
    return bones_ordered

def write_anim(file_write_anim, file_write_skel, scene, armatures):
    fw = file_write_anim
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
        armature_name = armature.name
        # find root bone, list all child bones
        # 421todo not sure which one to use, shouldn't matter as long as bones have the same names
        #pose_bones = armature.pose.bones
        bones = armature.data.bones
        root_bone = None
        for bone in bones:
            bone_parents = bone.parent_recursive
            root_parent_bone = bone_parents[-1] if bone_parents else bone
            if root_bone and root_parent_bone.name != root_bone.name:
                # 421todo
                print('bone_parents=%r root_bone=%r root_parent_bone=%r' % (bone_parents,root_bone,root_parent_bone))
                print('Error: armature %s has multiple root bones, at least %s and %s' % (armature_name, root_bone.name, root_parent_bone.name))
            root_bone = root_parent_bone
        #child_bones = [bone for bone in bones if bone is not root_bone]
        del bone_parents, root_parent_bone, bones
        if root_bone is None:
            # 421todo
            print('Error: armature %s has no bones' % armature_name)
        ordered_bones = order_bones(root_bone)
        bones_idx = {bone.name: bone_idx for bone_idx, bone in enumerate(ordered_bones)}
        skeletons.append((armature, ordered_bones))
        del ordered_bones
        # write animations
        fw('# %s\n' % armature_name)
        for action in armature_actions:
            frame_start, frame_end = action.frame_range
            frame_count = int(frame_end - frame_start + 1)
            fw('newanim %s %s %d\n' % (armature_name, action.name, frame_count))
            # find fcurves associated to each bone
            fcurve_root_bone_location = [None,None,None]
            fcurve_bones_rotation = [[None] * len(bones_idx) for _i in range(4)]
            for fcurve in action.fcurves:
                match = re.match(r'pose.bones\[(.*)\].([a-z_]+)', fcurve.data_path)
                if not match:
                    # 421todo idk
                    print('skipping unknown animated data path %s' % fcurve.data_path)
                    continue
                fcurve_bone_name = ast.literal_eval(match.group(1))
                fcurve_target = match.group(2)
                if fcurve_target == 'location':
                    if fcurve_bone_name == root_bone.name:
                        if not fcurve_root_bone_location[fcurve.array_index]:
                            fcurve_root_bone_location[fcurve.array_index] = fcurve
                        else:
                            print('skipping duplicate fcurve for location of root bone %s' % fcurve.data_path)
                            continue
                    else:
                        print('skipping location of non-root bone %s' % fcurve.data_path)
                        continue
                elif fcurve_target == 'rotation_quaternion':
                    bone_idx = bones_idx[fcurve_bone_name]
                    if not fcurve_bones_rotation[fcurve.array_index][bone_idx]:
                        fcurve_bones_rotation[fcurve.array_index][bone_idx] = fcurve
                    else:
                        print('skipping duplicate fcurve for rotation of bone %s' % fcurve.data_path)
                        continue
                else:
                    print('skipping unknown animated data %s' % fcurve.data_path)
                    continue
            # 421todo check all 4 wxyz have fcurve whenever at least one is set, same for loc xyz
            for frame_current_offset in range(frame_count):
                frame_current = frame_start + frame_current_offset
                print('loc fcurve evaluation %r' % [fc.evaluate(frame_current) if fc else 'X' for fc in fcurve_root_bone_location])
                fw('loc %.6f %.6f %.6f\n' % tuple([fc.evaluate(frame_current) if fc else 0 for fc in fcurve_root_bone_location]))
                for bone_idx in range(len(bones_idx)):
                    # 421todo ... this is ugly
                    fw('rot %.3f %.3f %.3f\n' % tuple([_r for _r in mathutils.Vector(mathutils.Quaternion([fc.evaluate(frame_current) if fc else 0 for fc in [fcurve_bones_rotation[_i][bone_idx] for _i in range(4)]]).to_euler()).zyx]))
            fw('\n')
        fw('\n')
    write_skel(file_write_skel, skeletons)
