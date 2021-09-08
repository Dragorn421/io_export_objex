#  Copyright 2021 Dragorn421
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

import mathutils

from .. import blender_version_compatibility

from ..util import CollectAbort
from ..logging_util import getLogger


class CollectedBone:
    def __init__(self, name, parent, head_world):
        self.name = name
        self.parent = parent
        self.head_world = head_world

    def __repr__(self):
        return repr(self.__dict__)


class CollectedActionFrame:
    def __init__(self, loc, rots):
        self.loc = loc
        self.rots = rots

    def __repr__(self):
        return repr(self.__dict__)


class CollectedAction:
    def __init__(self, name, frames):
        self.name = name
        self.frames = frames

    def __repr__(self):
        return repr(self.__dict__)


class CollectedArmature:
    def __init__(self, bones_ordered, actions):
        self.bones_ordered = bones_ordered
        self.actions = actions

    def __repr__(self):
        return repr(self.__dict__)


def collect_armature(scene, armature_object, transform, actions):
    log = getLogger("collect_armature")
    # list bones in hierarchy order (starting with the root bone), preserving the armature order
    bones = armature_object.data.bones
    root_bone = None
    bones_ordered = []
    skipped_bones = []
    for bone in bones:
        # 421todo skip bones assigned to no vertex if they're root
        # 421todo do not skip non-root bones if parent isnt skipped
        if not bone.use_deform:
            log.info(
                "Skipping non-deform bone {} (intended for eg IK bones)", bone.name
            )
            skipped_bones.append(bone)
            continue
        bone_parents = bone.parent_recursive
        for skipped_bone in skipped_bones:
            if skipped_bone in bone_parents:
                log.error(
                    "bone {} has bone {} in its parents, but that bone was skipped",
                    bone.name,
                    skipped_bone.name,
                )
        # make sure there is only one root bone
        root_parent_bone = bone_parents[-1] if bone_parents else bone
        if root_bone is not None and root_parent_bone.name != root_bone.name:
            log.debug(
                "bone_parents={!r} root_bone={!r} root_parent_bone={!r}",
                bone_parents,
                root_bone,
                root_parent_bone,
            )
            log.error(
                "armature {} has multiple root bones, at least {} and {}",
                armature_object.name,
                root_bone.name,
                root_parent_bone.name,
            )
        root_bone = root_parent_bone

        # preserve ordering from armature
        if bone_parents:
            # from top parent to closest parent
            for parent in reversed(bone_parents):
                if parent not in bones_ordered:
                    bones_ordered.append(parent)
        bones_ordered.append(bone)

    collected_bones_dict = dict()
    collected_bones_ordered = []
    for bone in bones_ordered:
        if bone.parent is not None:
            # the parent should come before and have been collected already
            parent_collected_bone = collected_bones_dict[bone.parent.name]
        else:
            parent_collected_bone = None
            if bone.head_local != mathutils.Vector((0, 0, 0)):
                log.debug(
                    "root bone {} at {!r} does not start at armature origin",
                    bone.name,
                    bone.head_local,
                )
        collected_bone = CollectedBone(
            bone.name,
            parent_collected_bone,
            blender_version_compatibility.matmul(transform, bone.head_local),
        )
        collected_bones_dict[bone.name] = collected_bone
        collected_bones_ordered.append(collected_bone)

    collected_actions = []

    if armature_object.animation_data is not None:
        user_armature_action = armature_object.animation_data.action

        for action in actions:
            collected_action = collect_action(scene, armature_object, transform, action)
            collected_actions.append(collected_action)

        armature_object.animation_data.action = user_armature_action
    else:
        # 421todo this warning may be a bit outdated with the ability to pick actions on a per-armature basis
        log.warning(
            "Skipped collecting actions {!r} with armature {},\n"
            "because the armature did not have animation_data\n"
            '(consider unchecking "Export all actions" under Objex armature properties;\n'
            "if you do want actions to be exported with this armature,\n"
            "animation_data can be initialized by creating a dummy action by adding a keyframe in pose mode)",
            actions,
            armature_object,
        )

    return CollectedArmature(collected_bones_ordered, collected_actions)


def collect_action(scene, armature_object, transform, action):
    log = getLogger("collect_armature")

    transform3 = transform.to_3x3()
    transform3_inv = transform3.inverted()

    armature_object.animation_data.action = action

    if armature_object.location != mathutils.Vector((0, 0, 0)):
        log.debug(
            "origin of armature {} {!r} is not world origin (0,0,0)",
            armature_object.name,
            armature_object.location,
        )
    for child in armature_object.children:
        if child.location != armature_object.location:
            log.debug(
                "origins of object {} {!r} and parent armature {} {!r} mismatch",
                child.name,
                child.location,
                armature_object.name,
                armature_object.location,
            )
        if child.location != mathutils.Vector((0, 0, 0)):
            log.debug(
                "origin of object {} {!r} (parent armature {}) is not world origin (0,0,0)",
                child.name,
                child.location,
                armature_object.name,
            )

    collected_frames = []

    frame_start, frame_end = action.frame_range
    frame_count = int(frame_end - frame_start + 1)

    for frame_current_offset in range(frame_count):
        frame_current = frame_start + frame_current_offset
        scene.frame_set(frame_current)

        root_loc = None
        rots = dict()

        for pose_bone in armature_object.pose.bones:
            parent_pose_bone = pose_bone.parent

            """
            pose_bone.matrix_channel is the deform matrix in armature space
            We use the deform relative to parent (parent_pose_bone.matrix_channel.inverted() * pose_bone.matrix_channel)
            
            Reference:
                OoT: Matrix_JointPosition source (decomp at 0x800d1340)
                Blender: eulO_to_mat3 source
            """

            # 421todo what if armature/object transforms are not identity?
            if parent_pose_bone is not None:
                # we only care about the 3x3 rotation part
                # for rotations, .transposed() is the same as .inverted()
                rot_matrix = blender_version_compatibility.matmul(
                    parent_pose_bone.matrix_channel.to_3x3().transposed(),
                    pose_bone.matrix_channel.to_3x3(),
                )
            else:
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
                root_loc = pose_bone.head  # armature space
                root_loc = blender_version_compatibility.matmul(transform, root_loc)

                # without a parent, transform can stay relative to armature (as if parent_pose_bone.matrix_channel = Identity)
                rot_matrix = pose_bone.matrix_channel.to_3x3()

            rot_matrix = blender_version_compatibility.matmul(
                blender_version_compatibility.matmul(transform3, rot_matrix),
                transform3_inv,
            )

            # OoT actually uses ZYX Euler angles, for some reason this works. FIXME Find out what's wrong eventually
            rot = rot_matrix.to_euler("XYZ")

            rots[pose_bone.name] = rot

        collected_frames.append(CollectedActionFrame(root_loc, rots))

    return CollectedAction(action.name, collected_frames)
