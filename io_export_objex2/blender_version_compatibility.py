import bpy

import inspect
import operator

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
    for cls in clazz.__mro__:
        bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple) and len(v) == 2 and inspect.isbuiltin(v[0]) and isinstance(v[1], dict)}
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
