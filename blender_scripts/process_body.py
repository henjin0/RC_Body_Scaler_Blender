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
    # mode: "full"（全処理）or "tire_cut_only"（タイヤカットのみ）
    mode = params.get("mode", "full")

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(preview_dir, exist_ok=True)

    # ---- Blender バージョン確認 ----
    blender_ver = bpy.app.version
    log(f"Blender version: {blender_ver[0]}.{blender_ver[1]}.{blender_ver[2]}")
    is_blender4 = blender_ver[0] >= 4

    # ---- 貫通カットモード ----
    # スケール＋カット済みの intermediate.blend に円柱ブーリアンを追加適用する。
    # フルパイプライン完了後に独立して実行できる。
    if mode == "through_cut":
        intermediate_path = os.path.join(preview_dir, "intermediate.blend")
        scale_info_path   = os.path.join(preview_dir, "scale_info.json")
        output_stl        = params.get("output_stl", os.path.join(preview_dir, "result.stl"))

        if not os.path.exists(intermediate_path):
            print("ERROR: intermediate.blend not found. Run full pipeline first.", file=sys.stderr)
            sys.exit(1)

        _clear_scene()
        bpy.ops.wm.open_mainfile(filepath=intermediate_path)
        obj = _get_main_object()
        if obj is None:
            print("ERROR: No mesh in intermediate.blend", file=sys.stderr)
            sys.exit(1)

        # スケール情報を読み込み（フルパイプライン時に保存したもの）
        applied_scale_x = applied_scale_y = applied_scale_z = 1.0
        if os.path.exists(scale_info_path):
            with open(scale_info_path) as _sf:
                _si = json.load(_sf)
            applied_scale_x = _si.get("scale_x", 1.0)
            applied_scale_y = _si.get("scale_y", 1.0)
            applied_scale_z = _si.get("scale_z", 1.0)
            log(f"Scale info: x={applied_scale_x:.4f} y={applied_scale_y:.4f} z={applied_scale_z:.4f}")

        through_cut = params.get("through_cut", {})
        front_d = through_cut.get("front_diameter", 0)
        rear_d  = through_cut.get("rear_diameter",  0)

        if front_d > 0 or rear_d > 0:
            log(f"Through-cut: front={front_d}mm  rear={rear_d}mm")
            thru_wheels = {
                "front_x":        wheels["front_x"]  * applied_scale_x,
                "rear_x":         wheels["rear_x"]   * applied_scale_x,
                "offset_y":       wheels["offset_y"] * applied_scale_z,
                "front_diameter": front_d,
                "rear_diameter":  rear_d,
                "front_cy": (wheels["front_cy"] * applied_scale_y
                             if wheels.get("front_cy") is not None else None),
                "rear_cy":  (wheels["rear_cy"]  * applied_scale_y
                             if wheels.get("rear_cy")  is not None else None),
            }
            _remove_tires(obj, thru_wheels)
        else:
            log("Through-cut: no diameters specified, exporting as-is.")

        # Loose parts を再分離してCleanupリストを更新（貫通カット後の状態を反映）
        parts_info = _separate_and_list_loose_parts(obj, preview_dir, is_blender4)
        parts_json_path = os.path.join(preview_dir, "loose_parts.json")
        with open(parts_json_path, "w", encoding="utf-8") as _pf:
            json.dump(parts_info, _pf, ensure_ascii=False, indent=2)
        log(f"Loose parts updated (through_cut): {len(parts_info)} found")

        # 中間ファイルを分離後の状態で保存（Cleanupのremove_partsで名前が一致するように）
        bpy.ops.wm.save_as_mainfile(filepath=intermediate_path)

        _export_main_stl(output_stl, is_blender4)
        log(f"STL exported (through_cut): {output_stl}")
        log("Done.")
        sys.exit(0)

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
            # ※ intermediate.blend の再保存は loose_parts 分離後に一括して行う（下方）
        else:
            # 中間ファイルがない場合は全処理をやり直す
            log("Intermediate file not found. Reprocessing...")
            remove_parts = []

    if not remove_parts:
        # 各軸の適用スケール係数を記録（ホイールアーチ追加カットの座標補正に使用）
        applied_scale_x = 1.0
        applied_scale_y = 1.0
        applied_scale_z = 1.0

        # ---- ホイールベース調整 ----
        # 注意: STLはmm値のままBlenderにインポートされるため、単位変換は不要。
        # Blender内の座標値 = vispy内のmm値（どちらも同一の数値）
        front_x = wheels["front_x"]
        rear_x  = wheels["rear_x"]
        current_wb = front_x - rear_x
        if current_wb > 0:
            scale_x = wb_target / current_wb
            applied_scale_x = scale_x
            log(f"Scaling X: {scale_x:.4f} (WB: {current_wb:.1f}mm -> {wb_target:.1f}mm)")
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
            # 向き調整後: Blender Z = 左右（幅）、Blender Y = 上下（高さ）
            cur_width  = max(v.z for v in bbox_corners) - min(v.z for v in bbox_corners)
            cur_height = max(v.y for v in bbox_corners) - min(v.y for v in bbox_corners)

            if target_width_mm > 0 and cur_width > 1e-3:
                scale_z = target_width_mm / cur_width
                applied_scale_z = scale_z
                log(f"Scaling Z (width): {scale_z:.4f}  ({cur_width:.1f} -> {target_width_mm:.1f} mm)")
                obj.scale.z *= scale_z
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.transform_apply(scale=True)

            if target_height_mm > 0 and cur_height > 1e-3:
                scale_y = target_height_mm / cur_height
                applied_scale_y = scale_y
                log(f"Scaling Y (height): {scale_y:.4f}  ({cur_height:.1f} -> {target_height_mm:.1f} mm)")
                obj.scale.y *= scale_y
                bpy.ops.object.select_all(action='DESELECT')
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.transform_apply(scale=True)

        # ---- 伸縮（stretch）と平行移動（offset）----
        shape = params.get("shape", {})
        stretch_x = shape.get("stretch_x", 1.0)
        stretch_y = shape.get("stretch_y", 1.0)
        stretch_z = shape.get("stretch_z", 1.0)
        offset_x  = shape.get("offset_x",  0.0)
        offset_y  = shape.get("offset_y",  0.0)
        offset_z  = shape.get("offset_z",  0.0)

        if stretch_x != 1.0 or stretch_y != 1.0 or stretch_z != 1.0:
            log(f"Stretch: x={stretch_x:.3f}  y={stretch_y:.3f}  z={stretch_z:.3f}")
            from mathutils import Vector
            bbox_c = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            cx = (max(v.x for v in bbox_c) + min(v.x for v in bbox_c)) / 2.0
            cy = (max(v.y for v in bbox_c) + min(v.y for v in bbox_c)) / 2.0
            cz = (max(v.z for v in bbox_c) + min(v.z for v in bbox_c)) / 2.0
            # 重心を原点に移動 → スケール → 戻す
            obj.location.x -= cx;  obj.location.y -= cy;  obj.location.z -= cz
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=True)
            obj.scale.x *= stretch_x
            obj.scale.y *= stretch_y
            obj.scale.z *= stretch_z
            bpy.ops.object.transform_apply(scale=True)
            obj.location.x += cx;  obj.location.y += cy;  obj.location.z += cz
            bpy.ops.object.transform_apply(location=True)

        if offset_x != 0.0 or offset_y != 0.0 or offset_z != 0.0:
            log(f"Offset: x={offset_x:.1f}  y={offset_y:.1f}  z={offset_z:.1f}")
            obj.location.x += offset_x
            obj.location.y += offset_y
            obj.location.z += offset_z
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=True)

        # ---- メッシュ修復 ----
        log("Repairing mesh...")
        _repair_mesh(obj)

        # ---- タイヤ除去（ソリッドモデルに対して先に実施）----
        # ソリッド状態でタイヤカットしてから中空化することで Boolean が安定し、
        # ホイールハウス内側に余分な壁も生じない。
        # スケール適用後のモデル座標に合わせて座標値を補正してから渡す。
        log("Removing tires (boolean subtract on solid)...")
        scaled_wheels = dict(wheels)
        scaled_wheels["front_x"]        = wheels["front_x"]        * applied_scale_x
        scaled_wheels["rear_x"]         = wheels["rear_x"]         * applied_scale_x
        scaled_wheels["offset_y"]       = wheels["offset_y"]       * applied_scale_z
        scaled_wheels["front_diameter"] = wheels["front_diameter"] * applied_scale_x
        scaled_wheels["rear_diameter"]  = wheels["rear_diameter"]  * applied_scale_x
        if wheels.get("front_cy") is not None:
            scaled_wheels["front_cy"] = wheels["front_cy"] * applied_scale_y
        if wheels.get("rear_cy") is not None:
            scaled_wheels["rear_cy"]  = wheels["rear_cy"]  * applied_scale_y
        log(f"  scaled front_x={scaled_wheels['front_x']:.1f}  rear_x={scaled_wheels['rear_x']:.1f}"
            f"  offset_y={scaled_wheels['offset_y']:.1f}"
            f"  front_d={scaled_wheels['front_diameter']:.1f}  rear_d={scaled_wheels['rear_diameter']:.1f}")
        _remove_tires(obj, scaled_wheels)

        if mode == "tire_cut_only":
            log("mode=tire_cut_only: スケール後・中空化後のタイヤカット結果を出力します")
            result_stl = os.path.join(preview_dir, "result.stl")
            _export_main_stl(result_stl, is_blender4)
            log(f"STL exported (tire_cut_only): {result_stl}")
            log("Done.")
            sys.exit(0)

        # ---- 中空化（タイヤカット済みソリッドに対して実施）----
        # タイヤカット後のソリッドを内側縮小コピーとの差分で中空化する。
        # タイヤホール形状が内側シェルにも反映されるため余分な壁が生じない。
        thickness   = solidify_params["thickness"]                # mm
        inner_ratio = solidify_params.get("inner_ratio", 1.0)   # 0.0–1.0 上部カット
        inner_front = solidify_params.get("inner_front", 1.0)   # 0.0–1.0 前方カット
        inner_rear  = solidify_params.get("inner_rear",  1.0)   # 0.0–1.0 後方カット
        log(f"Hollow Boolean: thickness={thickness}mm  "
            f"ratio={inner_ratio:.2f}  front={inner_front:.2f}  rear={inner_rear:.2f}")
        _hollow_boolean(obj, thickness, inner_ratio, inner_front, inner_rear)

        # ---- ボディ下部カット ----
        # cut_z_mm は処理前モデルのvispy Y座標（= Blender Y値）。
        # Yスケール適用後の座標に補正して渡す。
        cut_y = cut_z_mm * applied_scale_y
        log(f"Cutting bottom at Y={cut_y:.1f}mm "
            f"(picked={cut_z_mm:.1f}mm × scale_y={applied_scale_y:.4f})...")
        _cut_bottom(obj, cut_y)

        # ---- スケール情報保存（貫通カットモードで使用）----
        scale_info_path = os.path.join(preview_dir, "scale_info.json")
        with open(scale_info_path, "w", encoding="utf-8") as _sf:
            json.dump({
                "scale_x": applied_scale_x,
                "scale_y": applied_scale_y,
                "scale_z": applied_scale_z,
            }, _sf, indent=2)
        log(f"Scale info saved: x={applied_scale_x:.4f} y={applied_scale_y:.4f} z={applied_scale_z:.4f}")

    # ---- Loose parts を分離して一覧出力 ----
    log("Separating loose parts...")
    parts_info = _separate_and_list_loose_parts(obj, preview_dir, is_blender4)

    # loose_parts.json を出力
    parts_json_path = os.path.join(preview_dir, "loose_parts.json")
    with open(parts_json_path, "w", encoding="utf-8") as f:
        json.dump(parts_info, f, ensure_ascii=False, indent=2)
    log(f"Loose parts: {len(parts_info)} found -> {parts_json_path}")

    # ---- 中間ファイル保存（分離後に保存することでremove_partsで名前が一致する）----
    intermediate_path = os.path.join(preview_dir, "intermediate.blend")
    bpy.ops.wm.save_as_mainfile(filepath=intermediate_path)

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



def _hollow_boolean(obj, thickness: float,
                    inner_ratio: float = 1.0,
                    inner_front: float = 1.0,
                    inner_rear:  float = 1.0):
    """
    スケール済みモデルから「厚さ分だけ縮小した内側コピー」をブーリアン差分して中空化する。

    各軸の縮小スケール = (outer_dim - 2*thickness) / outer_dim
    スケールはバウンディングボックス中心まわりに適用するため、
    平坦面の壁厚は thickness mm に正確に一致する。

    inner_ratio : 0–1。上部カット比率。1.0=フル中空化、0.5=下50%のみ中空化。
    inner_front : 0–1。前方カット比率。モデル中心から前方へ何%まで内側シェルを使うか。
    inner_rear  : 0–1。後方カット比率。モデル中心から後方へ何%まで内側シェルを使うか。

    カットが必要な場合はブーリアン INTERSECT（keep-box との共通部分）を使うため、
    切断面は自動でキャップされ閉じたソリッドになる。
    """
    from mathutils import Vector

    bbox     = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    min_x    = min(v.x for v in bbox);  max_x = max(v.x for v in bbox)
    min_y    = min(v.y for v in bbox);  max_y = max(v.y for v in bbox)
    min_z    = min(v.z for v in bbox);  max_z = max(v.z for v in bbox)
    cur_x    = max_x - min_x
    cur_y    = max_y - min_y
    cur_z    = max_z - min_z
    x_mid    = (min_x + max_x) / 2.0

    min_dim = 4 * thickness
    if cur_x < min_dim or cur_y < min_dim or cur_z < min_dim:
        log(f"Warning: Model too small to hollow "
            f"(x={cur_x:.1f} y={cur_y:.1f} z={cur_z:.1f} / min={min_dim:.1f}mm). Skipping.")
        return

    sx = (cur_x - 2 * thickness) / cur_x
    sy = (cur_y - 2 * thickness) / cur_y
    sz = (cur_z - 2 * thickness) / cur_z

    log(f"  outer: x={cur_x:.1f} y={cur_y:.1f} z={cur_z:.1f} mm")
    log(f"  inner scale: sx={sx:.4f} sy={sy:.4f} sz={sz:.4f}")
    log(f"  inner_ratio={inner_ratio:.2f}  inner_front={inner_front:.2f}  inner_rear={inner_rear:.2f}")

    # ── 内側コピーを作成 ──────────────────────────────────────
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicate(linked=False)
    inner_obj = bpy.context.active_object
    inner_obj.name = "RCBody_Inner"

    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    inner_obj.scale.x *= sx
    inner_obj.scale.y *= sy
    inner_obj.scale.z *= sz

    bpy.ops.object.select_all(action='DESELECT')
    inner_obj.select_set(True)
    bpy.context.view_layer.objects.active = inner_obj
    bpy.ops.object.transform_apply(scale=True)

    # ── カットが必要な場合: keep-box との INTERSECT で閉じたソリッドを維持 ────
    # INTERSECT は切断面を自動キャップするため、開いたメッシュにならない。
    inner_ratio = max(0.0, min(1.0, inner_ratio))
    inner_front = max(0.0, min(1.0, inner_front))
    inner_rear  = max(0.0, min(1.0, inner_rear))

    needs_cut = (inner_ratio < 1.0 or inner_front < 1.0 or inner_rear < 1.0)
    if needs_cut:
        pad = max(cur_x, cur_y, cur_z) * 2.0

        # keep-box の各軸範囲を計算
        # Y (上下): 底面から inner_ratio × 高さ まで
        keep_y_lo = min_y - pad
        keep_y_hi = (min_y + inner_ratio * cur_y) if inner_ratio < 1.0 else (max_y + pad)

        # X (前後): 中心から前方 inner_front × 前半長、後方 inner_rear × 後半長
        keep_x_hi = (x_mid + inner_front * (max_x - x_mid)) if inner_front < 1.0 else (max_x + pad)
        keep_x_lo = (x_mid - inner_rear  * (x_mid - min_x)) if inner_rear  < 1.0 else (min_x - pad)

        # Z (左右): カットなし、余裕を持たせる
        keep_z_lo = min_z - pad
        keep_z_hi = max_z + pad

        box_cx = (keep_x_lo + keep_x_hi) / 2.0
        box_cy = (keep_y_lo + keep_y_hi) / 2.0
        box_cz = (keep_z_lo + keep_z_hi) / 2.0
        box_sx = keep_x_hi - keep_x_lo
        box_sy = keep_y_hi - keep_y_lo
        box_sz = keep_z_hi - keep_z_lo

        log(f"  Keep-box: X=[{keep_x_lo:.1f},{keep_x_hi:.1f}]  "
            f"Y=[{keep_y_lo:.1f},{keep_y_hi:.1f}]  Z=[{keep_z_lo:.1f},{keep_z_hi:.1f}]")

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(box_cx, box_cy, box_cz))
        keep_box = bpy.context.object
        keep_box.scale.x = box_sx
        keep_box.scale.y = box_sy
        keep_box.scale.z = box_sz
        bpy.ops.object.select_all(action='DESELECT')
        keep_box.select_set(True)
        bpy.context.view_layer.objects.active = keep_box
        bpy.ops.object.transform_apply(scale=True)

        _boolean_intersect(inner_obj, keep_box)

    # ── ブーリアン差分: 外側 − 内側 = 中空シェル ─────────────
    _boolean_subtract(obj, inner_obj)


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
    # EXACT ソルバーを優先（より確実）、なければ FAST にフォールバック
    try:
        mod.solver = 'EXACT'
    except (AttributeError, TypeError):
        try:
            mod.solver = 'FAST'
        except (AttributeError, TypeError):
            pass

    vert_before = len(target.data.vertices)
    bpy.ops.object.modifier_apply(modifier="Bool_Sub")
    vert_after = len(target.data.vertices)
    log(f"  Boolean: {vert_before} verts → {vert_after} verts")

    # カッターを削除
    bpy.data.objects.remove(cutter, do_unlink=True)


def _boolean_intersect(target: bpy.types.Object, keep_box: bpy.types.Object):
    """target と keep_box のブーリアン積（INTERSECT）を target に適用する。
    INTERSECT はカット断面を自動でキャップするため、閉じたソリッドが得られる。"""
    bpy.ops.object.select_all(action='DESELECT')
    target.select_set(True)
    bpy.context.view_layer.objects.active = target

    mod = target.modifiers.new(name="Bool_Intersect", type='BOOLEAN')
    mod.operation = 'INTERSECT'
    mod.object = keep_box
    try:
        mod.solver = 'EXACT'
    except (AttributeError, TypeError):
        try:
            mod.solver = 'FAST'
        except (AttributeError, TypeError):
            pass

    vert_before = len(target.data.vertices)
    bpy.ops.object.modifier_apply(modifier="Bool_Intersect")
    vert_after = len(target.data.vertices)
    log(f"  Boolean INTERSECT: {vert_before} verts → {vert_after} verts")

    bpy.data.objects.remove(keep_box, do_unlink=True)


def _remove_tires(obj, wheels: dict):
    """4本のタイヤをシリンダーブーリアンで除去する。
    向き調整（transform_apply）後の座標系：
      Blender X = vispy X = 前後方向
      Blender Y = vispy Y = 上下方向（高さ）
      Blender Z = vispy Z = 左右方向（幅）
    タイヤの軸はZ軸方向（左右）なのでデフォルトBlenderシリンダー（Z軸整列）をそのまま使う。
    """
    from mathutils import Vector

    # 単位: STLはmm値のままBlenderにインポートされるため /1000 不要
    front_x  = wheels["front_x"]
    rear_x   = wheels["rear_x"]
    offset_z = wheels["offset_y"]   # 左右オフセット (mm)

    front_r = wheels["front_diameter"] / 2.0
    rear_r  = wheels["rear_diameter"]  / 2.0

    # タイヤ中心Y: UIでクリックした位置（vispy Y = Blender Y値）を優先。
    # 未設定の場合はモデル高さの30%（底面から）を自動推定。
    # ※タイヤ半径で推定するとスケール後に半径>>モデル高さになる場合があるため高さ比率を使用。
    bbox_corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    min_y = min(v.y for v in bbox_corners)
    max_y = max(v.y for v in bbox_corners)
    auto_y = min_y + (max_y - min_y) * 0.30

    raw_front_cy = wheels.get("front_cy")
    raw_rear_cy  = wheels.get("rear_cy")
    front_cy = raw_front_cy if raw_front_cy is not None else auto_y
    rear_cy  = raw_rear_cy  if raw_rear_cy  is not None else auto_y

    # 車体のZ中心・幅をBBoxから計算
    min_z = min(v.z for v in bbox_corners)
    max_z = max(v.z for v in bbox_corners)
    car_z_center = (min_z + max_z) / 2.0
    car_z_extent = max_z - min_z

    # シリンダーのZ深さ: 車体の全幅×2 で確実にカットスルー（どこに置いても貫通）
    cyl_depth = car_z_extent * 2.0

    # Y Offset が車幅の30%未満ならタイヤ位置として不合理 → 自動補正
    # （タイヤは通常 Z中心から 35〜50% 程度の位置にある）
    min_reasonable = car_z_extent * 0.35
    if offset_z < min_reasonable:
        log(f"Y Offset {offset_z:.1f}mm が小さすぎるため自動補正: "
            f"{min_reasonable:.1f}mm (car_z_extent={car_z_extent:.1f}mm の 35%)")
        offset_z = min_reasonable

    log(f"Car Z: center={car_z_center:.1f}mm  extent={car_z_extent:.1f}mm")
    log(f"Tire Z positions: +{(car_z_center+offset_z):.1f}mm / {(car_z_center-offset_z):.1f}mm")
    log(f"Tire axle Y: front={front_cy:.1f}mm  rear={rear_cy:.1f}mm  (auto={auto_y:.1f}mm)")
    log(f"Cylinder depth (Z): {cyl_depth:.1f}mm")

    # シリンダーはZ軸方向（左右）に置く。
    # Z位置 = 車体Z中心 ± offset_z（モデル中心基準の相対オフセット）
    tire_configs = [
        # (x, cy, z, radius)
        (front_x, front_cy,  car_z_center + offset_z, front_r),   # 前右
        (front_x, front_cy,  car_z_center - offset_z, front_r),   # 前左
        (rear_x,  rear_cy,   car_z_center + offset_z, rear_r),    # 後右
        (rear_x,  rear_cy,   car_z_center - offset_z, rear_r),    # 後左
    ]

    for x, cy, z, r in tire_configs:
        log(f"  Cylinder at X={x:.1f} Y={cy:.1f} Z={z:.1f}  r={r:.1f}mm")
        cyl = _make_cylinder(location=(x, cy, z), radius_m=r, height_m=cyl_depth,
                             rotation_euler=None)
        try:
            _boolean_subtract(obj, cyl)
        except Exception as e:
            log(f"Warning: Tire boolean failed at x={x*1000:.1f} cy={cy*1000:.1f} z={z*1000:.1f}: {e}")


def _cut_bottom(obj, cut_y: float):
    """
    Y < cut_y の部分を大きなボックスでブーリアン差分してカット。
    座標値はmm単位（vispy Y = Blender Y値、単位変換不要）。
    cut_y == 0 の場合はバウンディングボックス最小Y付近を自動推定。
    """
    bbox = [obj.matrix_world @ v.co for v in obj.data.vertices]
    min_y = min(v.y for v in bbox)
    max_y = max(v.y for v in bbox)
    size_xz = max(
        max(v.x for v in bbox) - min(v.x for v in bbox),
        max(v.z for v in bbox) - min(v.z for v in bbox),
    ) * 3.0

    if cut_y == 0:
        # 自動: モデル高さの下10%をカット
        cut_y = min_y + (max_y - min_y) * 0.1

    box_height = (cut_y - min_y) + 1.0  # カット平面からmin_yまでの高さ + 余裕
    if box_height <= 0:
        log("Warning: cut_z is below model bottom. Skipping bottom cut.")
        return

    box_center_y = min_y + box_height / 2.0 - 0.001

    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(0, box_center_y, 0),
    )
    box = bpy.context.object
    box.scale = (size_xz, box_height, size_xz)
    bpy.ops.object.select_all(action='DESELECT')
    box.select_set(True)
    bpy.context.view_layer.objects.active = box
    bpy.ops.object.transform_apply(scale=True)

    try:
        _boolean_subtract(obj, box)
    except Exception as e:
        log(f"Warning: Bottom cut boolean failed: {e}")


def _separate_and_list_loose_parts(obj, preview_dir: str, is_blender4: bool) -> list:
    """
    Loose parts を分離し、体積情報のリストを返す。
    最大体積オブジェクトを main body として残す。
    各非メインパーツを preview/parts/ に STL として書き出す。
    """
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.separate(type='LOOSE')
    bpy.ops.object.mode_set(mode='OBJECT')

    parts = [o for o in bpy.context.scene.objects if o.type == 'MESH']

    # parts_dir の準備と古い STL のクリア
    parts_dir = os.path.join(preview_dir, "parts")
    os.makedirs(parts_dir, exist_ok=True)
    if os.path.isdir(parts_dir):
        for _f in os.listdir(parts_dir):
            if _f.endswith(".stl"):
                try:
                    os.remove(os.path.join(parts_dir, _f))
                except Exception:
                    pass

    # 体積を計算（Blenderはメートル³で返る）
    parts_with_vol = []
    for part in parts:
        bm = bmesh.new()
        bm.from_mesh(part.data)
        # STLはmm値のままインポートされるため、calc_volume()の戻り値は数値的にmm³
        vol_mm3 = abs(bm.calc_volume())
        bm.free()
        parts_with_vol.append((part, vol_mm3))

    # 体積で昇順ソート → 最後のエントリ（最大体積）がメインボディ
    parts_with_vol = sorted(parts_with_vol, key=lambda x: x[1])

    parts_info = []
    loose_idx = 0
    for i, (part, vol_mm3) in enumerate(parts_with_vol):
        is_main = (i == len(parts_with_vol) - 1)
        stl_file = None
        if not is_main:
            stl_path = os.path.join(parts_dir, f"part_{loose_idx}.stl")
            try:
                _export_object_stl(part, stl_path, is_blender4)
                stl_file = stl_path
            except Exception as _e:
                log(f"Warning: failed to export part STL: {_e}")
            loose_idx += 1
        parts_info.append({
            "name": part.name,
            "volume_mm3": round(vol_mm3, 2),
            "is_main": is_main,
            "stl_file": stl_file,
        })

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


def _export_object_stl(obj, filepath: str, is_blender4: bool):
    """指定オブジェクトを STL として出力する（_export_main_stl の汎用版）"""
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    if is_blender4:
        try:
            bpy.ops.wm.stl_export(
                filepath=filepath,
                export_selected_objects=True,
                global_scale=1.0,
            )
            return
        except Exception:
            pass

    # Blender 3.x / fallback
    try:
        bpy.ops.export_mesh.stl(
            filepath=filepath,
            use_selection=True,
            global_scale=1.0,
        )
    except Exception as e:
        log(f"Warning: STL export for {obj.name} failed: {e}")


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
                global_scale=1.0,  # STLはmm値のまま → 変換不要
            )
            return
        except Exception:
            pass

    # Blender 3.x / fallback
    try:
        bpy.ops.export_mesh.stl(
            filepath=filepath,
            use_selection=True,
            global_scale=1.0,
        )
    except Exception as e:
        print(f"ERROR: STL export failed: {e}", file=sys.stderr)
        sys.exit(1)


# ------------------------------------------------------------------ #
#  エントリポイント
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    main()
