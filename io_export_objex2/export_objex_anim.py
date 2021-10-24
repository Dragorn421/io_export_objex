#  Copyright 2020-2021 Dragorn421, Sauraen
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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from export_collect import collect_armature

import bpy
import mathutils
import math

from . import util
from .logging_util import getLogger


def write_skeleton(file_write_skel, collected_armature):
    log = getLogger('anim')
    fw = file_write_skel
    objex_data = collected_armature.objex_bonus
    fw("newskel {}".format(collected_armature.name_q))
    if objex_data.type != 'NONE':
        fw(" {}".format(objex_data.type))
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
            if blender_version_compatibility.no_ID_PointerProperty:
                pbody_parent_object_name = objex_data.pbody_parent_object
            else:
                pbody_parent_object_name = objex_data.pbody_parent_object.name
            fw(' parent %s %s' % (util.quote(pbody_parent_object_name), util.quote(objex_data.pbody_parent_bone)))
        fw('\n')
    indent = 0
    stack = [None]
    for collected_bone in collected_armature.bones_ordered:
        #print('indent=%d bone=%s parent=%s stack=%r' % (indent, bone.name, bone.parent.name if bone.parent else 'None', stack))
        while collected_bone.parent != stack[-1]:
            indent -= 1
            fw('%s-\n' % (' ' * indent))
            stack.pop()
        pos = collected_bone.head_world
        if collected_bone.parent:
            pos = pos.copy()
            pos -= collected_bone.parent.head_world
        fw('%s+ %s %.6f %.6f %.6f\n' % (' ' * indent, util.quote(collected_bone.name), pos.x, pos.y, pos.z))
        indent += 1
        stack.append(collected_bone)
    while indent > 0:
        indent -= 1
        fw('%s-\n' % (' ' * indent))
    fw('\n')

def write_armatures(file_write_skel, file_write_anim, collected_armatures, link_anim_basepath, link_bin_scale):
    log = getLogger('anim')

    log.trace("collected_armatures = {!r}", collected_armatures)

    for collected_armature in collected_armatures:
        if not collected_armature.bones_ordered:
            # 421todo abort?
            log.error('armature {} has no bones', collected_armature.name)

        if file_write_skel:
            write_skeleton(file_write_skel, collected_armature)

        if file_write_anim and collected_armature.actions:
            write_animations(file_write_anim, collected_armature, link_anim_basepath, link_bin_scale)

def write_animations(
    file_write_anim,
    collected_armature,  # type: collect_armature.CollectedArmature
    link_anim_basepath,
    link_bin_scale,
):
    log = getLogger('anim')
    fw = file_write_anim
    fw('# %s\n' % collected_armature.name)

    for collected_action in collected_armature.actions:
        frame_count = len(collected_action.frames)
        fw('newanim %s %s %d\n' % (collected_armature.name_q, util.quote(collected_action.name), frame_count))

        write_action(fw, collected_armature, collected_action)

        fw('\n')

    fw('\n')

    # TODO untested: binary link anim export
    # FIXME this is non functional anyway, the collect side isn't implemented
    # (nothing sets collected_armature.link_anims ever)
    if hasattr(collected_armature, "link_anims") and link_anim_basepath is not None:
        if len(collected_armature.bones_ordered) != 21:
            log.warning('Requested exporting Link animation binary, but armature does not have 21 bones')
        else:
            for collected_link_anim in collected_armature.link_anims:
                frame_count = len(collected_link_anim.frames)
                link_anim_filename = "{}{}_{}.bin".format(
                    link_anim_basepath,
                    ''.join(c for c in collected_link_anim.name if c.isalnum()),
                    frame_count,
                )
                with open(link_anim_filename, 'wb') as link_anim_file:
                    write_link_anim_bin(link_anim_file, link_bin_scale, collected_armature, collected_link_anim)

def write_action(
    fw,
    collected_armature,  # type: collect_armature.CollectedArmature
    collected_action,  # type: collect_armature.CollectedAction
):
    log = getLogger('anim')

    for collected_frame in collected_action.frames:
        root_loc = collected_frame.loc
        fw('loc %.6f %.6f %.6f\n' % (root_loc.x, root_loc.y, root_loc.z)) # 421todo what about "ms"

        for bone in collected_armature.bones_ordered:
            rot = collected_frame.rots[bone.name]
            # 5 digits: precision of s16 angles in radians is 2pi/2^16 ~ ‭0.000096
            fw('rot %.5f %.5f %.5f\n' % (rot.x, rot.y, rot.z))

def write_link_anim_bin(
    link_anim_file,
    link_bin_scale,
    collected_armature,  # type: collect_armature.CollectedArmature
    collected_link_anim,
):
    log = getLogger('anim')

    def link_write_shorts(x, y, z):
        link_anim_file.write(bytes([(x>>8)&0xFF, x&0xFF, (y>>8)&0xFF, y&0xFF, (z>>8)&0xFF, z&0xFF]))

    def rad_to_shortang(r):
        r *= 0x8000 / math.pi
        r = int(r) & 0xFFFF
        if r >= 0x8000:
            r -= 0x10000
        return r

    for collected_link_frame in collected_link_anim.frames:
        root_loc = collected_link_frame.loc
        x = int(root_loc.x * link_bin_scale)
        y = int(root_loc.y * link_bin_scale)
        z = int(root_loc.z * link_bin_scale)
        if any(n < -0x8000 or n > 0x7FFF for n in [x, y, z]):
            log.warning('Link anim position values out of range')
        link_write_shorts(x, y, z)

        for bone in collected_armature.bones_ordered:
            rot = collected_link_frame.rots[bone.name]
            link_write_shorts(rad_to_shortang(rot.x), rad_to_shortang(rot.y), rad_to_shortang(rot.z))

        texanimvalue = (
            (collected_link_frame.eye_index + 1)
            | ((collected_link_frame.mouth_index + 1) << 4)
        )
        link_anim_file.write(texanimvalue.to_bytes(2, byteorder='big'))
