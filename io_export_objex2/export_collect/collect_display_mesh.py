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

from ..util import CollectAbort
from ..logging_util import getLogger

from . import collect_display_material


def copy_to_rgba(color):
    if len(color) == 3:
        return (color[0], color[1], color[2], 1.0)
    return tuple(color)


class CollectedDisplayVertex:
    def __init__(self, coords, uv_coords, normal, color, groups):
        self.coords = coords
        self.uv_coords = uv_coords
        self.normal = normal
        self.color = color
        self.groups = groups


class CollectedDisplayFace:
    def __init__(self, vertices, material):
        self.vertices = vertices
        self.material = material


class CollectedDisplayMesh:
    def __init__(self, vertices, faces):
        self.vertices = vertices
        self.faces = faces


class DisplayMeshCollector:
    def __init__(self):
        # material: cd_material_explored (for objex materials)
        self.collected_materials = dict()
        # face_image: cd_material_phony (for face image fallback)
        self.face_image_materials = dict()

    def collect_display_mesh(
        self, mesh, collect_materials=True, collect_uvs=True, collect_vertex_colors=True
    ):
        log = getLogger("DisplayMeshCollector")
        collected_vertices = []
        collected_faces = []
        for face in mesh.polygons:
            material = None
            cd_material = None

            if collect_materials and mesh.materials:
                material = mesh.materials[face.material_index]
                if (
                    material.objex_bonus.is_objex_material
                    and material.objex_bonus.use_display
                ):
                    cd_material = self.collected_materials.get(material)
                    if cd_material is None:
                        if not material.use_nodes:
                            raise CollectAbort(
                                (
                                    "Material {0!r} {0.name} is_objex_material and use_display but not use_nodes"
                                    ' (was "Use Nodes" unchecked after adding objex nodes to it?)'
                                ).format(material)
                            )

                        material_explorer = collect_display_material.ObjexDisplayMaterialNodeTreeExplorer(
                            material
                        )
                        try:
                            cd_material = material_explorer.build()
                        except:
                            log.error(
                                "Failed to explore nodes of material {.name}", material
                            )
                            raise
                        self.collected_materials[material] = cd_material

                    if collect_uvs and cd_material.uvLayer is not None:
                        uv_layer = mesh.uv_layers[cd_material.uvLayer]
                    else:
                        uv_layer = None

                    if (
                        collect_vertex_colors
                        and cd_material.vertexColorLayer is not None
                    ):
                        vertex_color_layer = mesh.vertex_colors[
                            cd_material.vertexColorLayer
                        ]
                    else:
                        vertex_color_layer = None

            if cd_material is None:
                if collect_materials and hasattr(mesh, "uv_textures"):  # < 2.80
                    face_image = mesh.uv_textures.active.data[face.index].image
                    cd_material = self.face_image_materials.get(face_image)
                    if cd_material is None:
                        cd_material = (
                            collect_display_material.CollectedDisplayMaterial()
                        )
                        # FIXME set more stuff (eg combiner cycles)
                        cd_material.texel0 = collect_display_material.CollectedTexel()
                        cd_material.texel0.image = face_image
                        self.face_image_materials[face_image] = cd_material

                if collect_uvs:
                    uv_layer = mesh.uv_layers.active
                else:
                    uv_layer = None

                if collect_vertex_colors:
                    vertex_color_layer = mesh.vertex_colors.active
                else:
                    vertex_color_layer = None

            cd_face_vertices = []
            for loop_idx in face.loop_indices:
                loop = mesh.loops[loop_idx]
                vertex = mesh.vertices[loop.vertex_index]

                if uv_layer is not None:
                    uv = uv_layer.data[loop_idx].uv
                else:
                    uv = None

                if vertex_color_layer is not None:
                    color = vertex_color_layer.data[loop_idx].color
                else:
                    color = None

                groups = [(g.group, g.weight) for g in vertex.groups]

                cd_vertex = CollectedDisplayVertex(
                    vertex.co.copy().freeze(),
                    None if uv is None else uv.copy().freeze(),
                    loop.normal.copy().freeze(),
                    None if color is None else copy_to_rgba(color),
                    groups,
                )

                collected_vertices.append(cd_vertex)
                cd_face_vertices.append(cd_vertex)

            cd_face = CollectedDisplayFace(cd_face_vertices, cd_material)
            collected_faces.append(cd_face)

        return CollectedDisplayMesh(collected_vertices, collected_faces)
