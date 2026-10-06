"""받은 메쉬를 게임에 넣을 모양으로 다듬는다. Blender 가 돌린다 — asset.py finish 가 부른다.

  blender --background --factory-startup --python blender_finish.py -- <받은.glb> <나갈 파일> <크기 m> <glb|fbx>

하는 일: 메쉬를 하나로 합치고, 가장 긴 변이 <크기> 가 되게 맞추고, 원점을 바닥 가운데에 두고, 변환을 구워 내보낸다.
끝에 `FINISH {"tris": …, "size": [가로, 높이, 깊이]}` 한 줄을 적는다 (Y 가 위 — glTF 와 같다).
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
    sys.exit("메쉬가 없다")

bpy.ops.object.select_all(action="DESELECT")
for o in meshes:
    o.select_set(True)
bpy.context.view_layer.objects.active = meshes[0]
if len(meshes) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for o in list(bpy.context.scene.objects):  # 가져올 때 딸려 온 빈 노드
    if o != obj:
        bpy.data.objects.remove(o, do_unlink=True)

# Blender 안에서는 Z 가 위다. 내보낼 때 Y 가 위로 바뀐다
co = [v.co.copy() for v in obj.data.vertices]
lo = [min(c[i] for c in co) for i in range(3)]
hi = [max(c[i] for c in co) for i in range(3)]
longest = max(hi[i] - lo[i] for i in range(3))
if longest <= 0:
    sys.exit("메쉬에 크기가 없다")
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
