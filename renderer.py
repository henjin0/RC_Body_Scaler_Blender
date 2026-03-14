"""
RC Car Body Creator - 3D Renderer (vispy / OpenGL)
Provides mesh display with solid / transparent / wireframe modes,
tire-cylinder helpers, cut-plane preview and 3D surface picking.
"""

import numpy as np

# ── vispy backend negotiation ─────────────────────────────────────────────
HAS_VISPY  = False
_BACKEND   = ""

try:
    import vispy as _vispy

    # Prefer PySide6 (requires QApplication to exist before import).
    for _b in ("pyside6", "pyqt6", "pyqt5", "pyside2", "tkinter"):
        try:
            _vispy.use(_b)
            from vispy import scene as _vs
            from vispy.scene.visuals import (
                Mesh as _VMesh, XYZAxis as _VAxis,
                Line as _VLine, Text as _VText,
            )
            from vispy.geometry import MeshData as _VMeshData
            HAS_VISPY = True
            _BACKEND  = _b
            break
        except Exception:
            continue
except ImportError:
    pass

try:
    import trimesh as _tm
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False


# ── tiny helpers ──────────────────────────────────────────────────────────

def _hex_rgba(h: str, a: float = 1.0) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)) + (a,)


def _rotation_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    """Build a 3×3 rotation matrix from Euler angles (degrees), XYZ order."""
    rx = np.radians(rx_deg)
    ry = np.radians(ry_deg)
    rz = np.radians(rz_deg)

    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)

    Rx = np.array([[1,  0,   0 ],
                   [0,  cx, -sx],
                   [0,  sx,  cx]], dtype=np.float64)
    Ry = np.array([[ cy, 0, sy],
                   [  0, 1,  0],
                   [-sy, 0, cy]], dtype=np.float64)
    Rz = np.array([[cz, -sz, 0],
                   [sz,  cz, 0],
                   [ 0,   0, 1]], dtype=np.float64)

    return Rz @ Ry @ Rx


def _cylinder_mesh(cx: float, cy: float, cz: float,
                   radius: float, half_h: float, n: int = 28):
    """Closed cylinder (side + caps) aligned to the Y axis."""
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    bot_ring = np.c_[cx + radius * np.cos(t),
                     np.full(n, cy - half_h),
                     cz + radius * np.sin(t)].astype(np.float32)
    top_ring = np.c_[cx + radius * np.cos(t),
                     np.full(n, cy + half_h),
                     cz + radius * np.sin(t)].astype(np.float32)
    bot_ctr  = np.array([[cx, cy - half_h, cz]], dtype=np.float32)
    top_ctr  = np.array([[cx, cy + half_h, cz]], dtype=np.float32)
    # indices: 0..n-1 = bot ring, n..2n-1 = top ring, 2n = bot center, 2n+1 = top center
    verts = np.vstack([bot_ring, top_ring, bot_ctr, top_ctr])
    bi, ti, bc, tc = 0, n, 2 * n, 2 * n + 1
    side = np.array([[bi + i, bi + (i + 1) % n, ti + i,
                      bi + (i + 1) % n, ti + (i + 1) % n, ti + i]
                     for i in range(n)], dtype=np.int32).reshape(-1, 3)
    cap_b = np.array([[bc, bi + (i + 1) % n, bi + i] for i in range(n)], dtype=np.int32)
    cap_t = np.array([[tc, ti + i, ti + (i + 1) % n] for i in range(n)], dtype=np.int32)
    faces = np.vstack([side, cap_b, cap_t])
    return verts, faces


def _cylinder_mesh_z(cx: float, cy: float, cz: float,
                     radius: float, half_h: float, n: int = 28):
    """Closed cylinder (side + caps) aligned to the Z axis (wheel axle direction).
    In vispy: X=front-back, Y=up-down, Z=left-right.
    The cylinder cross-section (circle) faces the side view (XY plane).
    """
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    left_ring  = np.c_[cx + radius * np.cos(t),
                       cy + radius * np.sin(t),
                       np.full(n, cz - half_h)].astype(np.float32)
    right_ring = np.c_[cx + radius * np.cos(t),
                       cy + radius * np.sin(t),
                       np.full(n, cz + half_h)].astype(np.float32)
    left_ctr   = np.array([[cx, cy, cz - half_h]], dtype=np.float32)
    right_ctr  = np.array([[cx, cy, cz + half_h]], dtype=np.float32)
    verts = np.vstack([left_ring, right_ring, left_ctr, right_ctr])
    bi, ti, bc, tc = 0, n, 2 * n, 2 * n + 1
    side = np.array([[bi + i, bi + (i + 1) % n, ti + i,
                      bi + (i + 1) % n, ti + (i + 1) % n, ti + i]
                     for i in range(n)], dtype=np.int32).reshape(-1, 3)
    cap_b = np.array([[bc, bi + (i + 1) % n, bi + i] for i in range(n)], dtype=np.int32)
    cap_t = np.array([[tc, ti + i, ti + (i + 1) % n] for i in range(n)], dtype=np.int32)
    faces = np.vstack([side, cap_b, cap_t])
    return verts, faces


# ── main renderer class ───────────────────────────────────────────────────

class Renderer3D:
    """
    OpenGL mesh renderer using vispy.
    Call `.widget` to get the native Qt widget to embed.
    """

    MODES = ("solid", "transparent", "wireframe")

    def __init__(self, bgcolor: str = "#070a0d"):
        self._mesh_vis: object = None
        self._result_mesh_vis: object = None
        self._result_verts: np.ndarray | None = None
        self._result_faces: np.ndarray | None = None
        self._has_result: bool = False
        self._helpers: list      = []
        self._orient_vis: list   = []          # direction arrows / labels
        self._orig_verts: np.ndarray | None = None   # pre-rotation vertices
        self._verts: np.ndarray | None = None
        self._faces: np.ndarray | None = None
        self._trimesh = None
        self._mode: str = "solid"

        self.pick_callback      = None   # fn(x_mm, y_mm, z_mm)
        self.pick_miss_callback = None   # fn() called when click misses mesh
        self._pick_active       = False

        if not HAS_VISPY:
            self.canvas = None
            return

        self.canvas = _vs.SceneCanvas(
            keys="interactive", bgcolor=bgcolor, show=False
        )
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = _vs.cameras.TurntableCamera(
            fov=45, distance=500, elevation=18, azimuth=25, up="+y"
        )

        # Axis gizmo
        self._axis = _VAxis(parent=self.view.scene)

        self.canvas.events.mouse_press.connect(self._on_mouse)

    # ── public API ────────────────────────────────────────────────────────

    @property
    def widget(self):
        """Native widget to embed in the host GUI."""
        return self.canvas.native if self.canvas else None

    @property
    def available(self) -> bool:
        return HAS_VISPY and self.canvas is not None

    def set_bgcolor(self, color: str):
        if self.canvas:
            self.canvas.bgcolor = color

    # ── view presets & projection ──────────────────────────────────────────

    _VIEW_PRESETS = {
        # (elevation, azimuth, fov)
        # vispy TurntableCamera: azimuth=0 → camera at -X, azimuth=90 → camera at +Z
        # azimuth=180 → camera at +X (looking at car nose if nose faces +X)
        # +Z direction: car side profile (X-Y plane, X=horizontal)
        "iso":   (18.0, 135.0, 45.0),  # default perspective (front-right-above)
        "top":   (89.5, 180.0,  0.0),  # top-down orthographic
        "front": ( 0.0, 180.0,  0.0),  # az=180 → camera at +X → sees car nose (front face)
        "side":  ( 0.0,  90.0,  0.0),  # az=90  → camera at +Z → sees X-Y plane (side profile)
    }

    def _set_ortho_scale(self, cam):
        """Set scale_factor so the loaded model fills ~70 % of the ortho viewport."""
        if self._verts is not None:
            ext = self._verts.max(axis=0) - self._verts.min(axis=0)
            cam.scale_factor = float(ext.max()) * 1.5
        else:
            cam.scale_factor = float(cam.distance) * 1.0

    def set_view_preset(self, preset: str):
        if not self.canvas or preset not in self._VIEW_PRESETS:
            return
        el, az, fov = self._VIEW_PRESETS[preset]
        cam = self.view.camera
        cam.elevation = el
        cam.azimuth   = az
        if fov == 0:
            self._set_ortho_scale(cam)   # must come BEFORE setting fov=0
        cam.fov = fov

    def toggle_projection(self):
        if not self.canvas:
            return
        cam = self.view.camera
        if float(cam.fov) > 0:
            self._set_ortho_scale(cam)
            cam.fov = 0.0
        else:
            cam.fov = 45.0

    @property
    def is_ortho(self) -> bool:
        return self.canvas is not None and float(self.view.camera.fov) <= 0

    # ── mesh loading ──────────────────────────────────────────────────────

    def load(self, filepath: str) -> dict:
        """Load mesh from file.  Returns size info dict."""
        if not HAS_TRIMESH:
            return {}
        try:
            m = _tm.load(filepath, force="mesh")
        except Exception as e:
            print(f"[Renderer] load error: {e}")
            return {}

        v = np.array(m.vertices, dtype=np.float32)
        f = np.array(m.faces,    dtype=np.int32)

        if len(v) == 0:
            print(f"[Renderer] load error: mesh has no vertices: {filepath}")
            return {}

        # Unit detection: if max extent < 10 assume meters → convert to mm
        ext = v.max(axis=0) - v.min(axis=0)
        if float(ext.max()) < 10.0:
            v   *= 1000.0
            ext *= 1000.0

        self._orig_verts = v.copy()
        self._verts      = v
        self._faces      = f
        self._trimesh    = _tm.Trimesh(v.copy(), f.copy(), process=False)

        # Aim camera at model
        if self.canvas:
            c = v.mean(axis=0)
            d = float(ext.max())
            self.view.camera.center      = tuple(c)
            self.view.camera.distance    = d * 2.2
            self.view.camera.scale_factor = max(d * 100.0, 100000.0)  # near~1mm, far effectively infinite

        # Clear any previous result overlay
        self._has_result = False
        self._result_verts = None
        self._result_faces = None

        self._refresh_mesh()
        self._clear_helpers()
        self._update_orient_vis()

        return {
            "X_mm": float(ext[0]),
            "Y_mm": float(ext[1]),
            "Z_mm": float(ext[2]),
            "faces": len(f),
            "verts": len(v),
        }

    def load_result(self, filepath: str) -> dict:
        """Load Blender result STL as a teal overlay alongside the original model."""
        if not HAS_TRIMESH:
            return {}
        try:
            m = _tm.load(filepath, force="mesh")
        except Exception as e:
            print(f"[Renderer] load_result error: {e}")
            return {}

        v = np.array(m.vertices, dtype=np.float32)
        f = np.array(m.faces,    dtype=np.int32)

        if len(v) == 0:
            print(f"[Renderer] load_result: mesh has no vertices: {filepath}")
            return {}

        ext = v.max(axis=0) - v.min(axis=0)
        if float(ext.max()) < 10.0:
            v   *= 1000.0
            ext *= 1000.0

        self._result_verts = v
        self._result_faces = f
        self._has_result   = True

        self._refresh_mesh()
        return {
            "X_mm": float(ext[0]),
            "Y_mm": float(ext[1]),
            "Z_mm": float(ext[2]),
            "faces": len(f),
            "verts": len(v),
        }

    def clear_result(self):
        """Remove the result overlay and return to normal single-model display."""
        self._has_result   = False
        self._result_verts = None
        self._result_faces = None
        self._refresh_mesh()

    def hide_for_processing(self):
        """処理開始時に全メッシュを非表示にする。
        _has_result=True かつ _result_verts=None にすることで
        元モデルも結果モデルも描画されない状態にする。
        """
        self._has_result   = True
        self._result_verts = None
        self._result_faces = None
        self._refresh_mesh()

    # ── rotation ──────────────────────────────────────────────────────────

    def apply_rotation(self, rx_deg: float, ry_deg: float, rz_deg: float):
        """Rotate the mesh in place (applied to original loaded vertices)."""
        if self._orig_verts is None:
            return

        R   = _rotation_matrix(rx_deg, ry_deg, rz_deg)
        v   = (R @ self._orig_verts.T).T.astype(np.float32)
        f   = self._faces

        self._verts   = v
        self._trimesh = _tm.Trimesh(v.copy(), f.copy(), process=False)

        # Re-aim camera
        if self.canvas:
            ext = v.max(axis=0) - v.min(axis=0)
            c   = v.mean(axis=0)
            d   = float(ext.max())
            self.view.camera.center       = tuple(c)
            self.view.camera.distance     = d * 2.2
            self.view.camera.scale_factor = max(d * 100.0, 100000.0)  # near~1mm, far effectively infinite

        self._refresh_mesh()
        self._clear_helpers()
        self._update_orient_vis()

    # ── render mode ───────────────────────────────────────────────────────

    def set_mode(self, mode: str):
        if mode in self.MODES:
            self._mode = mode
            self._refresh_mesh()

    def _refresh_mesh(self):
        if not self.canvas:
            return
        if self._mesh_vis is not None:
            self._mesh_vis.parent = None
            self._mesh_vis = None
        if self._result_mesh_vis is not None:
            self._result_mesh_vis.parent = None
            self._result_mesh_vis = None
        if self._verts is None:
            return

        v, f  = self._verts, self._faces
        md    = _VMeshData(vertices=v, faces=f)
        scene = self.view.scene

        if self._has_result and self._result_verts is not None:
            # 結果モデルのみ表示（元モデルは非表示）
            rmd  = _VMeshData(vertices=self._result_verts, faces=self._result_faces)
            rvis = _VMesh(meshdata=rmd, color=(0.0, 0.88, 0.72, 0.95),
                          shading="smooth", parent=scene)
            rvis.set_gl_state("opaque", depth_test=True, cull_face=False)
            self._result_mesh_vis = rvis

        elif self._mode == "wireframe":
            vis = _VMesh(meshdata=md, color=(0.0, 0.9, 1.0, 0.85),
                         mode="lines", parent=scene)
            self._mesh_vis = vis

        elif self._mode == "transparent":
            vis = _VMesh(meshdata=md, color=(0.47, 0.56, 0.61, 0.30),
                         shading="smooth", parent=scene)
            vis.set_gl_state("translucent", depth_test=True, cull_face=False)
            self._mesh_vis = vis

        else:  # solid
            vis = _VMesh(meshdata=md, color=(0.47, 0.56, 0.61, 1.0),
                         shading="smooth", parent=scene)
            self._mesh_vis = vis

        # 描画を強制更新
        self.canvas.update()

    # ── helpers (tires + cut plane) ───────────────────────────────────────

    def update_viz(
        self,
        front_x: float, rear_x: float, offset_y: float,
        cut_z: float,
        front_cut_r: float | None = None, rear_cut_r: float | None = None,
        thru_front_r: float | None = None, thru_rear_r: float | None = None,
        front_cy: float | None = None, rear_cy: float | None = None,
        cut_z_result: float | None = None,
        # スケール後の座標（結果モデル表示時に貫通カット円柱の位置に使用）
        sc_front_x: float | None = None, sc_rear_x: float | None = None,
        sc_offset_y: float | None = None,
        sc_front_cy: float | None = None, sc_rear_cy: float | None = None,
    ):
        self._clear_helpers()
        if not self.canvas or self._verts is None:
            return

        v = self._verts
        # 結果モデル表示中は result_verts を空間参照に使う
        ref_v = (self._result_verts
                 if (self._has_result and self._result_verts is not None) else v)

        model_y_ctr  = float((ref_v[:, 1].max() + ref_v[:, 1].min()) / 2.0)
        model_z_ctr  = float(ref_v[:, 2].mean())
        model_z_half = float(ref_v[:, 2].max() - ref_v[:, 2].min()) / 2.0 * 1.05

        # 結果モデル表示中はスケール後座標を使用（提供されていれば）
        result_shown = self._has_result and self._result_verts is not None
        if result_shown and sc_front_x is not None:
            disp_front_x = sc_front_x
            disp_rear_x  = sc_rear_x  if sc_rear_x  is not None else rear_x
            disp_offset_y = sc_offset_y if sc_offset_y is not None else offset_y
        else:
            disp_front_x  = front_x
            disp_rear_x   = rear_x
            disp_offset_y = offset_y

        cy_front = (sc_front_cy if (result_shown and sc_front_cy is not None)
                    else (front_cy if front_cy is not None else model_y_ctr))
        cy_rear  = (sc_rear_cy  if (result_shown and sc_rear_cy  is not None)
                    else (rear_cy  if rear_cy  is not None else model_y_ctr))

        # ── シリンダー表示 ────────────────────────────────────────────────
        # 結果モデル表示中: カット径（黄）は非表示、貫通カット径（緑）のみ表示
        # 通常時: カット径（黄）＋貫通カット径（緑）
        axle_specs = [
            (disp_front_x, front_cut_r, thru_front_r, cy_front, "#00e5ff", "FRONT"),
            (disp_rear_x,  rear_cut_r,  thru_rear_r,  cy_rear,  "#ff6b35", "REAR"),
        ]
        for x, cut_r, thru_r, cy, col, tag in axle_specs:
            # カット径（黄色）— 結果表示中は非表示
            if cut_r is not None and not result_shown:
                vvc, ffc = _cylinder_mesh_z(x, cy, model_z_ctr, cut_r, model_z_half)
                visc = _VMesh(
                    vertices=vvc, faces=ffc,
                    color=(1.0, 0.85, 0.0, 0.28),
                    parent=self.view.scene,
                )
                visc.set_gl_state("translucent", depth_test=True, cull_face=False)
                self._helpers.append(visc)

            # 貫通カット径（緑）— 0より大きい場合のみ
            if thru_r is not None and thru_r > 0:
                vva, ffa = _cylinder_mesh_z(x, cy, model_z_ctr, thru_r, model_z_half)
                visa = _VMesh(
                    vertices=vva, faces=ffa,
                    color=(0.2, 1.0, 0.45, 0.28),
                    parent=self.view.scene,
                )
                visa.set_gl_state("translucent", depth_test=True, cull_face=False)
                self._helpers.append(visa)

            # ラベル
            try:
                lbl_r   = thru_r if (thru_r is not None and thru_r > 0) else (
                          cut_r  if cut_r  is not None else 26.0)
                lbl_pos = np.array([x, cy + lbl_r + 10, model_z_ctr], dtype=np.float32)
                lbl_txt = tag
                if cut_r is not None and not result_shown:
                    lbl_txt += f"  Cut:{cut_r*2:.0f}mm"
                if thru_r is not None and thru_r > 0:
                    lbl_txt += f"  貫通:{thru_r*2:.0f}mm"
                txt = _VText(
                    lbl_txt, pos=lbl_pos,
                    color=_hex_rgba(col, 1.0),
                    font_size=9, bold=True,
                    parent=self.view.scene,
                )
                self._helpers.append(txt)
            except Exception:
                pass

        # ホイールベースライン
        try:
            wb_line = _VLine(
                pos=np.array([[disp_front_x, cy_front, model_z_ctr],
                              [disp_rear_x,  cy_rear,  model_z_ctr]],
                             dtype=np.float32),
                color=(1.0, 1.0, 1.0, 0.7), width=2,
                parent=self.view.scene,
            )
            self._helpers.append(wb_line)

            mid_x  = (disp_front_x + disp_rear_x) / 2.0
            mid_cy = (cy_front + cy_rear) / 2.0
            wb_mm  = abs(disp_front_x - disp_rear_x)
            max_r  = max(
                front_cut_r if front_cut_r is not None else 26.0,
                rear_cut_r  if rear_cut_r  is not None else 26.0,
            )
            wb_lbl = _VText(
                f"WB {wb_mm:.0f}mm",
                pos=np.array([mid_x, mid_cy + max_r + 10, model_z_ctr], dtype=np.float32),
                color=(1.0, 1.0, 1.0, 0.9), font_size=9, bold=True,
                parent=self.view.scene,
            )
            self._helpers.append(wb_lbl)

            if not result_shown:
                for side_z in (model_z_ctr + disp_offset_y, model_z_ctr - disp_offset_y):
                    track_line = _VLine(
                        pos=np.array([[disp_front_x, cy_front, side_z],
                                      [disp_rear_x,  cy_rear,  side_z]], dtype=np.float32),
                        color=(0.6, 0.6, 0.6, 0.4), width=1,
                        parent=self.view.scene,
                    )
                    self._helpers.append(track_line)
        except Exception:
            pass

        # ── カットツールボディの可視化 ──────────────────────────────────────
        # 結果表示中: result_vertsのバウンディングボックスを使い、cut_z_resultを優先
        # 通常時:    元モデルのバウンディングボックスとcut_zを使用
        if self._has_result and self._result_verts is not None:
            vb = self._result_verts
            eff_cut_z = cut_z_result  # Noneの場合は表示しない
        else:
            vb = v
            eff_cut_z = cut_z

        if eff_cut_z is not None:
            min_y_b = float(vb[:, 1].min())
            ex_b = float(vb[:, 0].max() - vb[:, 0].min()) * 0.56
            ez_b = float(vb[:, 2].max() - vb[:, 2].min()) * 0.56
            cx_b  = float(vb[:, 0].mean())
            cz_b  = float(vb[:, 2].mean())

            if eff_cut_z > min_y_b + 0.5:
                # 除去されるゾーン: min_y_b から eff_cut_z までの半透明ボックス
                pad = max(abs(min_y_b) * 0.05, 5.0)
                bv = np.array([
                    [cx_b - ex_b, min_y_b - pad, cz_b - ez_b],
                    [cx_b + ex_b, min_y_b - pad, cz_b - ez_b],
                    [cx_b + ex_b, min_y_b - pad, cz_b + ez_b],
                    [cx_b - ex_b, min_y_b - pad, cz_b + ez_b],
                    [cx_b - ex_b, eff_cut_z,     cz_b - ez_b],
                    [cx_b + ex_b, eff_cut_z,     cz_b - ez_b],
                    [cx_b + ex_b, eff_cut_z,     cz_b + ez_b],
                    [cx_b - ex_b, eff_cut_z,     cz_b + ez_b],
                ], dtype=np.float32)
                bf = np.array([
                    [0,2,1],[0,3,2],  # 底面
                    [4,5,6],[4,6,7],  # 上面 (カット平面)
                    [0,1,5],[0,5,4],  # 前面
                    [3,7,6],[3,6,2],  # 後面
                    [1,2,6],[1,6,5],  # 右面
                    [0,4,7],[0,7,3],  # 左面
                ], dtype=np.int32)
                cut_body = _VMesh(
                    vertices=bv, faces=bf,
                    color=(1.0, 0.28, 0.05, 0.32),
                    parent=self.view.scene,
                )
                cut_body.set_gl_state("translucent", depth_test=False)
                self._helpers.append(cut_body)

                # カット平面の輪郭ライン（明るいオレンジ）
                outline = np.array([
                    [cx_b - ex_b, eff_cut_z, cz_b - ez_b],
                    [cx_b + ex_b, eff_cut_z, cz_b - ez_b],
                    [cx_b + ex_b, eff_cut_z, cz_b + ez_b],
                    [cx_b - ex_b, eff_cut_z, cz_b + ez_b],
                    [cx_b - ex_b, eff_cut_z, cz_b - ez_b],
                ], dtype=np.float32)
                cut_outline = _VLine(
                    pos=outline, color=(1.0, 0.55, 0.0, 1.0), width=2,
                    parent=self.view.scene,
                )
                self._helpers.append(cut_outline)

                # ラベル
                try:
                    lbl_pos = np.array(
                        [cx_b, eff_cut_z + abs(eff_cut_z - min_y_b) * 0.1 + 5, cz_b + ez_b],
                        dtype=np.float32,
                    )
                    cut_lbl = _VText(
                        f"CUT Z  {eff_cut_z:.1f}mm",
                        pos=lbl_pos,
                        color=(1.0, 0.65, 0.0, 1.0),
                        font_size=9, bold=True,
                        parent=self.view.scene,
                    )
                    self._helpers.append(cut_lbl)
                except Exception:
                    pass
            else:
                # カットゾーンがほぼゼロ → 警告色の平面のみ
                pv = np.array([
                    [cx_b - ex_b, eff_cut_z, cz_b - ez_b],
                    [cx_b + ex_b, eff_cut_z, cz_b - ez_b],
                    [cx_b + ex_b, eff_cut_z, cz_b + ez_b],
                    [cx_b - ex_b, eff_cut_z, cz_b + ez_b],
                ], dtype=np.float32)
                pf = np.array([[0,1,2],[0,2,3]], dtype=np.int32)
                plane = _VMesh(
                    vertices=pv, faces=pf,
                    color=(1.0, 0.0, 0.0, 0.50),
                    parent=self.view.scene,
                )
                plane.set_gl_state("translucent", depth_test=False)
                self._helpers.append(plane)
                try:
                    warn_pos = np.array([cx_b, eff_cut_z + 5, cz_b + ez_b], dtype=np.float32)
                    warn_lbl = _VText(
                        "⚠ CUT Z が底面以下 — カット不可",
                        pos=warn_pos,
                        color=(1.0, 0.0, 0.0, 1.0),
                        font_size=9, bold=True,
                        parent=self.view.scene,
                    )
                    self._helpers.append(warn_lbl)
                except Exception:
                    pass

    def _clear_helpers(self):
        for h in self._helpers:
            h.parent = None
        self._helpers.clear()

    # ── direction indicators ───────────────────────────────────────────────

    def _clear_orient(self):
        for v in self._orient_vis:
            v.parent = None
        self._orient_vis.clear()

    def _update_orient_vis(self):
        """
        Draw FRONT / UP / BOTTOM arrows starting from the model bounding box
        faces, pointing outward.  Arrows are always visible regardless of camera angle.
        """
        self._clear_orient()
        if not self.canvas or self._verts is None or not HAS_VISPY:
            return

        v      = self._verts
        mn     = v.min(axis=0).astype(np.float64)
        mx     = v.max(axis=0).astype(np.float64)
        ctr    = ((mn + mx) / 2.0)
        ext    = mx - mn
        arrow  = float(ext.max()) * 0.30   # arrow length ≈ 30 % of bounding box
        scene  = self.view.scene

        # Each entry: (shaft_start, axis_dir, rgba)
        # Arrows originate from the corresponding bounding-box face centre.
        indicators = [
            # FRONT: starts at +X face, points further in +X
            (np.array([mx[0], ctr[1], ctr[2]]),
             np.array([1.0, 0.0, 0.0]),
             (0.00, 0.90, 1.00, 1.0)),
            # UP: starts at +Y face, points further in +Y
            (np.array([ctr[0], mx[1], ctr[2]]),
             np.array([0.0, 1.0, 0.0]),
             (0.24, 0.83, 0.33, 1.0)),
            # BOTTOM: starts at -Y face, points further in -Y
            (np.array([ctr[0], mn[1], ctr[2]]),
             np.array([0.0, -1.0, 0.0]),
             (1.00, 0.42, 0.21, 1.0)),
        ]

        for org_pt, axis_dir, rgba in indicators:
            tip     = (org_pt + axis_dir * arrow).astype(np.float32)
            org_f32 = org_pt.astype(np.float32)

            # Shaft line
            line = _VLine(
                pos=np.array([org_f32, tip], dtype=np.float32),
                color=rgba, width=3, parent=scene,
            )
            self._orient_vis.append(line)

            # Arrowhead cone
            cone_len = arrow * 0.22
            cone_r   = arrow * 0.065
            base_pt  = tip - (axis_dir * cone_len).astype(np.float32)
            n        = 14
            t        = np.linspace(0, 2 * np.pi, n, endpoint=False)

            if abs(axis_dir[0]) < 0.9:
                perp = np.cross(axis_dir, [1.0, 0.0, 0.0])
            else:
                perp = np.cross(axis_dir, [0.0, 1.0, 0.0])
            perp  /= np.linalg.norm(perp)
            perp2  = np.cross(axis_dir, perp)

            ring = np.array(
                [base_pt + cone_r * (np.cos(ti) * perp + np.sin(ti) * perp2)
                 for ti in t],
                dtype=np.float32,
            )
            cone_verts = np.vstack([ring, [tip]])
            cone_faces = np.array(
                [[i, (i + 1) % n, n] for i in range(n)], dtype=np.int32
            )
            cone_mesh = _VMesh(
                vertices=cone_verts, faces=cone_faces,
                color=rgba, parent=scene,
            )
            self._orient_vis.append(cone_mesh)

    # ── 3D surface picking ────────────────────────────────────────────────

    def start_pick(self, callback, miss_callback=None):
        """
        Activate pick mode.
        callback(x, y, z)   — called on a successful mesh hit.
        miss_callback()      — called when the click misses the mesh (pick stays active).
        """
        self.pick_callback      = callback
        self.pick_miss_callback = miss_callback
        self._pick_active       = True

    def _on_mouse(self, event):
        if not self._pick_active or event.button != 1:
            return
        if self._trimesh is None:
            return
        try:
            origin, direction = self._screen_to_ray(event.pos)
            if origin is None or direction is None:
                return
            locs, _, _ = self._trimesh.ray.intersects_location(
                [origin], [direction]
            )
            if len(locs) > 0:
                # Hit — deactivate pick and report
                self._pick_active = False
                dists   = np.linalg.norm(locs - origin, axis=1)
                closest = locs[dists.argmin()]
                if self.pick_callback:
                    self.pick_callback(
                        float(closest[0]),
                        float(closest[1]),
                        float(closest[2]),
                    )
            else:
                # Miss — keep pick active so user can retry
                if self.pick_miss_callback:
                    self.pick_miss_callback()
        except Exception as e:
            print(f"[Renderer] pick error: {e}")

    def _screen_to_ray(self, pos):
        """
        Convert 2-D canvas position to a 3-D ray (origin, unit_direction).
        Handles both perspective (fov > 0) and orthographic (fov == 0) cameras.
        """
        try:
            cam  = self.view.camera
            w, h = float(self.canvas.size[0]), float(self.canvas.size[1])

            # ── Camera orientation ────────────────────────────────────────
            az   = np.radians(cam.azimuth)
            el   = np.radians(cam.elevation)
            dist = float(cam.distance)
            ctr  = np.array(cam.center, dtype=np.float64)

            # Unit vector from center toward camera eye.
            # vispy TurntableCamera: az=0 → camera at -X, az=90 → camera at +Z, az=180 → camera at +X
            cam_offset = np.array([
                -np.cos(el) * np.cos(az),
                 np.sin(el),
                 np.cos(el) * np.sin(az),
            ], dtype=np.float64)

            # ── Camera frame (right / true_up) ────────────────────────────
            forward  = -cam_offset          # points toward center
            world_up = np.array([0.0, 1.0, 0.0])
            right    = np.cross(forward, world_up)
            norm_r   = np.linalg.norm(right)
            if norm_r < 1e-6:              # camera near top/bottom pole
                world_up = np.array([0.0, 0.0, 1.0])
                right    = np.cross(forward, world_up)
                norm_r   = np.linalg.norm(right)
            right  /= norm_r
            true_up = np.cross(right, forward)

            # NDC: sx ∈ [-1,+1] left→right, sy ∈ [-1,+1] bottom→top
            sx = (pos[0] / w) * 2.0 - 1.0
            sy = 1.0 - (pos[1] / h) * 2.0

            fov = float(cam.fov)

            if fov > 0:
                # ── Perspective ───────────────────────────────────────────
                cam_pos   = ctr + dist * cam_offset
                half_h    = np.tan(np.radians(fov) / 2.0)
                half_w    = half_h * (w / h)
                direction = forward + sx * half_w * right + sy * half_h * true_up
                direction /= np.linalg.norm(direction)
                return cam_pos, direction

            else:
                # ── Orthographic ──────────────────────────────────────────
                # scale_factor = visible height in world units (set by _set_ortho_scale)
                try:
                    scale = float(cam.scale_factor)
                    if scale <= 0 or scale > 1e9:
                        raise ValueError
                except Exception:
                    # Fallback: derive from model extent
                    if self._verts is not None:
                        ext = self._verts.max(axis=0) - self._verts.min(axis=0)
                        scale = float(ext.max()) * 1.5
                    else:
                        scale = dist * 1.0

                half_h_w = scale / 2.0
                half_w_w = half_h_w * (w / h)
                # Origin on the image plane, pushed back along cam_offset
                # so rays start safely in front of all scene geometry.
                origin = (ctr
                          + sx * half_w_w * right
                          + sy * half_h_w * true_up
                          + cam_offset * dist * 3.0)
                direction = forward / np.linalg.norm(forward)
                return origin, direction

        except Exception as e:
            print(f"[Renderer] ray error: {e}")
            return None, None
