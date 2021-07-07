from . import blender_version_compatibility

import bpy
import mathutils

from math import pi

from . import logging_util

# find/show unassigned/multiassigned vertices

class OBJEX_OT_mesh_find_vertices():

    bl_options = {'REGISTER','UNDO'}

    select_found = bpy.props.BoolProperty(
            name='Select',
            description='Select vertices found',
            default=True
        )

    @classmethod
    def poll(self, context):
        object = context.object if hasattr(context, 'object') else None
        return object and object.find_armature() and object.type == 'MESH'

    def execute(self, context):
        select_found = self.select_found
        object = context.object
        armature = object.find_armature()
        mesh = object.data
        # leave edit mode
        was_editmode = mesh.is_editmode
        if was_editmode:
            bpy.ops.object.mode_set(mode='OBJECT')
        found = False
        self.ignored_vertex_groups = set()
        def test(v):
            n_bone_groups = 0
            for g in v.groups:
                if object.vertex_groups[g.group].name in armature.data.bones:
                    n_bone_groups += 1
                else:
                    self.ignored_vertex_groups.add(g.group)
            return self.test(n_bone_groups)
        # search for any matching vertex
        for v in mesh.vertices:
            if test(v):
                found = True
                break
        # only select vertices if some were found
        if found and select_found:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='VERT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            for v in mesh.vertices:
                if test(v):
                    v.select = True
        if was_editmode or (found and select_found):
            bpy.ops.object.mode_set(mode='EDIT')
        if found:
            level = 'WARNING'
            message = self.__class__.message_found
        else:
            level = 'INFO'
            message = self.__class__.message_not_found
        if self.ignored_vertex_groups:
            message = ('%s (ignored group %s: not a bone)'
                        if len(self.ignored_vertex_groups) == 1
                        else '%s (ignored groups %s: not bones)'
            ) % (message, ', '.join(object.vertex_groups[group].name for group in self.ignored_vertex_groups))
        self.report({level}, message)
        return {'FINISHED'}

class OBJEX_OT_mesh_find_multiassigned_vertices(bpy.types.Operator, OBJEX_OT_mesh_find_vertices):

    bl_idname = 'objex.mesh_find_multiassigned_vertices'
    bl_label = 'Find vertices assigned to several bones'

    message_found = 'Found multiassigned vertices!'
    message_not_found = 'Did not find any multiassigned vertex.'
    def test(self, n_bone_groups):
        return n_bone_groups > 1

class OBJEX_OT_mesh_find_unassigned_vertices(bpy.types.Operator, OBJEX_OT_mesh_find_vertices):

    bl_idname = 'objex.mesh_find_unassigned_vertices'
    bl_label = 'Find vertices not assigned to any bones'

    message_found = 'Found unassigned vertices!'
    message_not_found = 'Did not find any unassigned vertex.'
    def test(self, n_bone_groups):
        return n_bone_groups == 0

class OBJEX_OT_mesh_list_vertex_groups(bpy.types.Operator):

    bl_idname = 'objex.mesh_list_vertex_groups'
    bl_label = 'List vertex groups and weights of the selected vertex'

    @classmethod
    def poll(self, context):
        object = context.object if hasattr(context, 'object') else None
        return object and object.type == 'MESH'

    def execute(self, context):
        mesh = context.object.data
        was_editmode = mesh.is_editmode
        if was_editmode:
            bpy.ops.object.mode_set(mode='OBJECT')
        vert = None
        for v in mesh.vertices:
            if v.select:
                if vert:
                    self.report({'WARNING'}, 'More than 1 vertex selected')
                    if was_editmode:
                        bpy.ops.object.mode_set(mode='EDIT')
                    return {'CANCELLED'}
                vert = v
        if not vert:
            self.report({'WARNING'}, 'No vertex selected')
            if was_editmode:
                bpy.ops.object.mode_set(mode='EDIT')
            return {'CANCELLED'}
        vertGroupNames = context.object.vertex_groups.keys()
        self.report({'INFO'}, 'Groups: %s' % ', '.join('%s (%.2g)' % (vertGroupNames[g.group], g.weight) for g in vert.groups))
        if was_editmode:
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}


# folding/unfolding

def var_armature_rest(obj):
    """Compute variance of x,y,z coordinates in world space of bones center in rest position"""
    arma = obj.data.copy()
    arma.transform(obj.matrix_world)
    sum = mathutils.Vector()
    for b in arma.bones:
        sum += ((b.head_local + b.tail_local) / 2)
    mean = sum / len(arma.bones)
    var = mathutils.Vector()
    for b in arma.bones:
        delta = ((b.head_local + b.tail_local) / 2) - mean
        var += mathutils.Vector(d*d for d in delta)
    var /= len(arma.bones)
    bpy.data.armatures.remove(arma)
    return var

def var_armature_pose(obj):
    """Compute variance of x,y,z coordinates in world space of bones center in pose position"""
    sum = mathutils.Vector()
    for b in obj.pose.bones:
        sum += blender_version_compatibility.matmul(obj.matrix_world, b.center)
    mean = sum / len(obj.pose.bones)
    var = mathutils.Vector()
    for b in obj.pose.bones:
        delta = blender_version_compatibility.matmul(obj.matrix_world, b.center) - mean
        var += mathutils.Vector(d*d for d in delta)
    var /= len(obj.pose.bones)
    return var

def is_folded_guess(armature):
    """
    Returns True if all bones in rest position have head_local.x >= 0,
    which seems to be a common factor of folded skeletons
    """
    xMin = min(bone.head_local.x for bone in armature.data.bones)
    logging_util.getLogger('rigging_helpers').debug('xMin = {}', xMin)
    return xMin > -1e-5 # allow a small error

def checkSaveCompatibitility(armature, saved_pose):
    """
    Returns true if the pose defined by saved_pose can be restored to armature
    """
    # 421todo store and check hierarchy too?
    # check if armature and saved_pose have bones with the same names
    return (
        set(bone.name for bone in armature.pose.bones)
            == set(bone.bone_name for bone in saved_pose.bones)
    )

def restoreSavedPose(armature, saved_bones, invert=False):
    """
    Set the armature's pose from the provided saved bones
    names of armature pose bones should match the names of saved bones (this doesn't check)
    invert=True inverts the pose before setting it on the armature
    """
    # 421fixme test setting .location when not 0,0,0 , test if order of setting it matters
    for saved_bone in saved_bones:
        # assume eg checkSaveCompatibitility() has been called somewhere
        bone = armature.pose.bones[saved_bone.bone_name]
        location = mathutils.Vector(saved_bone.location)
        rotation_quaternion = mathutils.Quaternion(saved_bone.rotation_quaternion)
        if invert:
            location *= (-1)
            rotation_quaternion.invert()
            location.rotate(rotation_quaternion)
        bone.location = location
        rotation_mode_prev = bone.rotation_mode
        # convert from quaternion in rotation_quaternion to any mode
        bone.rotation_mode = 'QUATERNION'
        bone.rotation_quaternion = rotation_quaternion
        bone.rotation_mode = rotation_mode_prev

def fold_unfold(scene, armature, do_folding, saved_pose, log=None):
    if not log:
        log = logging_util.getLogger('rigging_helpers')

    meshs = (obj for obj in scene.objects
        if obj.type == 'MESH' and obj.find_armature() == armature)

    # set pose
    log.trace('restoreSavedPose')
    if do_folding:
        # armature/mesh are UNFOLDED, set folded pose
        # saved_pose.type can only be 'UNFOLDEDpose_foldedRest' or 'foldedPose_UNFOLDEDrest'
        restoreSavedPose(armature, saved_pose.bones, invert=saved_pose.type != 'foldedPose_UNFOLDEDrest')
    else:
        # armature/mesh are folded, set UNFOLDED pose
        restoreSavedPose(armature, saved_pose.bones, invert=saved_pose.type != 'UNFOLDEDpose_foldedRest')

    # if not called, modifiers are applied with the wrong pose by to_mesh
    if hasattr(scene, 'update'): # < 2.80
        scene.update()
    else: # 2.80+
        pass

    # (UN)fold rigged meshs
    for mesh in meshs:
        # find the armature deform modifier
        armature_deform_modifier_candidates = [
            modifier for modifier in mesh.modifiers
            if modifier.type == 'ARMATURE' and modifier.object == armature
        ]
        if len(armature_deform_modifier_candidates) == 0:
            log.warn('No armature deform modifier on mesh {} using armature {}, skipping mesh',
                        mesh.name, armature.name)
            continue
        if len(armature_deform_modifier_candidates) > 1:
            log.warn('More than one armature deform modifier on mesh {} using armature {}: {}',
                        mesh.name, armature.name, armature_deform_modifier_candidates)
        armature_deform_modifier = armature_deform_modifier_candidates[0]
        log.debug('armature_deform_modifier.name = {}', armature_deform_modifier.name)
        # make only armature_deform_modifier active
        armature_deform_modifier_show_viewport_user = armature_deform_modifier.show_viewport
        temporarily_disabled_modifiers = [
            modifier for modifier in mesh.modifiers
                if modifier != armature_deform_modifier
                    and modifier.show_viewport]
        for modifier in temporarily_disabled_modifiers:
            modifier.show_viewport = False
        armature_deform_modifier.show_viewport = True
        log.trace('{} to_mesh...', mesh.name)
        # replace mesh data by mesh with modifier-applied
        if not hasattr(mesh, 'evaluated_get'): # < 2.80
            mesh.data = mesh.to_mesh(scene, True, calc_tessface=False, settings='PREVIEW')
        else: # 2.80+
            # 2.80+ to_mesh: The result is temporary and can not be used by objects from the main database
            # using new_from_object instead (with evaluated_get's result /!\, not mesh directly) works
            log.trace('evaluated_depsgraph_get')
            depsgraph = bpy.context.evaluated_depsgraph_get()
            log.trace('evaluated_get')
            mesh_evaluated = mesh.evaluated_get(depsgraph)
            log.trace('new_from_object')
            mesh.data = bpy.data.meshes.new_from_object(mesh_evaluated)
        # restore modifier visibility
        log.trace('to_mesh done')
        for modifier in temporarily_disabled_modifiers:
            modifier.show_viewport = True
        armature_deform_modifier.show_viewport = armature_deform_modifier_show_viewport_user

    # (UN)fold armature, apply pose as rest pose
    # store current context
    armature_mode_user = armature.mode
    selected_objects_user = bpy.context.selected_objects[:]
    active_object_user = blender_version_compatibility.get_active_object(bpy.context)
    # switch context to only armature active/selected and in pose mode
    while bpy.context.selected_objects:
        blender_version_compatibility.set_object_select(bpy.context.selected_objects[0], False)
    blender_version_compatibility.set_object_select(armature, True)
    # use bpy.context.scene instead of scene
    blender_version_compatibility.set_active_object(bpy.context, armature)
    bpy.ops.object.mode_set(mode='POSE')
    # call "Apply Pose as Rest Pose" operator
    bpy.ops.pose.armature_apply()
    # restore context
    bpy.ops.object.mode_set(mode=armature_mode_user)
    blender_version_compatibility.set_object_select(armature, False)
    # everything is deselected, now select what was previously selected
    for obj in selected_objects_user:
        blender_version_compatibility.set_object_select(obj, True)
    blender_version_compatibility.set_active_object(bpy.context, active_object_user)

class AutofoldOperator():

    @classmethod
    def poll(self, context):
        return (
            hasattr(context, 'object')
            and context.object
            and (
                context.object.type == 'ARMATURE'
                or (
                    context.object.type == 'MESH'
                    and context.object.find_armature()
                )
            )
        )

    def get_armature(self, context):
        if context.object.type == 'MESH':
            return context.object.find_armature()
        else: # ARMATURE
            return context.object

    def startLogging(self):
        self.log = logging_util.getLogger(self.bl_idname)
        logging_util.setLogOperator(self, user_friendly_formatter=True)
        return self.log

    def endLogging(self):
        logging_util.setLogOperator(None)

class OBJEX_OT_autofold_save_pose(bpy.types.Operator, AutofoldOperator):

    bl_idname = 'objex.autofold_save_pose'
    bl_label = 'Save Pose position'
    bl_options = {'REGISTER', 'UNDO'}

    pose_name = bpy.props.StringProperty(
            name='Pose name',
            description='Name identifier for the pose position to save',
        )
    # pose_name_current is used to ignore the "already used" pose name during redo in the redo panel
    pose_name_current = bpy.props.StringProperty()
    type = bpy.props.EnumProperty(
            items=[
                ('UNFOLDEDpose_foldedRest','Unfolding pose','The pose position UNFOLDS the armature from its folded rest position',1),
                ('foldedPose_UNFOLDEDrest','Folding pose','The pose position folds the armature from its UNFOLDED rest position',2),
            ],
            name='Type',
            description='Define if this pose position is folding or UNFOLDING the armature',
            default='UNFOLDEDpose_foldedRest'
        )

    def invoke(self, context, event):
        log = self.startLogging()
        try:
            armature = self.get_armature(context)

            self.pose_name_current = ''

            identity_quaternion = mathutils.Quaternion()
            identity_quaternion.identity()
            is_identity_pose = True
            for bone in armature.pose.bones:
                if bone.rotation_mode == 'QUATERNION':
                    if bone.rotation_quaternion != identity_quaternion:
                        is_identity_pose = False
                elif bone.rotation_mode == 'AXIS_ANGLE':
                    if (bone.rotation_axis_angle[0] % (2*pi)) != 0:
                        is_identity_pose = False
                elif bone.rotation_mode in ('XYZ','XZY','YXZ','YZX','ZXY','ZYX'): # Euler
                    if any((angle % (2*pi)) != 0 for angle in bone.rotation_euler):
                        is_identity_pose = False
                else:
                    log.error('Unknown rotation_mode {}', bone.rotation_mode)
                    is_identity_pose = False
            if is_identity_pose:
                log.warn('The pose position matches rest position, it is useless')
                return {'FINISHED'} # still allow the user to pick a name (and save)

            var_pose = var_armature_pose(armature)
            var_rest = var_armature_rest(armature)
            # UNFOLDED positions are usually more spread out
            if var_pose.length > var_rest.length:
                self.type = 'UNFOLDEDpose_foldedRest'
            else:
                self.type = 'foldedPose_UNFOLDEDrest'
            log.debug('var_pose = {} .length = {}', var_pose, var_pose.length)
            log.debug('var_rest = {} .length = {}', var_rest, var_rest.length)
            log.debug('guessed type = {}', self.type)
            try:
                # 421todo c'est très gadget (useless feature), but could be improved by
                # taking into account modifier keys and other hotkey features
                keymap_items = (bpy.context.window_manager.keyconfigs.user
                                .keymaps['3D View Generic'].keymap_items)
                if 'view3d.toolshelf' in keymap_items: # < 2.80
                    redo_in_toolbar = True
                    toolbar_hotkey = keymap_items['view3d.toolshelf'].type
                else: # 2.80+
                    redo_in_toolbar = False
            except:
                log.exception('Failed to get toolbar hotkey')
                redo_in_toolbar = bpy.app.version < (2, 80, 0)
                toolbar_hotkey = 'T'
            if redo_in_toolbar: # < 2.80
                log.info('Please set a pose name in the toolbar (left of 3D view, hotkey {})', toolbar_hotkey)
            else: # 2.80+
                return context.window_manager.invoke_props_dialog(self)
            return {'FINISHED'}
        finally:
            self.endLogging()

    def execute(self, context):
        log = self.startLogging()
        try:
            scene = context.scene
            armature = self.get_armature(context)

            if not self.pose_name:
                log.warn('Pose name cannot be empty')
                return {'CANCELLED'}
            if self.pose_name in scene.objex_bonus.saved_poses:
                log.warn('Pose name already used')
                return {'CANCELLED'}

            saved_pose = scene.objex_bonus.saved_poses.add()

            saved_pose.name = self.pose_name
            saved_pose.type = self.type

            self.pose_name_current = saved_pose.name

            identity_quaternion = mathutils.Quaternion()
            identity_quaternion.identity()
            is_identity_pose = True
            for bone in armature.pose.bones:
                rotation_mode_prev = bone.rotation_mode
                # convert from any mode to quaternion in rotation_quaternion
                bone.rotation_mode = 'QUATERNION'
                saved_pose_bone = saved_pose.bones.add()
                saved_pose_bone.bone_name = bone.name
                saved_pose_bone.location = tuple(bone.location)
                saved_pose_bone.rotation_quaternion = tuple(bone.rotation_quaternion)
                if bone.rotation_quaternion != identity_quaternion:
                    is_identity_pose = False
                bone.rotation_mode = rotation_mode_prev

            if is_identity_pose:
                log.warn('The saved pose position matches rest position, it is useless')

            return {'FINISHED'}
        finally:
            self.endLogging()

    def draw(self, context):
        scene = context.scene
        armature = self.get_armature(context)

        self.layout.prop(
            self, 'pose_name',
            icon='ERROR'
                if (self.pose_name in scene.objex_bonus.saved_poses
                        and self.pose_name != self.pose_name_current # ignore currently saved pose during redo
                    ) or not self.pose_name
                else 'NONE')
        self.layout.prop(self, 'type')

class OBJEX_OT_autofold_delete_pose(bpy.types.Operator, AutofoldOperator):

    bl_idname = 'objex.autofold_delete_pose'
    bl_label = 'Delete a saved Pose position'
    bl_options = {'REGISTER', 'UNDO'}

    pose_name = bpy.props.StringProperty(
            name='Pose',
            description='The saved pose position to delete',
        )

    def invoke(self, context, event):
        scene = context.scene
        armature = self.get_armature(context)
        try:
            self.pose_name = scene.objex_bonus.saved_poses[armature.data.objex_bonus.fold_unfold_saved_pose_index].name
        except IndexError: # bad fold_unfold_saved_pose_index
            pass
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        scene = context.scene
        pose_index = scene.objex_bonus.saved_poses.find(self.pose_name)
        if pose_index < 0: # not found
            return {'CANCELLED'}
        scene.objex_bonus.saved_poses.remove(pose_index)
        return {'FINISHED'}

    def draw(self, context):
        scene = context.scene
        self.layout.prop_search(self, 'pose_name', scene.objex_bonus, 'saved_poses')

class OBJEX_OT_autofold_restore_pose(bpy.types.Operator, AutofoldOperator):

    bl_idname = 'objex.autofold_restore_pose'
    bl_label = 'Restore Pose position as previously saved'
    bl_options = {'REGISTER', 'UNDO'}

    pose_name = bpy.props.StringProperty(
            name='Pose',
            description='The saved pose position to restore',
        )

    def invoke(self, context, event):
        scene = context.scene
        armature = self.get_armature(context)

        try:
            self.pose_name = scene.objex_bonus.saved_poses[armature.data.objex_bonus.fold_unfold_saved_pose_index].name
        except IndexError: # bad fold_unfold_saved_pose_index
            pass

        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        log = self.startLogging()
        try:
            scene = context.scene
            armature = self.get_armature(context)

            saved_pose = scene.objex_bonus.saved_poses.get(self.pose_name)
            if not saved_pose:
                log.warn('Must choose a pose')
                return {'CANCELLED'}

            if not checkSaveCompatibitility(armature, saved_pose):
                log.warn('Saved pose {} cannot be used with armature {}', saved_pose.name, armature.name)
                return {'CANCELLED'}

            restoreSavedPose(armature, saved_pose.bones)

            return {'FINISHED'}
        finally:
            self.endLogging()

    def draw(self, context):
        scene = context.scene

        self.layout.prop_search(self, 'pose_name', scene.objex_bonus, 'saved_poses')

class OBJEX_OT_autofold_fold_unfold(bpy.types.Operator, AutofoldOperator):

    bl_idname = 'objex.autofold_fold_unfold'
    bl_label = 'Fold/Unfold an armature and the meshs rigged to it'
    bl_options = {'REGISTER', 'UNDO'}

    action = bpy.props.EnumProperty(
            items=[
                ('FOLD','Fold','',1),
                ('UNFOLD','Unfold','',2),
                ('SWITCH','Switch','Fold if unfolded, unfold if folded',3),
            ],
            name='Action',
            description='Fold or unfold',
            default='SWITCH'
        )
    pose_name = bpy.props.StringProperty(
            name='Pose',
            description='The saved pose position to use',
        )

    def execute(self, context):
        log = self.startLogging()
        try:
            scene = context.scene
            armature = self.get_armature(context)

            if self.pose_name:
                # self.pose_name should be valid thanks to prop_search
                saved_pose = scene.objex_bonus.saved_poses[self.pose_name]
            else:
                try:
                    saved_pose = scene.objex_bonus.saved_poses[armature.data.objex_bonus.fold_unfold_saved_pose_index]
                except IndexError:
                    log.warn('Select a pose to use among the saved poses\n'
                        '(if there are no saved poses available you must save a pose first)')
                    return {'CANCELLED'}

            if not checkSaveCompatibitility(armature, saved_pose):
                log.warn('Saved pose {} cannot be used with armature {}', saved_pose.name, armature.name)
                return {'CANCELLED'}

            if self.action == 'SWITCH':
                if is_folded_guess(armature):
                    # assume currently folded
                    do_folding = False # unfold
                else:
                    # assume currently unfolded
                    do_folding = True # fold
            else: # FOLD, UNFOLD
                do_folding = (self.action == 'FOLD')
            log.info('Folding' if do_folding else 'Unfolding')

            fold_unfold(scene, armature, do_folding, saved_pose=saved_pose, log=log)
            # 421todo also fold/unfold actions?

            if self.action == 'SWITCH' and do_folding != is_folded_guess(armature):
                from_folded_state, to_folded_state = ('UNFOLDED', 'folded') if do_folding else ('folded', 'UNFOLDED')
                log.warn('It was guessed that the armature was initially {from_folded_state} and had to be {to_folded_state},\n'
                    'but now that the armature should be {to_folded_state} it is still guessed as {from_folded_state}.\n'
                    'Results of this switch fold/unfold operation may be wrong,\n'
                    'you may have to avoid using the Switch feature.'
                        .format(from_folded_state=from_folded_state, to_folded_state=to_folded_state))

            return {'FINISHED'}
        finally:
            self.endLogging()

    def draw(self, context):
        scene = context.scene
        armature = self.get_armature(context)

        self.layout.prop(self, 'action')

        default_to_saved_pose = None
        if not self.pose_name:
            try:
                default_to_saved_pose = scene.objex_bonus.saved_poses[armature.data.objex_bonus.fold_unfold_saved_pose_index]
            except IndexError: # bad fold_unfold_saved_pose_index
                pass

        box = self.layout.box() if default_to_saved_pose else self.layout
        box.prop_search(self, 'pose_name', scene.objex_bonus, 'saved_poses')
        if default_to_saved_pose:
            box.label(text='Using {}'.format(default_to_saved_pose.name))


classes = (
    OBJEX_OT_mesh_find_multiassigned_vertices,
    OBJEX_OT_mesh_find_unassigned_vertices,
    OBJEX_OT_mesh_list_vertex_groups,
    OBJEX_OT_autofold_save_pose,
    OBJEX_OT_autofold_delete_pose,
    OBJEX_OT_autofold_restore_pose,
    OBJEX_OT_autofold_fold_unfold,
)

def register():
    for clazz in classes:
        blender_version_compatibility.make_annotations(clazz)
        bpy.utils.register_class(clazz)

def unregister():
    for clazz in reversed(classes):
        bpy.utils.unregister_class(clazz)
