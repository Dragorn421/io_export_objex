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


class CollectedFace:
    def __init__(self, vertices, material):
        self.vertices = vertices
        self.material = material


class CollectedMesh:
    def __init__(self, vertices, faces):
        self.vertices = vertices
        self.faces = faces


def collect_mesh(
    mesh,
    collected_vertex_factory,
    material_handler=None,
    face_image_handler=None,
    collect_uvs=True,
    collect_normals=True,
    collect_vertex_colors=True,
    collect_groups=True,
):
    collected_vertices = []
    collected_faces = []
    for face in mesh.polygons:
        material = None
        collected_material = None

        if material_handler is not None and mesh.materials:
            material = mesh.materials[face.material_index]
            material_handler_result = material_handler(material)
            if material_handler_result is not None:
                collected_material, uvLayer, vertexColorLayer = material_handler_result

                if collect_uvs and uvLayer is not None:
                    uv_layer = mesh.uv_layers[uvLayer]
                else:
                    uv_layer = None

                if collect_vertex_colors and vertexColorLayer is not None:
                    vertex_color_layer = mesh.vertex_colors[vertexColorLayer]
                else:
                    vertex_color_layer = None

        if collected_material is None:
            if face_image_handler is not None and hasattr(
                mesh, "uv_textures"
            ):  # < 2.80
                face_image = mesh.uv_textures.active.data[face.index].image
                collected_material = face_image_handler(face_image)

            if collect_uvs:
                uv_layer = mesh.uv_layers.active
            else:
                uv_layer = None

            if collect_vertex_colors:
                vertex_color_layer = mesh.vertex_colors.active
            else:
                vertex_color_layer = None

        collected_face_vertices = []
        for loop_idx in face.loop_indices:
            loop = mesh.loops[loop_idx]
            vertex = mesh.vertices[loop.vertex_index]

            if uv_layer is not None:
                uv = uv_layer.data[loop_idx].uv
            else:
                uv = None

            if vertex_color_layer is not None:
                color = vertex_color_layer.data[loop_idx].color
                if len(color) == 3:
                    color = (color[0], color[1], color[2], 1.0)
                else:
                    color = tuple(color)
            else:
                color = None

            if collect_groups:
                groups = [(g.group, g.weight) for g in vertex.groups]
            else:
                groups = None

            collected_vertex = collected_vertex_factory(
                vertex.co.copy().freeze(),
                None if uv is None else uv.copy().freeze(),
                loop.normal.copy().freeze() if collect_normals else None,
                color,
                groups,
            )

            collected_vertices.append(collected_vertex)
            collected_face_vertices.append(collected_vertex)

        collected_face = CollectedFace(collected_face_vertices, collected_material)
        collected_faces.append(collected_face)

    return CollectedMesh(collected_vertices, collected_faces)
