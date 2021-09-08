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

def write_animations(file_write_anim, collected_armature, link_anim_basepath, link_bin_scale):
    log = getLogger('anim')
    fw = file_write_anim
    fw('# %s\n' % collected_armature.name)

    if link_anim_basepath is not None and len(collected_armature.bones_ordered) != 21:
        log.warning('Requested exporting Link animation binary, but armature does not have 21 bones')
        link_anim_basepath = None

    for collected_action in collected_armature.actions:
        frame_count = len(collected_action.frames)
        fw('newanim %s %s %d\n' % (collected_armature.name_q, util.quote(collected_action.name), frame_count))

        link_anim_file = None
        if link_anim_basepath is not None:
            link_anim_filename = link_anim_basepath + ''.join(c for c in collected_action.name if c.isalnum()) + '_' + str(frame_count) + '.bin'
            link_anim_file = open(link_anim_filename, 'wb')

        try:
            write_action(fw, collected_armature, collected_action, link_anim_file, link_bin_scale)
        finally:
            if link_anim_file is not None:
                link_anim_file.close()

        fw('\n')

    fw('\n')

def write_action(fw, collected_armature, collected_action, link_anim_file, link_bin_scale):
    log = getLogger('anim')

    def link_write_shorts(x, y, z):
        link_anim_file.write(bytes([(x>>8)&0xFF, x&0xFF, (y>>8)&0xFF, y&0xFF, (z>>8)&0xFF, z&0xFF]))

    if link_anim_file is not None:
        # FIXME
        eyes_bone = pose_bones.get('Eyes')
        mouth_bone = pose_bones.get('Mouth')
        if eyes_bone is None:
            log.warning('Eyes animation index bone not found (bone with name Eyes)')
        if mouth_bone is None:
            log.warning('Mouth animation index bone not found (bone with name Mouth)')

    for collected_frame in collected_action.frames:
        root_loc = collected_frame.loc
        fw('loc %.6f %.6f %.6f\n' % (root_loc.x, root_loc.y, root_loc.z)) # 421todo what about "ms"
        if link_anim_file is not None:
            x = int(root_loc.x * link_bin_scale)
            y = int(root_loc.y * link_bin_scale)
            z = int(root_loc.z * link_bin_scale)
            if any(n < -0x8000 or n > 0x7FFF for n in [x, y, z]):
                log.warning('Link anim position values out of range')
            link_write_shorts(x, y, z)
        #TODO
        for bone in collected_armature.bones_ordered:
            rot = collected_frame.rots[bone.name]
            # 5 digits: precision of s16 angles in radians is 2pi/2^16 ~ ‭0.000096
            fw('rot %.5f %.5f %.5f\n' % (rot.x, rot.y, rot.z))
            if link_anim_file is not None:
                def rad_to_shortang(r):
                    r *= 0x8000 / math.pi
                    r = int(r) & 0xFFFF
                    if r >= 0x8000:
                        r -= 0x10000
                    return r
                link_write_shorts(rad_to_shortang(rot.x), rad_to_shortang(rot.y), rad_to_shortang(rot.z))
        
        if link_anim_file is not None:
            texanimvalue = 0
            if eyes_bone is not None:
                i = round(eyes_bone.head.x) # Want it in armature space, not transform space
                if i < -1 or i > 7:
                    log.warning('Link eye index (Eyes bone X value) out of range -1 to 7')
                    if i < -1 or i > 14:
                        i = -1
                texanimvalue |= i+1
            if mouth_bone is not None:
                i = round(mouth_bone.head.x)
                if i < -1 or i > 3:
                    log.warning('Link mouth index (Mouth bone X value) out of range -1 to 3')
                    if i < -1 or i > 14:
                        i = -1
                texanimvalue |= (i+1) << 4
            link_anim_file.write(texanimvalue.to_bytes(2, byteorder='big'))
