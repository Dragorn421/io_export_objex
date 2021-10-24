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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .. import properties

import collect_mesh
from .. import util
from ..logging_util import getLogger


class CollectedCollisionVertex:
    def __init__(self, coords):
        self.coords = coords


class CollectedCollisionMaterial:
    def __init__(
        self,
        name,  # type: str
        properties,  # type: properties.ObjexMaterialCollisionProperties
    ):
        self.original_name = name
        self.name = name
        self.name_q = util.quote(name)
        self.properties = properties


class CollisionMeshCollector:
    def __init__(self):
        self.log = getLogger("CollisionMeshCollector")
        # material: cc_material
        self.collected_materials = dict()

    def material_handler(self, material):
        objex_data = material.objex_bonus  # type: properties.ObjexMaterialProperties

        # FIXME warning spam because material_handler is called once per face
        if not objex_data.is_objex_material:
            self.log.warning("Material {!r} is not an objex material, but is used in a collision mesh, ignoring it", material)
            return None

        if not material.objex_bonus.use_collision:
            self.log.warning("Material {!r} is not a collision objex material, but is used in a collision mesh, ignoring it", material)
            return None

        cc_material = self.collected_materials.get(material)
        if cc_material is None:
            # TODO copy properties?
            cc_material = CollectedCollisionMaterial(
                material.name, material.objex_bonus.collision
            )
            self.collected_materials[material] = cc_material
        return cc_material, None, None

    def collect_collision_mesh(self, mesh, collect_materials=True):
        return collect_mesh.collect_mesh(
            mesh,
            lambda coords, uv_coords, normal, color, groups: CollectedCollisionVertex(
                coords
            ),
            material_handler=(
                lambda mat: self.material_handler(mat) if collect_materials else None
            ),
            face_image_handler=None,
            collect_uvs=False,
            collect_normals=False,
            collect_vertex_colors=False,
            collect_groups=False,
        )
