import bpy

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
        return object and object.type == 'MESH'

    def execute(self, context):
        select_found = self.select_found
        mesh = context.object.data
        # leave edit mode
        was_editmode = mesh.is_editmode
        if was_editmode:
            bpy.ops.object.mode_set(mode='OBJECT')
        found = False
        # search for any matching vertex
        for v in mesh.vertices:
            if self.test(v):
                found = True
                break
        # only select vertices if some were found
        if found and select_found:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='VERT')
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            for v in mesh.vertices:
                if self.test(v):
                    v.select = True
        if was_editmode or (found and select_found):
            bpy.ops.object.mode_set(mode='EDIT')
        if found:
            self.report({'WARNING'}, self.__class__.message_found)
        else:
            self.report({'INFO'}, self.__class__.message_not_found)
        return {'FINISHED'}

# 421fixme export_objex doesnt naively exports every group in v.groups,
# only the ones corresponding to an actual bone from the armature
# but here len(v.groups) is simply checked
# though maybe groups not matching a bone have a weight-related
# effect and should still be avoided for wysiwyg?

class OBJEX_OT_mesh_find_multiassigned_vertices(bpy.types.Operator, OBJEX_OT_mesh_find_vertices):

    bl_idname = 'objex.mesh_find_multiassigned_vertices'
    bl_label = 'Find vertices assigned to several bones'

    message_found = 'Found multiassigned vertices!'
    message_not_found = 'Did not find any multiassigned vertex.'
    def test(self, v):
        return len(v.groups) > 1

class OBJEX_OT_mesh_find_unassigned_vertices(bpy.types.Operator, OBJEX_OT_mesh_find_vertices):

    bl_idname = 'objex.mesh_find_unassigned_vertices'
    bl_label = 'Find vertices not assigned to any bones'

    message_found = 'Found unassigned vertices!'
    message_not_found = 'Did not find any unassigned vertex.'
    def test(self, v):
        return len(v.groups) == 0

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


classes = (
    OBJEX_OT_mesh_find_multiassigned_vertices,
    OBJEX_OT_mesh_find_unassigned_vertices,
    OBJEX_OT_mesh_list_vertex_groups,
)

def register():
    for clazz in classes:
        bpy.utils.register_class(clazz)

def unregister():
    for clazz in classes:
        bpy.utils.unregister_class(clazz)
