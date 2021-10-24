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

from typing import Dict, Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .. import properties

import bpy

from .. import data_updater
from ..util import CollectAbort
from ..logging_util import getLogger

from . import collect_mesh
from . import collect_display_material


class CollectedDisplayVertex:
    def __init__(self, coords, uv_coords, normal, color, groups):
        self.coords = coords
        self.uv_coords = uv_coords
        self.normal = normal
        self.color = color
        self.groups = groups


class DisplayMeshCollector:
    def __init__(self):
        self.log = getLogger("DisplayMeshCollector")
        # source: cd_material_explored
        # where source can be a material or an image (for handling face images in Blender 2.79)
        self.collected_materials = (
            dict()
        )  # type: Dict[Any, collect_display_material.CollectedDisplayMaterial]

    def material_handler(self, material):
        log = self.log

        objex_data = material.objex_bonus  # type: properties.ObjexMaterialProperties

        # FIXME all these warnings are going to spam since material_handler is called for every face!

        # assume non-objex materials using nodes are a rarity before 2.8x
        if (
            bpy.app.version < (2, 80, 0)
            and material.use_nodes
            and not objex_data.is_objex_material
        ):
            log.warning(
                "Material {!r} use_nodes but not is_objex_material\n"
                '(did you copy-paste nodes from another material instead of clicking the "Init..." button?),\n'
                "nodes will be ignored and the face image will be used\n"
                "(for now, to use the current nodes you can make a temporary duplicate of the material,\n"
                'click the "Init..." button on the original material, delete all the generated nodes\n'
                "and paste the actual nodes from the duplicate)",
                material,
            )

        if objex_data.is_objex_material and objex_data.use_collision:
            log.error(
                "Material {!r} is an objex collision material, but is used in a display mesh",
                material,
            )
            return None

        if objex_data.is_objex_material and objex_data.use_display:
            # raises if the material version doesn't match the current addon material version
            data_updater.assert_material_at_current_version(material, CollectAbort)

            cd_material = self.collected_materials.get(material)
            if cd_material is None:
                if not material.use_nodes:
                    raise CollectAbort(
                        (
                            "Material {0!r} {0.name} is_objex_material and use_display but not use_nodes"
                            ' (was "Use Nodes" unchecked after adding objex nodes to it?)'
                        ).format(material)
                    )

                material_explorer = (
                    collect_display_material.ObjexDisplayMaterialNodeTreeExplorer(
                        material
                    )
                )
                try:
                    cd_material = material_explorer.build()
                except:
                    log.error("Failed to explore nodes of material {.name}", material)
                    raise
                self.collected_materials[material] = cd_material
            return cd_material, cd_material.uvLayer, cd_material.vertexColorLayer

        if objex_data.is_objex_material:
            log.error(
                "Material {!r} is an objex material, but neither display nor collision",
                material,
            )
            return None

        # try to find an image from the non-objex material
        image = None
        if hasattr(material, "texture_slots"):  # < 2.80
            # backwards so topmost are highest priority (421todo ... sure about that?)
            for mtex in reversed(material.texture_slots):
                if mtex and mtex.texture and mtex.texture.type == "IMAGE":
                    image = mtex.texture.image
                    if image and (
                        mtex.use_map_color_diffuse
                        and (mtex.use_map_warp is False)
                        and (mtex.texture_coords != "REFLECTION")
                    ):
                        break
                    else:
                        image = None
        else:  # 2.80+
            import bpy_extras

            # based on the Blender 2.82 obj exporter
            mat_wrap = bpy_extras.node_shader_utils.PrincipledBSDFWrapper(material)
            # image can be None
            image = mat_wrap.base_color_texture.image

        if image is not None:
            # FIXME return non-None uv and vertex color layers
            return self.face_image_handler(image), None, None
        else:
            return None

    def face_image_handler(self, face_image):
        cd_material = self.collected_materials.get(face_image)
        if cd_material is None:
            cd_material = collect_display_material.CollectedDisplayMaterial(
                name=face_image.name,
                # default to texel0 * shade * primColor for both cycles
                combinerFlags=[
                    "G_CCMUX_TEXEL0",
                    "G_CCMUX_0",
                    "G_CCMUX_SHADE",
                    "G_CCMUX_0",
                    "G_ACMUX_TEXEL0",
                    "G_ACMUX_0",
                    "G_ACMUX_SHADE",
                    "G_ACMUX_0",
                    "G_CCMUX_COMBINED",
                    "G_CCMUX_0",
                    "G_CCMUX_PRIMITIVE",
                    "G_CCMUX_0",
                    "G_ACMUX_COMBINED",
                    "G_ACMUX_0",
                    "G_ACMUX_PRIMITIVE",
                    "G_ACMUX_0",
                ],
                primColor=None,
                primLodFrac=None,
                envColor=None,
                shadeSource="NORMALS",
                vertexColorLayer=None,
                texel0=collect_display_material.CollectedTexel(
                    image=face_image,
                    uScale=0,
                    vScale=0,
                    uWrap=True,
                    vWrap=True,
                    uMirror=False,
                    vMirror=False,
                ),
                texel1=None,
                uvLayer=None,  # FIXME can't be None
                uScaleMain=1,
                vScaleMain=1,
                texgen=None,
                properties=None,  # FIXME can't be None
            )
            self.collected_materials[face_image] = cd_material
        return cd_material

    def collect_display_mesh(
        self,
        mesh,
        collect_materials=True,
        collect_uvs=True,
        collect_normals=True,
        collect_vertex_colors=True,
        collect_groups=True,
    ):
        return collect_mesh.collect_mesh(
            mesh,
            CollectedDisplayVertex,
            lambda mat: self.material_handler(mat) if collect_materials else None,
            lambda img: self.face_image_handler(img) if collect_materials else None,
            collect_uvs=collect_uvs,
            collect_normals=collect_normals,
            collect_vertex_colors=collect_vertex_colors,
            collect_groups=collect_groups,
        )
