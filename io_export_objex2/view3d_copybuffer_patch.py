import bpy

from .logging_util import getLogger

log = getLogger('view3d_copybuffer_patch')

# monkeypatch view3d.copybuffer crash

def get_view3d_copybuffer_keymap_item_active():
    return bpy.data.window_managers['WinMan'].keyconfigs.user.keymaps['3D View'].keymap_items['view3d.copybuffer'].active

def set_view3d_copybuffer_keymap_item_active(active):
    log.debug('active <- %r' % active)
    bpy.data.window_managers['WinMan'].keyconfigs.user.keymaps['3D View'].keymap_items['view3d.copybuffer'].active = active

def monkeyPatch_view3d_copybuffer_update(addon_preferences, context):
    log.debug('!')
    patchMethod = addon_preferences.monkeyPatch_view3d_copybuffer
    active_user = addon_preferences.monkeyPatch_view3d_copybuffer_active_user
    log.debug('patchMethod = %r' % patchMethod)
    log.debug('active_user = %r' % active_user)
    if patchMethod == 'NOTHING':
        if active_user != 'None': # True, False
            set_view3d_copybuffer_keymap_item_active(active_user == 'True')
            active_user = 'None'
    else: # AUTO, DISABLE
        if active_user == 'None':
            active_user = ('True' if get_view3d_copybuffer_keymap_item_active() else 'False')
        set_view3d_copybuffer_keymap_item_active(False)
    log.debug('active_user <- %r' % active_user)
    addon_preferences.monkeyPatch_view3d_copybuffer_active_user = active_user


handlers = (bpy.app.handlers.load_post, bpy.app.handlers.scene_update_pre)

def remove_from_handlers():
    for handler in handlers:
        if monkeyPatch_view3d_copybuffer_handler in handler:
            handler.remove(monkeyPatch_view3d_copybuffer_handler)

def monkeyPatch_view3d_copybuffer_handler(_):
    log.debug('!')
    addon_preferences = bpy.context.user_preferences.addons[__package__].preferences
    monkeyPatch_view3d_copybuffer_update(addon_preferences, bpy.context)
    # remove from handlers after first call
    remove_from_handlers()

def register():
    # cannot set key mapping during register, so we do it as soon as possible using handlers
    for handler in handlers:
        handler.append(monkeyPatch_view3d_copybuffer_handler)

def unregister():
    # in the seemingly unlikely event monkeyPatch_view3d_copybuffer_handler isn't called and doesn't remove itself, remove it here
    remove_from_handlers()
    # restore view3d.copybuffer key mapping if needed
    addon_preferences = bpy.context.user_preferences.addons[__package__].preferences
    if addon_preferences.monkeyPatch_view3d_copybuffer_active_user != 'None':
        set_view3d_copybuffer_keymap_item_active(addon_preferences.monkeyPatch_view3d_copybuffer_active_user == 'True')
