# **objex specification**

*Iteration 44*

# changes from .obj

#### `skellib` and `animlib`

`skellib` and `animlib` have been introduced, and work
similarly to `mtllib` (see `.skel` and `.anim` below)
- `skellib` and `animlib` must be used in that order
- multiple `skellib` and `animlib` files can be specified,
one per line, each starting with `skellib` or `animlib`
- `skellib` can be used without `animlib`, but not vice versa

#### `version`

`version major.minor` (e.g. `version 2.000`)
- if no version string is detected, zzconvert will
tell the user to upgrade their Blender script
- if `major` version is not `2`, zzconvert will
suggest upgrading zzconvert

#### `exportid`

`exportid string` (e.g. `exportid gee it sure is boring around here`)
- this is mandatory (zzconvert complains otherwise)
- the `objex` file and all files included via `mtllib`,
`animlib`, and `skellib` must contain one
- the `exportid` of all linked files must match
- to get the most out of this, `exportid` is a string
representation of the time at which the blender export
script was run (this helps to identify when something has
gone wrong during the export process, such as a file not
being updated properly due to write permissions or
plugin errors)
- `exportid` must be used before the `*lib` directives

#### `softinfo`

`softinfo one_tag string`
- store info about the software used or the file
from which the objex was exported
- currently only `animation_framerate` is supported;
this is the preview framerate that is set in blender;
if the `string` part is not `20`, zzconvert writes a
warning that the converted animations may run at a
different speed in-game than expected

#### `useskel`

`useskel name` has been introduced for specifying
which skeleton will be used to source bones named
within the `v` directive

#### `clearmtl`

`clearmtl` can be used at any time to explicitly specify
that the geometry that follows should have no material
assigned to it

#### `attrib`

`attrib attributes` (optional)
- for specifying additional group attributes not
covered by anything else
- can span multiple lines, as long as each line begins
with `attrib`
- eg: `attrib whatever you feel like man`

#### `priority`

`priority number` (optional)
- `number` is an integer (`1`, `-1`, `1000`, etc)
- groups with higher priorities are written first;
- if no priority is specified, the default is `0`;
- priority can be negative to specify a group is to be
written last
- the order in which groups sharing priority are written
is undefined

#### `origin`

`origin x y z` (optional)
- object/group position in blender world space during export
- if specified, the mesh will be translated
so that its origin will be `(0, 0, 0)`
- `origin` should only be written if the user specifies it
should in the group settings in blender

#### `v`

the `v` directive now supports (optional) weight parameters
parameters, following the form: weight, ..., weight

- e.g. `v x y z weight "Hat" 0.5, weight "Head" 0.5`
- weight works like this: `weight "bone_name" influence`
for each bone that influences the vertex
- tip: if there is only one bone, influence is `1.0`
- for zzconvert specifically, there should be only one bone with
an influence of `1.0` for vertices that are rigged to a skeleton;
otherwise, zzconvert will complain that N64 skeletons don't support
vertices influenced by multiple bones

#### `vc`

`vc r g b a` (optional)
- specifies vertex color (plus alpha)
- values must be between `0.0` and `1.0`, inclusive

#### `f`

the `f` directive now supports an optional `vc` parameter
- e.g. `f v/vt/vn/vc`
- note: it's possible for certain vertices of a triangle to
use colors and certain vertices to use shading, with
the result being interpolated in-game (N64-specific)

# .mtl files

objex supports the standard Wavefront mtl specification,
though what is done with everything besides `map_Kd`
is undefined; that's because everything has been overhauled
to work in a way fine-tuned to the Nintendo 64

## `newtex`
`newtex name` is used to specify and name a texture; it is
then described by the following directives

#### `map`

`map filename` is used to specify the image file that
will be used, relative to the `.mtl`, or absolute path
(`filename` can contain spaces, as the remainder of the
line is used as the path)

#### `pointer`

`pointer 0xPointer` (optional)
- specify a 32-bit value to write instead of the address of
the converted texture
- this is useful for having a pointer that is controlled by
a ram segment (for example, Link's eyes use `0x08000000`)
- this is also useful for referencing textures in other files
(e.g. `0x0400000400` (Hylian Shield, rgba5551, 32x64))
- the only invalid value is `0`, which means none has been set
- it must be hexadecimal

#### `format`

`format fmt` (optional*)
- specify the format to force the texture to use during
conversion; valid formats include:
- `rgba32, rgba16, ia16, ci4, ci8, ia4, ia8, i4, i8`
- `*` not optional if `pointer` has been specified, unless
`texturebank` is also used (texture banks default to `ci8`)

#### `alphamode`

`alphamode mode` (optional)
- controls how colors of alpha pixels are derived
during conversion
- `mode` must be one of the following:
- `edge`: derives alpha colors by expanding visible edge colors
- `average`: use average of all visible colors for every alpha
- `white`: every invisible pixel's color is set to white
- `black`: every invisible pixel's color is set to black
- `image`: use colors already stored in image (falls back to
`edge` on `ci` formats if more than four unique invisible colors)

#### `palette`

`palette number` (optional) (ci formats only)
- `number` is an actual number (`1`, `2`, `3`, etc) (must be > 0);
- optionally specify a palette slot to use; when multiple
textures occupy a slot, an optimized palette that factors
all their colors together is generated, and every texture
is updated to use this palette

#### `priority`

`priority number` (optional)
- `number` is an integer (`1`, `-1`, `1000`, etc)
- textures with higher priorities are written first;
- if no priority is specified, the default is `0`;
- priority can be negative to specify a texture is to be
written last, but why would you want to do that?
- the order in which textures sharing priority are written
is undefined
- use cases: textures that must be written at a certain offset
in a file (Link's eye and mouth textures, for example)

#### `forcewrite`

`forcewrite` (optional)

explicitly state that a texture is used and should be
included in the converted file, whether or not it is
actually referenced by any materials, and whether or
not those materials are used

#### `forcenowrite`

`forcenowrite` (optional)

explicitly state that a texture is unused and should not
be included in the converted file, whether or not it is
actually referenced by any materials, and whether or
not those materials are used

#### `texturebank`

`texturebank filename` (optional)
- source another file for pixel data, still using the image
specified with `map` for the texture mapping dimensions
- use cases: texture strips that are not referenced anywhere
(animated eye textures, day/night window textures, etc)
- if no format has been specified before this, it will default
to `ci8`

## `newmtl`

`newmtl name` creates a material; `newmtl` can be followed
by any of these new (optional) directives:

#### `priority`

`priority number` (optional)
- `number` is an integer (`1`, `-1`, `1000`, etc)
- geometry using higher-priority materials is written first;
- if no priority is specified, the default is `0`;
- priority can be negative to specify to write it last
- the order in which materials sharing priority are processed
is undefined
- use cases: materials that must be written last in a display
list to prevent drawing issues (triangles containing transparency
written to OPA, for example)

#### `vertexshading`

`vertexshading mode`

What to write for the color/normal part of vertices data

`mode` can be
 - color: write vc for vertex
 - normal: write vn for vertex
 - dynamic: auto-detect, allows some vertices to use colors,
 and some normals, using normals where vc is full intensity
 (`0xFFFFFFFF` opaque white)
 - none: write anything, the color/normal data part isn't
 used and doesn't matter

`dynamic` mode also switches the geometry mode `G_LIGHTING` flag accordingly

#### `gbi`

every line starting with `gbi` after a `newmtl` will be
processed as a gbi macro when constructing the material
	
```
gbi  gbiMacro
gbi  gbiMacro
#etc (for every gbi macro)
```
			
(zzconvert) there are special variables macros can contain
```
_texelXaddress
_texelXformat
_texelXbitdepth
_texelXwidth
_texelXheight
_texelXwidth-1
_texelXheight-1
_texelXmasks  (calculate appropriate masking values)
_texelXmaskt
```
where `X` is `0` or `1` depending on the texel

and

```
_group="X"
```

where `X` is the name of the group as it appears in Blender
(e.g. `_group="BunnyHood"`)

(zzconvert)
additionally, `gbi _loadtexels` can be used to generate
gbi macros for texture/palette loading of any format
automatically (this way, formats and bit depths can
change without having to adjust the macros); it generates
palette/texture calls for both texel0 and texel1

#### `gbivar`

`gbivar`
- this directive is used by zzconvert to set internal variables;
- those which aren't specified default to `0`
- the only exception to the above rule are `masks/t 0/1`, which
default to `_texel0/1masks/t`

`gbivar varName "value"`

`varName` can be any of the following
```
cms0    , cmt0    , cms1   , cmt1
masks0  , maskt0  , masks1 , maskt1
shifts0 , shiftt0 , shifts1, shiftt1
```

`"value"` can be things like `"G_TX_NOMIRROR | G_TX_CLAMP"`, etc
(the quotes are necessary)

#### `standalone`

`standalone`
another new directive is the `standalone` directive; put
this on a line below `newmtl` and zzconvert will write the
material only once to the generated file, calling it via a
DE command any time it needs it

#### `empty`

`empty`
- specifies that any geometry with the material assigned
to it is not to be written
- in place of the geometry that would have been written,
the material properties are written instead
- (you can force physics bodies (Pbodies) to always be
loaded and attached to certain limbs this way)
- starting a material name with `empty.` is another way
to specify an empty (`empty.hat` etc)

#### `texel0`, `texel1`

`texel0 name`, `texel1 name`
- for specifying which texture goes in which slot
- the texture name(s) you specify must have
been previously declared via `newtex`

#### `attrib`

`attrib attributes`
- for specifying additional material attributes not
covered by anything else
- can span multiple lines, as long as each line begins
with `attrib`
- eg: `attrib SOUND_LAVA FLOOR_LAVA` (lava floor collision)

#### `forcewrite`

`forcewrite`
- explicitly state that a material is used and should be
included in the converted file, whether or not it is
actually referenced by any geometry, and whether or
not that geometry is part of the build recipe

## (zzconvert)

zzconvert offers only minimal support for standard `.mtl`
features (only `map_Kd`); this is to provide at least enough
functionality to get a textured mesh into the game if you
are limited to `.obj` or are doing a fairly simple test; for
this reason, it is highly recommended that users use the
objex plug-in for blender

# `.skel` files

## `newskel`

every line that starts with the text `newskel`
signals that skeleton data follows

```
newskel "name" "extra"
segment 0xCustomSegment [local]
pbody [parent "anotherSkeleton" "boneName"]
```
	
`newskel` = directive

`"name"`  = name of skeleton

`"extra"` = optional game-specific fields
```
"z64player" = Link skeleton format
"z64npc"    = non-Link skeleton
"z64dummy"  = mini skeleton for producing Pbodies
              (self-contained deformable meshes)
```

#### `pbody`

`pbody [parent "sk" "bn"]` directive (optional)

any mesh rigged to this skeleton is to be treated as
a physics body (Pbody); this means no skeleton will
be stored/written, and the mesh will not be divided
in any way
- `parent` is optional
- if `parent` is used, this indicates that the Pbody
is attached to a bone within another skeleton; all
vertices that are assigned to this skeleton's root
bone are treated as if they were assigned directly
to the skeleton's parent

#### `segment`

`segment 0xSegment [local]` directive (optional)
- when a line begins with the `segment` directive,
this can be used to customize the segment where
deformation matrices for the skeleton are stored
- ex: `segment 0x0B000000`
- it must be hexadecimal
- if the provided address is followed by a space
and the string `local`, the matrix is treated as
local to the compiled binary and is initialized
with an identity matrix
  - it is the user's responsibility to ensure that
	the data at the provided address is safe for
	zzconvert to overwrite in this fashion
  - ex: `segment 0x06005800 local`
- if no segment is provided, zzconvert defaults to `0x0D000000`

#### bones

`(bones * 2)` lines follow the skeleton header;
the first non-blank character on each line will be
either `+` or `-`, which mean push or pop, respectively;
when a bone is pushed (`+`), this format follows:

```
"name" pos.x pos.y pos.z
```

`"name"` = name of bone

`pos`    = position of bone relative to parent

there should be equal numbers of `+` and `-`

sample:

```
newskel "player" "z64player"
+ "RootControl" 0.000000 0.000000 -0.000000
	+ "Waist" -0.004000 -0.104000 -0.000000
		+ "LowerControl" 0.607000 0.000000 -0.000000
			+ "Thigh.R" -0.172000 0.050000 -0.190000
				+ "Shin.R" 0.697000 0.000000 -0.000000
					+ "Foot.R" 0.825000 0.005000 0.011000
					-
				-
			-
			+ "Thigh.L" -0.170000 0.057000 0.192000
				+ "Shin.L" 0.695000 0.000000 -0.000000
					+ "Foot.L" 0.817000 0.008000 0.004000
					-
				-
			-
		-
	-
	+ "UpperControl" 0.000000 -0.103000 -0.007000
		+ "Head" 0.996000 -0.201000 -0.001000
			+ "Hat" -0.365000 -0.670000 -0.000000
			-
		-
		+ "Collar" 0.000000 0.000000 -0.000000
		-
		+ "Shoulder.L" 0.696000 -0.175000 0.466000
			+ "Forearm.L" 0.581000 0.000000 -0.000000
				+ "Hand.L" 0.514000 0.000000 -0.000000
				-
			-
		-
		+ "Shoulder.R" 0.696000 -0.175000 -0.466000
			+ "Forearm.R" 0.577000 0.000000 -0.000000
				+ "Hand.R" 0.525000 0.000000 -0.000000
				-
			-
		-
		+ "Sheath" 0.657000 -0.523000 0.367000
		-
		+ "Torso" 0.000000 0.000000 -0.000000
		-
	-
-
```

# `.anim` files

## `newanim`

every line that starts with the text `newanim`
signals that animation data follows

```
newanim "skel" "name" frames
```

`newanim` = directive

`"skel"`  = name of skeleton animation deforms

`"name"`  = name of animation

`frames`  = number of frames

each `newanim` line is followed immediately by data
for every frame

sample:

```
newanim "player" "salute" 10
loc pos.x pos.y pos.z ms
rot rot.x rot.y rot.z
rot rot.x rot.y rot.z
...
loc pos.x pos.y pos.z ms
#etc
```

`ms` is optional, and in the case of animations that use
a keyframable format, refers to where on a timeline the
frame would fall, in milliseconds

also in the case of keyframable animations, a copy of the
first frame is written as the last frame, with the `ms`
attribute signifying the end time of the animation

# group naming conventions

## collision

group names beginning with `collision` represent
collections of triangles which can be walked on,
function as walls, ladders, etc; `collision` is
followed by a `.`, then the name	(`collision.carriage`)

important points:
- all collision associated with a single object
fits inside one such `collision.name` group
- we do not divide it based on flags
- flags are controlled via materials instead;
this has the added benefit of each flag being
visibly distinct, and being able to adjust
triangles without having to modify multiple groups

all collision attributes are packed into the `.mtl`
file using the `attrib` directive; how collision
attributes are configured is entirely vendor-specific

## colliders

group names beginning with `collider` represent
colliders (hitboxes, hurtboxes, bumpboxes);
`collider` is always followed by a `.`, then
the type, then a `.`, then its name
(`collider.joints.wolfHurtbox`)

types follow different rules:

#### collider.joints

- collider must be rigged to a skeleton
- collider mesh is made up of separate spheres/cubes,
assigned to one bone each
- multiple spheres/cubes can be assigned to the same
bone within the same group; this helps prevent gaps
on skeletons with greater distances between bones
- multiple `collider.joints` groups can be rigged to
the same skeleton (e.g. you may find it beneficial in
some cases to put hurt/hit boxes in separate groups)
- settings for each individual joint are controlled
via material attributes
(see: `collider material attributes`)
- in addition to the above, independent settings that
control how the game treats the collection are
specified by group attributes
(see: `collider group attributes`)

#### collider.cylinder

- these must not be rigged to a skeleton
- colliders are positioned in world space, where the
origin of the world is considered the coordinates of
the enemy/NPC/etc
- in the context of z64, such relative positioning is
usually pointless, because the collider's center is
snapped to the entity's coordinates
- one exception to the above is a cylinder's offset from
the origin along the Y axis (y_shift)
- settings for each are controlled via group and material
attributes (see: `collider group attributes`,
`collider material attributes`)

```
TODO maybe in a future revision:
collider.sphere
collider.quad
```

#### zzconvert specific

##### collider group attributes

when a group directive `g` specifies a collider
(ex. `g collider.joints.wolfHurtbox`), any lines
that follow that start with `attrib` can be used
to specify attributes; they follow this format:

`attrib X 0xZ`
- where `X` is the name of the attribute
- and `Z` is the value (in this case, as a hexadecimal uint32_t)

for collider groups, the following attributes may be specified
(if an attribute is not specified, it is treated as 0)
- `collider.type`
- `collider.atFlags`
- `collider.acFlags`
- `collider.maskA`
- `collider.maskB`

##### collider material attributes
		
when a collider mesh has a material assigned to it, it uses
the material's attributes for its settings
(see `attrib attributes` for material attribute explanation)

the material attributes for colliders are expected to follow
this format:

`attrib X 0xZ`
 - where `X` is the name of the attribute
 - and `Z` is the value (in this case, as a hexadecimal uint32_t)

for collider groups, the following attributes may be specified
(if an attribute is not specified, it is treated as 0)
 - `collider.bodyFlags`
 - `collider.touchFlags`
 - `collider.touchFx`
 - `collider.bumpFlag`
 - `collider.bumpFx`
 - `collider.tchBmpBdy`
beware that these are packed values that may contain padding;
for instance, touchFx is broken down like so: `eedd0000`, where
`ee` = effect, `dd` = damage, `0000` = padding

##### collision material attributes

All attributes in the following tables should be prefixed with `collision.`,
for example a complete line would be `attrib collision.IGNORE_CAMERA`.

Some attributes such as `WATERBOX` accept parameters like so:
`attrib collision.WATERBOX,light=0,camera=0,room=0`

<details>
<summary>list of attributes</summary>

| | Ignore Settings |
|-|-|
| `IGNORE_CAMERA` | Camera can pass through it |
| `IGNORE_ENTITY` | Link, enemies, etc. can pass through it |
| `IGNORE_AMMO` | Deku Seeds, Arrows, Bombchus, etc. can pass through it |

| | Sound Settings (unless otherwise stated, the sound made when struck with a sword is the default metallic one) |
|-|-|
| `SOUND_DIRT` | Earth/Dirt |
| `SOUND_SAND` | Sand |
| `SOUND_STONE` | Stone |
| `SOUND_STONE_WET` | Stone (wet) |
| `SOUND_SPLASH` | Shallow water |
| `SOUND_SPLASH_1` | Shallow water (lower-pitched) |
| `SOUND_GRASS` | Underbrush/Grass |
| `SOUND_LAVA` | Lava/Goo |
| `SOUND_DIRT_1` | Earth/Dirt (duplicate) |
| `SOUND_WOOD` | Wooden |
| `SOUND_WOOD_STRUCK` | (formerly `SOUND_DIRT_PACKED`)  Packed Earth/Wood (makes wooden sound when struck) |
| `SOUND_DIRT_2` | Earth/Dirt (duplicate) |
| `SOUND_CERAMIC` | Ceramic |
| `SOUND_DIRT_LOOSE` | Loose Earth/Dirt |
| `SOUND_DIRT_3` | Earth/Dirt (duplicate) |
| `SOUND_DIRT_4` | Earth/Dirt (duplicate) |

| | Floor Settings |
|-|-|
| `FLOOR_VOID_SCENE` | (formerly `FLOOR_PIT_SMALL`) Voids Link out, returns you to the last -scene- you entered |
| `FLOOR_VOID_ROOM` | (formerly `FLOOR_PIT_LARGE`) Voids Link out, returns you to the last -room- you entered |
| `FLOOR_JUMP_VINE` | Instead of jumping, climb down |
| `FLOOR_JUMP_HANG` | (formerly `FLOOR_AIR_STOP`) Instead of jumping, hang from ledge |
| `FLOOR_JUMP_FALL` | Instead of jumping, step off the platform into falling state |
| `FLOOR_JUMP_DIVE` | Instead of jumping, activate diving animation/state |

| | Floor Settings (SPECIAL) |
|-|-|
| `FLOOR_LAVA` | Lava |
| `FLOOR_LAVA_1` | Lava (TODO: What's the difference?) |
| `FLOOR_SAND` | Sand |
| `FLOOR_ICE` | Ice |
| `FLOOR_NOFALLDMG` | No Fall Damage |
| `FLOOR_QUICKHORSE` | Quicksand, passable on horseback |
| `FLOOR_QUICKSAND` | Quicksand |
| `FLOOR_STEEP` | Steep Surface (causes Link to slide) |

| | Wall Settings (SPECIAL) |
|-|-|
| `WALL_BARRIER` | (formerly `WALL_NOGRAB`) Link will not jump over or attempt to climb the wall, even if it is short enough for these actions |
| `WALL_LADDER` | Ladder |
| `WALL_LADDER_TOP` | Ladder (Top), makes Link climb down onto a ladder |
| `WALL_VINES` | Climbable Vine Wall |
| `WALL_CRAWL` | Wall used to activate/deactivate crawling |
| `WALL_CRAWL_1` | TODO: What's the difference? |
| `WALL_PUSHBLOCK` | Pushblock |
| `WALL_DAMAGE` | Wall Damage |

| | Ungrouped Settings |
|-|-|
| `SPECIAL_BLEEDWALL` | Spawns "blood" particles when struck, special sound when struck with sword (used in Jabu-Jabu's Belly) (TODO: Walls, floors, or both?) |
| `SPECIAL_INSTAVOID` | Instantly void out on contact |
| `SPECIAL_LOOKUP` | Causes Link to look upwards when he stands on it |
| `NOHORSE` | Epona can't walk on the polygon |
| `RAYCAST` | Paths? Decreases surface height in raycast function by 1 |
| `HOOKSHOT` | Hookshot |
| `DOUBLE_SIDED` | Double-sided geometry. <br> **Do not use this** <br> it's for lazy people <br> apparently if Link rolls into it, he'll clip through it <br> please do it the way Nintendo did instead by giving such meshes thickness <br> this has the added benefit of Link being able to jump over and/or climb onto them (e.g. fences) |


**WATERBOX**

| Name | Parameter Description | Default (if not set) |
|-|-|-|
| `light` | environment/lighting setting to use while camera is inside waterbox | 0 |
| `camera` | fixed camera setting to use | 0 |
| `room` | room where waterbox is active | active in all rooms |

**WARP**

`attrib collision.WARP,exit=%d`

- `exit` Scene Exit Table Index (0-indexed, meaning 0 is the first table entry)

**CAMERA**

`attrib collision.CAMERA,id=%d`

- `id` Mesh Camera Data Index ID

**ECHO**

TODO: Confirm if this controls sound echo, music echo, etc.

`attrib collision.ECHO,value=%d`

**LIGHTING**

TODO: Confirm if this controls sound echo, music echo, etc.

`attrib collision.LIGHTING,value=%d`

**CONVEYOR**

`attrib collision.CONVEYOR,direction=%d,speed=%d`

`attrib collision.CONVEYOR,direction=%d,speed=%d,inherit`

- `direction` range 0 - 360

- `speed` range 0.none, 1.slow, 2.medium, 3.fast

- `inherit` is optional; if enabled, a `0`-speed conveyor triangle will have the speed of the conveyor triangle stepped on immediately before it

</details>

##### mesh attributes
		
objex groups can contain attributes (see `attrib attributes`)

the following zzconvert mesh attribs are supported:
- `LIMBMTX` = include explicit limb matrix at start of Dlist
- `POSMTX`  = include world positioning matrix at start of Dlist
- `BBMTXS`  = include spherical billboard matrix in Dlist
- `BBMTXC`  = include cylindrical billboard matrix in Dlist
- `NOSPLIT` = do not divide mesh by bones (and do not write skeleton)
- `NOSKEL`  = do not write a skeleton to the generated zobj
- `PROXY`   = write a proxy Dlist (will have `_PROXY` suffix)
  - in the case of a divided mesh, a proxy is written
		  for each Dlist, and a C array is generated
  - if `NOSKEL` is not present (if a skeleton is written), that C array data is also written to zobj at `PROXY_` offset and the skeleton points to that table
  - in play-as data, display list pointers point to
		  the proxy for each instead of the real display list

example:
```
g Gauntlet.L
attrib LIMBMTX
```
