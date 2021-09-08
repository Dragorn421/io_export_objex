#  Copyright 2020-2021 Dragorn421
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

import bpy
import io
import contextlib

from .logging_util import getLogger
from . import util

# set in register()
log = None
km_view3d_copybuffer_wrapper = None
kmi_view3d_copybuffer_wrapper = None

# monkeypatch view3d.copybuffer crash

# wrap view3d.copybuffer operator

class OBJEX_OT_view3d_copybuffer_wrapper(bpy.types.Operator):
    """
    421todo

    for each material of the copied selection (or every material in the blend if
    we can't tell what is being copied idk), encode nodes or do something so they can carry
    over and save any data to a hidden Material property

    instead of trying to copy groups, may be easier for a future next iteration of this wrapper
    to assume every copy/paste source/target would use the same addon version, and assume
    every material/blend has up-to-date groups everywhere (can check in copy wrapper if
    material is updated, can check in future paste wrapper if version matches too)

    2nd part: wrap pastebuffer operator to receive data

    bonus?: make copied data "compatible" (visually) with any blender install (aka even
    without the addon) by making node setup not use any objex stuff
    """

    # reference: see view3d_copybuffer_exec at
    # https://github.com/blender/blender/blob/2d1cce8331f3ecdfb8cb0c651e111ffac5dc7153/source/blender/editors/space_view3d/view3d_ops.c#L62
    # and (in the same file) operator registration

    bl_idname = 'objex.view3d_copybuffer_wrapper'
    bl_label = 'Objex wrapper for operator view3d.copybuffer'

    @classmethod
    def poll(self, context):
        return bpy.ops.view3d.copybuffer.poll()

    def execute(self, context):
        bpy.ops.ed.undo_push()

        # remove node groups (overkill)
        for material in bpy.data.materials:
            if material.node_tree:
                if material.node_tree.nodes:
                    group_nodes = tuple(n for n in material.node_tree.nodes if n.type == 'GROUP')
                    for group_node in group_nodes:
                        material.node_tree.nodes.remove(group_node)

        # call vanilla view3d.copybuffer operator and capture/report its output
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            bpy.ops.view3d.copybuffer()
        stdout = stdout.getvalue()
        log.debug('stdout = {!r}', stdout)
        for line in stdout.split('\n'):
            if not line:
                continue
            parts = line.split(': ', maxsplit=1)
            if len(parts) == 2:
                lvl, msg = parts
            else:
                lvl, msg = 'INFO', line
            self.report({lvl.upper()}, '(Objex Wrapper) %s' % msg)

        # undo node groups removal
        bpy.ops.ed.undo()

        return {'FINISHED'}


# handle user-defined patch method (in addon preferences) and view3d.copybuffer hotkey (Ctrl+C by default)

def get_context_user_keymaps():
    return bpy.context.window_manager.keyconfigs.user.keymaps
def get_view3d_copybuffer_keymap_item():
    return get_context_user_keymaps()['3D View'].keymap_items['view3d.copybuffer']

def get_view3d_copybuffer_keymap_item_active():
    return get_view3d_copybuffer_keymap_item().active

def set_view3d_copybuffer_keymap_item_active(active):
    log.debug('active <- {!r}', active)
    get_view3d_copybuffer_keymap_item().active = active

def monkeyPatch_view3d_copybuffer_update(addon_preferences, context):
    log.debug('!')
    patchMethod = addon_preferences.monkeyPatch_view3d_copybuffer
    active_user = addon_preferences.monkeyPatch_view3d_copybuffer_active_user
    log.debug('patchMethod = {!r}', patchMethod)
    log.debug('active_user = {!r}', active_user)
    if patchMethod == 'AUTO':
        patchMethod = 'WRAPPER_DELETE'
        log.debug('patchMethod <- {!r}', patchMethod)
    if patchMethod == 'NOTHING':
        if active_user != 'None': # True, False
            set_view3d_copybuffer_keymap_item_active(active_user == 'True')
            active_user = 'None'
    else: # DISABLE, WRAPPER_DELETE
        if active_user == 'None':
            active_user = ('True' if get_view3d_copybuffer_keymap_item_active() else 'False')
        set_view3d_copybuffer_keymap_item_active(False)
    global kmi_view3d_copybuffer_wrapper
    kmi_view3d_copybuffer_wrapper.active = (patchMethod == 'WRAPPER_DELETE')
    log.debug('active_user <- {!r}', active_user)
    addon_preferences.monkeyPatch_view3d_copybuffer_active_user = active_user


# (un)registering

handlers = (
    bpy.app.handlers.load_post,
    # 421fixme in 2.82 depsgraph_update_pre runs much less often, would need to use the new handler stuff
    bpy.app.handlers.scene_update_pre if hasattr(bpy.app.handlers, 'scene_update_pre') else bpy.app.handlers.depsgraph_update_pre,
)

def remove_from_handlers():
    for handler in handlers:
        if monkeyPatch_view3d_copybuffer_handler in handler:
            handler.remove(monkeyPatch_view3d_copybuffer_handler)

@bpy.app.handlers.persistent
def monkeyPatch_view3d_copybuffer_handler(_):
    addon_preferences = util.get_addon_preferences()
    if addon_preferences is None:
        log.debug('No addon preferences (yet?)')
        return
    kc = bpy.context.window_manager.keyconfigs.addon if addon_preferences else None
    # don't call get_context_user_keymaps if addon_preferences or kc isn't defined (if --background)
    if addon_preferences and kc and not get_context_user_keymaps():
        log.debug('No keymaps (yet)')
        return
    log.debug('!')
    if kc:
        # 421fixme 'Object Mode' means copying is possible in less contexts than vanilla view3d.copybuffer (see below for attempts at not using 'Object Mode'...)
        km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')

        # those parameters are the exact ones used for view3d.copybuffer:
        # https://github.com/blender/blender/blob/29eb8916587be9bc58418937e86802b3d4eca4a3/release/scripts/presets/keyconfig/keymap_data/blender_default.py#L929
        # https://github.com/blender/blender/blob/6c9178b183f5267e07a6c55497b6d496e468a709/release/scripts/modules/bl_keymap_utils/io.py#L244
        # and it will NOT work
        # also same name, space_type, region_type as bpy.context.window_manager.keyconfigs.user.keymaps['3D View']
        # note: in the UI view3d.copybuffer is under "3D View" then "3D View (Global)",
        # and using 'Object Mode' here puts the mapping under "3D View" then "Object Mode"
        # no idea where these names/relations come from...
        #km = kc.keymaps.new(name='3D View', space_type='VIEW_3D', region_type='WINDOW')

        kmi_vanilla = get_view3d_copybuffer_keymap_item()
        kmi = km.keymap_items.new(
            'objex.view3d_copybuffer_wrapper',
            kmi_vanilla.type, kmi_vanilla.value,
            any=kmi_vanilla.any, shift=kmi_vanilla.shift, ctrl=kmi_vanilla.ctrl,
            alt=kmi_vanilla.alt, oskey=kmi_vanilla.oskey, key_modifier=kmi_vanilla.key_modifier
        )

        global km_view3d_copybuffer_wrapper, kmi_view3d_copybuffer_wrapper
        km_view3d_copybuffer_wrapper = km
        kmi_view3d_copybuffer_wrapper = kmi

        monkeyPatch_view3d_copybuffer_update(addon_preferences, bpy.context)
    else:
        log.info('Ignored patching, no keyconfig available (Blender is likely in background mode)')
    # remove from handlers after first call
    remove_from_handlers()


classes = (
    OBJEX_OT_view3d_copybuffer_wrapper,
)

def register():
    global log
    log = getLogger('view3d_copybuffer_patch')

    for clazz in classes:
        bpy.utils.register_class(clazz)

    # cannot set key mapping during register, so we do it as soon as possible using handlers
    for handler in handlers:
        handler.append(monkeyPatch_view3d_copybuffer_handler)
    log.debug('handler appended')

def unregister():
    log.debug('!')

    # key mapping
    global km_view3d_copybuffer_wrapper, kmi_view3d_copybuffer_wrapper
    if km_view3d_copybuffer_wrapper:
        if kmi_view3d_copybuffer_wrapper:
            km_view3d_copybuffer_wrapper.keymap_items.remove(kmi_view3d_copybuffer_wrapper)
        bpy.context.window_manager.keyconfigs.addon.keymaps.remove(km_view3d_copybuffer_wrapper)

    # in the seemingly unlikely event monkeyPatch_view3d_copybuffer_handler isn't called and doesn't remove itself, remove it here
    remove_from_handlers()
    # restore view3d.copybuffer key mapping if needed
    addon_preferences = util.get_addon_preferences()
    if addon_preferences and addon_preferences.monkeyPatch_view3d_copybuffer_active_user != 'None':
        set_view3d_copybuffer_keymap_item_active(addon_preferences.monkeyPatch_view3d_copybuffer_active_user == 'True')

    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
