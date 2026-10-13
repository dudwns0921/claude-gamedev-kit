"""Finishes a downloaded mesh into the shape the game takes. Run by Blender — called by asset.py finish.

  blender --background --factory-startup --python blender_finish.py -- <downloaded.glb> <output file> <size m> <glb|fbx>

What it does: joins the meshes into one, scales so the longest side is <size>, puts the origin at the center of the base, bakes the transforms and exports.
It ends by printing one line, `FINISH {"tris": …, "size": [width, height, depth]}` (Y is up — as in glTF).
"""
import json
import sys

import bpy

src, dst, size, fmt = sys.argv[sys.argv.index("--") + 1:]
size = float(size)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    sys.exit("no mesh")

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(bpy.context.scene.objects):  # empty nodes that came along on import
    if o != obj:
        bpy.data.objects.remove(o, do_unlink=True)

# Inside Blender Z is up. On export it becomes Y up
co = [v.co.copy() for v in obj.data.vertices]
lo = [min(c[i] for c in co) for i in range(3)]
hi = [max(c[i] for c in co) for i in range(3)]
longest = max(hi[i] - lo[i] for i in range(3))
if longest <= 0:
    sys.exit("the mesh has no size")
k = size / longest
cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
for v in obj.data.vertices:
    v.co = ((v.co.x - cx) * k, (v.co.y - cy) * k, (v.co.z - lo[2]) * k)
obj.location = (0, 0, 0)
obj.data.update()

obj.data.calc_loop_triangles()
tris = len(obj.data.loop_triangles)
dims = [round((hi[i] - lo[i]) * k, 3) for i in (0, 2, 1)]

obj.select_set(True)
if fmt == "fbx":
    bpy.ops.export_scene.fbx(filepath=dst, use_selection=True, apply_scale_options="FBX_SCALE_ALL", path_mode="COPY",
                             embed_textures=True)
else:
    bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", use_selection=True)
print("FINISH " + json.dumps({"tris": tris, "size": dims}))
