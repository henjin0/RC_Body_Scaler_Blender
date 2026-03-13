"""
RC Car Body Creator - Blender bpy スクリプト
Blender --background --python で実行される。
params.json を読み込んで全処理を行い、result.stl と loose_parts.json を出力する。
"""

import json
import math
import os
import sys

import bpy
import bmesh

# ------------------------------------------------------------------ #
#  パスの解決
# ------------------------------------------------------------------ #

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
PARAMS_PATH = os.path.join(SCRIPT_DIR, "params.json")


def log(msg: str):
    print(f"[RC-Body] {msg}", flush=True)


# ------------------------------------------------------------------ #
#  メイン処理
# ------------------------------------------------------------------ #

def main():
    # params.json 読み込み
    if not os.path.exists(PARAMS_PATH):
        print(f"ERROR: params.json not found: {PARAMS_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(PARAMS_PATH, "r", encoding="utf-8") as f:
        params = json.load(f)

    input_file = params["input_file"]
    wheels = params["wheels"]
    wb_target = params["wheelbase_target"]
    solidify_params = params["solidify"]
    cut_z_mm = params["cut_z"]
    remove_parts = params.get("remove_parts", [])
    output_dir = params.get("output_dir", os.path.join(BASE_DIR, "outputs"))
    preview_dir = params.get("preview_dir", os.path.join(BASE_DIR, "preview"))

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(preview_dir, exist_ok=True)

    # ---- Blender バージョン確認 ----
    blender_ver = bpy.app.version
    log(f"Blender version: {blender_ver[0]}.{blender_ver[1]}.{blender_ver[2]}")
    is_blender4 = blender_ver[0] >= 4

    # ---- シーンをクリア ----
    _clear_scene()

    # ---- モデルインポート ----
    log(f"Importing: {input_file}")
    obj = _import_model(input_file)
    if obj is None:
        print("ERROR: Failed to import model.", file=sys.stderr)
        sys.exit(1)

    # ---- 向き調整（UIの回転と同じ変換をBlenderで適用）----
    orientation = params.get("orientation", {})
    rx = orientation.get("rx", 0.0)
    ry = orientation.get("ry", 0.0)
    rz = orientation.get("rz", 0.0)
    if rx != 0 or ry != 0 or rz != 0:
        log(f"Applying orientation: rx={rx}, ry={ry}, rz={rz}")
        obj.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(rotation=True)

    # ---- メッシュ修復 (remove doubles) ----
    log("Repairing mesh (remove doubles)...")
    _repair_mesh(obj)

    # ---- デシメーション（ポリゴン数 > 50K の場合）----
    poly_count = len(obj.data.polygons)
    log(f"Polygon count: {poly_count}")
    if poly_count > 50000:
        log("Applying decimation (ratio=0.5)...")
        _decimate(obj, ratio=0.5)

    # ---- remove_parts モードの場合は中間ファイルを読み込んで削除のみ実施 ----
    if remove_parts:
        log(f"Removing parts: {remove_parts}")
        _clear_scene()
        intermediate_path = os.path.join(preview_dir, "intermediate.blend")
        if os.path.exists(intermediate_path):
            bpy.ops.wm.open_mainfile(filepath=intermediate_path)
            _remove_loose_parts_by_name(remove_parts)
            obj = _get_main_object()
        else:
            # 中間ファイルがない場合は全処理をやり直す
            log("Intermediate file not found. Reprocessing...")
            remove_parts = []

    if not remove_parts:
        # ---- タイヤ除去 ----
        log("Removing tires (boolean subtract)...")
        _remove_tires(obj, wheels)

        # ---- ホイールベース調整 ----
        front_x_m = wheels["front_x"] / 1000.0
        rear_x_m = wheels["rear_x"] / 1000.0
        current_wb = front_x_m - rear_x_m
        target_wb_m = wb_target / 1000.0
        if current_wb > 0:
            scale_x = target_wb_m / current_wb
            log(f"Scaling X: {scale_x:.4f} (WB: {current_wb*1000:.1f}mm -> {wb_target:.1f}mm)")
            obj.scale.x *= scale_x
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(scale=True)

        # ---- ボディ幅・高さ調整 ----
        body_target = params.get("body_target", {})
        target_width_mm  = body_target.get("width_mm",  0)
        target_height_mm = body_target.get("height_mm", 0)

        if target_width_mm > 0 or target_height_mm > 0:
            from mathutils import Vector
            bbox_corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            cur_width_m  = max(v.y for v in bbox_corners) - min(v.y for v in bbox_corners)
            cur_height_m = max(v.z for v in bbox_corners) - min(v.z for v in bbox_corners)

            if target_width_mm > 0 and cur_width_m > 1e-6:
                scale_y = (target_width_mm / 1000.0) / cur_width_m
                log(f"Scaling Y (width): {scale_y:.4f}  ({cur_width_m*1000:.1f} -> {target_width_mm:.1f} mm)")
                obj.scale.y *= scale_y
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.transform_apply(scale=True)

            if target_height_mm > 0 and cur_height_m > 1e-6:
                scale_z = (target_height_mm / 1000.0) / cur_height_m
                log(f"Scaling Z (height): {scale_z:.4f}  ({cur_height_m*1000:.1f} -> {target_height_mm:.1f} mm)")
                obj.scale.z *= scale_z
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.transform_apply(scale=True)

        # ---- ソリッファイ（肉厚付与） ----
        thickness_m = solidify_params["thickness"] / 1000.0
        direction = solidify_params["direction"]
        log(f"Solidify: thickness={solidify_params['thickness']}mm, direction={direction}")
        _solidify(obj, thickness_m, direction)

        # ---- ボディ下部カット ----
        log(f"Cutting bottom at Z={cut_z_mm}mm...")
        _cut_bottom(obj, cut_z_mm / 1000.0)

        # ---- 中間ファイル保存 ----
        intermediate_path = os.path.join(preview_dir, "intermediate.blend")
        bpy.ops.wm.save_as_mainfile(filepath=intermediate_path)

    # ---- Loose parts を分離して一覧出力 ----
    log("Separating loose parts...")
    parts_info = _separate_and_list_loose_parts(obj, preview_dir)

    # loose_parts.json を出力
    parts_json_path = os.path.join(preview_dir, "loose_parts.json")
    with open(parts_json_path, "w", encoding="utf-8") as f:
        json.dump(parts_info, f, ensure_ascii=False, indent=2)
    log(f"Loose parts: {len(parts_info)} found -> {parts_json_path}")

    # ---- STL出力（最大体積のオブジェクトを main body として出力） ----
    result_stl = os.path.join(preview_dir, "result.stl")
    _export_main_stl(result_stl, is_blender4)
    log(f"STL exported: {result_stl}")

    log("Done.")
    sys.exit(0)


# ------------------------------------------------------------------ #
#  ヘルパー関数
# ------------------------------------------------------------------ #

def _clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def _import_model(filepath: str):
    ext = os.path.splitext(filepath)[1].lower()
    try:
        if ext == ".glb" or ext == ".gltf":
            bpy.ops.import_scene.gltf(filepath=filepath)
        elif ext == ".obj":
            try:
                bpy.ops.wm.obj_import(filepath=filepath)
            except AttributeError:
                bpy.ops.import_scene.obj(filepath=filepath)
        elif ext == ".stl":
            try:
                bpy.ops.wm.stl_import(filepath=filepath)
            except AttributeError:
                bpy.ops.import_mesh.stl(filepath=filepath)
        elif ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=filepath)
        else:
            print(f"ERROR: Unsupported format: {ext}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"ERROR: Import failed: {e}", file=sys.stderr)
        return None

    # インポート後、全メッシュをひとつに結合
    mesh_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not mesh_objects:
        print("ERROR: No mesh found after import.", file=sys.stderr)
        return None

    bpy.ops.object.select_all(action='DESELECT')
    for o in mesh_objects:
        o.select_set(True)
    bpy.context.view_layer.objects.active = mesh_objects[0]

    if len(mesh_objects) > 1:
        bpy.ops.object.join()

    obj = bpy.context.view_layer.objects.active
    obj.name = "RCBody"
    return obj


def _repair_mesh(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    bmesh.update_edit_mesh(obj.data)
    bpy.ops.object.mode_set(mode='OBJECT')


def _decimate(obj, ratio: float):
    mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
    mod.ratio = ratio
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Decimate")


def _solidify(obj, thickness_m: float, direction: str):
    mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY')
    mod.thickness = thickness_m
    mod.offset = -1.0 if direction == "inner" else 1.0
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier="Solidify")


def _make_cylinder(location, radius_m: float, height_m: float, rotation_euler=None) -> bpy.types.Object:
    """Z軸回転シリンダーを作成して返す"""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=radius_m,
        depth=height_m,
        location=location,
        vertices=32,
    )
    cyl = bpy.context.object
    if rotation_euler:
        cyl.rotation_euler = rotation_euler
        bpy.ops.object.transform_apply(rotation=True)
    return cyl


def _boolean_subtract(target: bpy.types.Object, cutter: bpy.types.Object):
    """target から cutter をブーリアン差分で除去する"""
    bpy.ops.object.select_all(action='DESELECT')
    target.select_set(True)
    bpy.context.view_layer.objects.active = target

    mod = target.modifiers.new(name="Bool_Sub", type='BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    # Blender 3.x / 4.x 共通の solver 設定
    try:
        mod.solver = 'FAST'
    except AttributeError:
        pass

    bpy.ops.object.modifier_apply(modifier="Bool_Sub")

    # カッターを削除
    bpy.data.objects.remove(cutter, do_unlink=True)


def _remove_tires(obj, wheels: dict):
    """4本のタイヤをシリンダーブーリアンで除去する"""
    front_x = wheels["front_x"] / 1000.0
    rear_x = wheels["rear_x"] / 1000.0
    offset_y = wheels["offset_y"] / 1000.0

    front_r = (wheels["front_diameter"] / 2.0) / 1000.0
    front_h = wheels["front_width"] / 1000.0
    rear_r = (wheels["rear_diameter"] / 2.0) / 1000.0
    rear_h = wheels["rear_width"] / 1000.0

    # シリンダーはY軸方向（横向き）に置く
    # rotation_euler で X軸90度回転 → Y軸方向に高さが向く
    rot_y = (math.pi / 2, 0, 0)

    tire_configs = [
        # (x, y, radius, height)
        (front_x, offset_y, front_r, front_h),    # 前左
        (front_x, -offset_y, front_r, front_h),   # 前右
        (rear_x, offset_y, rear_r, rear_h),        # 後左
        (rear_x, -offset_y, rear_r, rear_h),       # 後右
    ]

    for x, y, r, h in tire_configs:
        # Z座標は車体の中心（0）付近
        cyl = _make_cylinder(location=(x, y, 0), radius_m=r, height_m=h * 2,
                             rotation_euler=rot_y)
        try:
            _boolean_subtract(obj, cyl)
        except Exception as e:
            log(f"Warning: Tire boolean failed at ({x:.3f}, {y:.3f}): {e}")


def _cut_bottom(obj, cut_z_m: float):
    """
    Z < cut_z_m の部分を大きなボックスでブーリアン差分してカット。
    cut_z_m == 0 の場合はバウンディングボックス最小Z付近を自動推定。
    """
    bbox = [obj.matrix_world @ v.co for v in obj.data.vertices]
    min_z = min(v.z for v in bbox)
    max_z = max(v.z for v in bbox)
    size_xy = max(
        max(v.x for v in bbox) - min(v.x for v in bbox),
        max(v.y for v in bbox) - min(v.y for v in bbox),
    ) * 3.0

    if cut_z_m == 0:
        # 自動: モデル高さの下10%をカット
        cut_z_m = min_z + (max_z - min_z) * 0.1

    box_height = (cut_z_m - min_z) + 1.0  # カット平面からmin_zまでの高さ + 余裕
    if box_height <= 0:
        log("Warning: cut_z is below model bottom. Skipping bottom cut.")
        return

    box_center_z = min_z + box_height / 2.0 - 0.001

    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(0, 0, box_center_z),
    )
    box = bpy.context.object
    box.scale = (size_xy, size_xy, box_height)
    bpy.ops.object.select_all(action='DESELECT')
    box.select_set(True)
    bpy.context.view_layer.objects.active = box
    bpy.ops.object.transform_apply(scale=True)

    try:
        _boolean_subtract(obj, box)
    except Exception as e:
        log(f"Warning: Bottom cut boolean failed: {e}")


def _separate_and_list_loose_parts(obj, preview_dir: str) -> list:
    """
    Loose parts を分離し、体積情報のリストを返す。
    最大体積オブジェクトを main body として残す。
    """
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')

    parts = [o for o in bpy.context.scene.objects if o.type == 'MESH']

    # 体積を計算（Blenderはメートル³で返る）
    parts_info = []
    for part in parts:
        bm = bmesh.new()
        bm.from_mesh(part.data)
        vol_m3 = abs(bm.calc_volume())
        bm.free()
        vol_mm3 = vol_m3 * 1e9  # m³ → mm³
        parts_info.append({"name": part.name, "volume_mm3": round(vol_mm3, 6)})

    # 体積でソート（昇順）→ UIでは小さい部品が上に表示される
    parts_info.sort(key=lambda x: x["volume_mm3"])
    return parts_info


def _remove_loose_parts_by_name(names: list):
    for name in names:
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)


def _get_main_object() -> bpy.types.Object | None:
    """最大体積のメッシュオブジェクトを返す"""
    mesh_objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not mesh_objects:
        return None

    def vol(o):
        bm = bmesh.new()
        bm.from_mesh(o.data)
        v = abs(bm.calc_volume())
        bm.free()
        return v

    return max(mesh_objects, key=vol)


def _export_main_stl(filepath: str, is_blender4: bool):
    """最大体積のオブジェクトをSTLとして出力"""
    main_obj = _get_main_object()
    if main_obj is None:
        print("ERROR: No mesh object to export.", file=sys.stderr)
        sys.exit(1)

    bpy.ops.object.select_all(action='DESELECT')
    main_obj.select_set(True)
    bpy.context.view_layer.objects.active = main_obj

    if is_blender4:
        try:
            bpy.ops.wm.stl_export(
                filepath=filepath,
                export_selected_objects=True,
                global_scale=1000.0,  # m → mm
            )
            return
        except Exception:
            pass

    # Blender 3.x / fallback
    try:
        bpy.ops.export_mesh.stl(
            filepath=filepath,
            use_selection=True,
            global_scale=1000.0,
        )
    except Exception as e:
        print(f"ERROR: STL export failed: {e}", file=sys.stderr)
        sys.exit(1)


# ------------------------------------------------------------------ #
#  エントリポイント
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    main()
