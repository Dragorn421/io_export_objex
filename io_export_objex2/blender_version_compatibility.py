import bpy

import inspect
import operator

from .logging_util import getLogger

# thanks to https://theduckcow.com/2019/update-addons-both-blender-28-and-27-support/

def get_preferences(context):
    if hasattr(context, 'user_preferences'):
        return context.user_preferences
    else:
        return context.preferences

def make_annotations(clazz):
    """Converts class fields to annotations if running with Blender 2.8"""
    if bpy.app.version < (2, 80):
        return clazz
    elif bpy.app.version < (2, 93):
        isPropertyDeferred = lambda v: (isinstance(v, tuple) and len(v) == 2 and inspect.isbuiltin(v[0]) and isinstance(v[1], dict))
    else:
        isPropertyDeferred = lambda v: isinstance(v, bpy.props._PropertyDeferred)
    for cls in clazz.__mro__:
        bl_props = {k: v for k, v in cls.__dict__.items() if isPropertyDeferred(v)}
        if bl_props:
            if '__annotations__' not in cls.__dict__:
                setattr(cls, '__annotations__', {})
            annotations = cls.__dict__['__annotations__']
            for k, v in bl_props.items():
                annotations[k] = v
                delattr(cls, k)
    return clazz

def matmul(a, b):
    if bpy.app.version < (2, 80):
        return a * b
    else:
        return operator.matmul(a, b) # a @ b

def get_active_object(context):
    if not hasattr(context, 'view_layer'): # < 2.80
        return context.scene.objects.active
    else: # 2.80+
        return context.view_layer.objects.active

def set_active_object(context, object):
    if not hasattr(context, 'view_layer'): # < 2.80
        context.scene.objects.active = object
    else: # 2.80+
        context.view_layer.objects.active = object

def get_object_select(object):
    if hasattr(object, 'select'): # < 2.80
        return object.select
    else: # 2.80+
        return object.select_get()

def set_object_select(object, select):
    if hasattr(object, 'select'): # < 2.80
        object.select = select
    else: # 2.80+
        object.select_set(select)

# when PointerProperty didn't support ID
no_ID_PointerProperty = bpy.app.version < (2, 79, 0)

def adapt_ID_PointerProperty(clazz):
    log = getLogger('blender_version_compatibility')
    if not no_ID_PointerProperty:
        return
    for attr in dir(clazz):
        val = getattr(clazz, attr)
        if not (isinstance(val, tuple) and len(val) >= 1):
            continue
        if val[0] is not bpy.props.PointerProperty:
            continue
        params = val[1]
        type = params.get('type')
        if not (type and bpy.types.ID in type.mro()):
            continue
        del params['type']
        poll = params.get('poll')
        if poll:
            if type not in (bpy.types.Object,):
                raise TypeError('unsupported ID type {!r}'.format(type))
            log.debug('{!r} {!r} wrap poll which expects ID', clazz, attr)
            del params['poll']
            def poll_wrapper_with_update_factory():
                _attr = attr
                _poll = poll
                _type = type
                def poll_wrapper_with_update(self, context):
                    name = getattr(self, _attr)
                    if name:
                        if _type is bpy.types.Object:
                            id_data = bpy.data.objects.get(name)
                        if not _poll(self, id_data):
                            setattr(self, _attr, '')
                return poll_wrapper_with_update
            params['update'] = poll_wrapper_with_update_factory()
        log.debug('PointerProperty -> StringProperty {!r} {!r}', clazz, attr)
        setattr(clazz, attr, bpy.props.StringProperty(**params))

has_per_material_backface_culling = bpy.app.version >= (2, 80, 0)
