"""
RC Car Body Creator
PySide6 + vispy (OpenGL) desktop app.
Layout: header (48px) | 3D viewport (left) | sidebar 300px (right)
"""

import glob as _glob
import json
import os
import shutil
import subprocess
import sys
import threading

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QVBoxLayout, QWidget,
)

# ── QApplication must exist before vispy initializes ──────────────────────
_qapp = QApplication.instance() or QApplication(sys.argv)

# ── renderer (safe after QApplication) ────────────────────────────────────
try:
    from renderer import Renderer3D, HAS_VISPY, _BACKEND
except Exception as _e:
    print(f"[main] renderer import error: {_e}")
    HAS_VISPY = False
    _BACKEND  = ""
    class Renderer3D:                          # stub
        available = False
        widget    = None
        is_ortho  = False
        def load(self, *a, **kw): return {}
        def load_result(self, *a, **kw): return {}
        def clear_result(self, *a): pass
        def hide_for_processing(self): pass
        def set_mode(self, *a): pass
        def set_bgcolor(self, *a): pass
        def update_viz(self, *a, **kw): pass
        def apply_rotation(self, *a): pass
        def start_pick(self, *a): pass
        def set_view_preset(self, *a): pass
        def toggle_projection(self): pass

try:
    import trimesh as _trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False

# ── paths ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PARAMS_PATH = os.path.join(BASE_DIR, "blender_scripts", "params.json")
SCRIPT_PATH = os.path.join(BASE_DIR, "blender_scripts", "process_body.py")
PREVIEW_DIR = os.path.join(BASE_DIR, "preview")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

# ── themes ─────────────────────────────────────────────────────────────────
_DARK = {
    "bg":       "#0a0c0f", "panel":   "#111418", "border":  "#1e2530",
    "accent":   "#00e5ff", "accent2": "#ff6b35", "text":    "#c8d4e0",
    "dim":      "#4a5568", "success": "#39d353", "warning": "#f6c90e",
    "scene_bg": "#070a0d", "entry":   "#0d1117",
}
_LIGHT = {
    "bg":       "#f0ede8", "panel":   "#fafafa",  "border":  "#d4c9be",
    "accent":   "#0066cc", "accent2": "#cc4400",  "text":    "#1a1a2e",
    "dim":      "#888888", "success": "#2d8f3c",  "warning": "#d4a017",
    "scene_bg": "#e8e4de", "entry":   "#ffffff",
}
THEMES = {"dark": _DARK, "light": _LIGHT}
_CUR_THEME = "dark"


def _build_qss(t: dict) -> str:
    return f"""
    * {{ background-color: {t['bg']}; color: {t['text']};
         font-family: -apple-system, 'Helvetica Neue', 'Segoe UI', sans-serif; }}
    QPushButton {{
        background: {t['panel']}; border: 1px solid {t['border']};
        color: {t['text']}; padding: 6px 10px; border-radius: 4px;
        font-size: 13px;
    }}
    QPushButton:hover {{ background: {t['border']}; }}
    QPushButton:pressed {{ background: {t['border']}; border-color: {t['accent']}; }}
    QPushButton[role="accent"] {{
        background: transparent; border-color: {t['accent']}; color: {t['accent']};
    }}
    QPushButton[role="accent"]:hover {{ background: {t['accent']}22; }}
    QPushButton[role="accent2"] {{
        background: transparent; border-color: {t['accent2']}; color: {t['accent2']};
    }}
    QPushButton[role="accent2"]:hover {{ background: {t['accent2']}22; }}
    QPushButton[role="success"] {{
        background: {t['success']}22; border-color: {t['success']};
        color: {t['success']}; font-size: 13px; font-weight: bold;
    }}
    QPushButton[role="done"] {{
        background: {t['success']}18; border: 2px solid {t['success']};
        color: {t['success']}; font-size: 13px; font-weight: bold;
    }}
    QPushButton[role="done"]:hover {{ background: {t['success']}30; }}
    QPushButton[role="active"] {{
        background: {t['accent']}33; border: 2px solid {t['accent']};
        color: {t['accent']}; font-weight: bold;
    }}
    QLineEdit {{
        background: {t['entry']}; border: 1px solid {t['border']};
        color: {t['text']}; padding: 4px 8px; border-radius: 3px;
        font-size: 13px;
    }}
    QLineEdit:focus {{ border-color: {t['accent']}; }}
    QLabel {{ background: transparent; }}
    QGroupBox {{
        border: 1px solid {t['border']}; border-radius: 6px;
        margin-top: 16px; padding: 8px 6px 6px 6px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; subcontrol-position: top left;
        left: 10px; padding: 0 4px;
        color: {t['accent']}; font-size: 11px; font-weight: bold;
        letter-spacing: 1px;
    }}
    QScrollArea {{ border: none; }}
    QScrollBar:vertical {{ width: 6px; background: transparent; border: none; }}
    QScrollBar::handle:vertical {{
        background: {t['border']}; border-radius: 3px; min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QProgressBar {{
        border: 1px solid {t['border']}; border-radius: 3px;
        background: {t['entry']}; max-height: 8px;
    }}
    QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}
    QListWidget {{
        background: {t['entry']}; border: 1px solid {t['border']};
        color: {t['text']}; font-size: 11px;
    }}
    QListWidget::item:selected {{ background: {t['border']}; color: {t['accent']}; }}
    QSplitter::handle {{ background: {t['border']}; }}
    """


# ── helper widgets ─────────────────────────────────────────────────────────

class _NumEntry(QWidget):
    """Label + QLineEdit + unit label in one row."""
    changed = Signal(float)

    def __init__(self, label: str, default: float, unit: str = "mm",
                 lo: float = -9999.0, hi: float = 9999.0):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        lbl = QLabel(label)
        lbl.setFixedWidth(90)
        lbl.setStyleSheet("font-size: 13px;")
        lay.addWidget(lbl)

        self._edit = QLineEdit(str(default))
        self._edit.setValidator(QDoubleValidator(lo, hi, 1))
        self._edit.setFixedWidth(72)
        self._edit.setFixedHeight(28)
        self._edit.textChanged.connect(self._emit)
        lay.addWidget(self._edit)

        u = QLabel(unit)
        u.setStyleSheet("font-size: 12px; color: #4a5568;")
        lay.addWidget(u)
        lay.addStretch()

    def _emit(self, txt):
        try:
            self.changed.emit(float(txt))
        except ValueError:
            pass

    def get(self) -> float:
        try:
            return float(self._edit.text())
        except ValueError:
            return 0.0

    def set(self, v: float):
        self._edit.setText(f"{v:.1f}")


class _Section(QGroupBox):
    """Titled section container."""
    def __init__(self, title: str):
        super().__init__(title)
        self._lay = QVBoxLayout(self)
        self._lay.setSpacing(6)
        self._lay.setContentsMargins(8, 16, 8, 8)

    def add(self, w: QWidget) -> QWidget:
        self._lay.addWidget(w)
        return w

    def addRow(self, *widgets) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        for w in widgets:
            lay.addWidget(w)
        self._lay.addWidget(row)
        return row


# ── thread signals ─────────────────────────────────────────────────────────

class _WorkerSignals(QObject):
    done = Signal(int, str, str)


# ── main window ────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RC Car Body Creator")
        self.resize(1280, 800)

        self._model_path   = ""
        self._blender_path = ""
        self._model_size: dict  = {}
        self._loose_parts: list = []
        self._processing   = False
        self._signals: _WorkerSignals | None = None

        self._renderer = Renderer3D()
        self._active_pick_btn: QPushButton | None = None
        self._front_axle_y: float | None = None   # Y (height) picked for front axle
        self._rear_axle_y:  float | None = None   # Y (height) picked for rear axle
        self._result_cut_z:   float | None = None  # スケール後のCut Z（結果表示用）
        self._scale_info: dict = {}                # フルパイプライン後のスケール情報
        self._has_result_displayed: bool = False   # 結果モデル表示中フラグ

        os.makedirs(PREVIEW_DIR, exist_ok=True)
        os.makedirs(OUTPUTS_DIR, exist_ok=True)

        self._load_config()
        self._build_ui()
        self._apply_theme()
        self._set_render_mode("solid")
        self._set_view("iso")

        if not self._blender_path:
            QTimer.singleShot(300, self._detect_blender)

    # ── config ─────────────────────────────────────────────────────────────

    def _load_config(self):
        try:
            with open(CONFIG_PATH) as f:
                d = json.load(f)
            self._blender_path = d.get("blender_path", "")
        except Exception:
            pass

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump({"blender_path": self._blender_path}, f, indent=2)
        except Exception:
            pass

    # ── Blender detection ──────────────────────────────────────────────────

    def _detect_blender(self):
        if self._blender_path and os.path.isfile(self._blender_path):
            return
        found = ""
        if sys.platform == "darwin":
            for pat in [
                "/Applications/Blender*.app/Contents/MacOS/Blender",
                "/Applications/Blender.app/Contents/MacOS/Blender",
            ]:
                m = sorted(_glob.glob(pat))
                if m:
                    found = m[-1]
                    break
        elif sys.platform.startswith("win"):
            pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
            m = sorted(_glob.glob(
                os.path.join(pf, "Blender Foundation", "Blender *", "blender.exe")
            ))
            if m:
                found = m[-1]
        else:
            import shutil as _sh
            found = _sh.which("blender") or ""

        if found:
            self._blender_path = found
            self._blender_lbl.setText(f"Blender: {os.path.basename(found)}")
            self._save_config()
        else:
            self._blender_lbl.setText("Blender: not found — click Set…")

    # ── UI construction ────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        vbox.addWidget(self._build_header())

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.addWidget(self._build_viewport())
        splitter.addWidget(self._build_sidebar())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        vbox.addWidget(splitter, 1)

    def _build_header(self) -> QWidget:
        hdr = QWidget()
        hdr.setFixedHeight(48)
        lay = QHBoxLayout(hdr)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(8)

        title = QLabel("RC Car Body Creator")
        title.setStyleSheet(
            "font-size: 15px; font-weight: bold; letter-spacing: 1px;"
        )
        lay.addWidget(title)
        lay.addStretch()

        self._mode_btns: dict[str, QPushButton] = {}
        for mode, label in [("solid", "SOLID"), ("transparent", "TRANSP"), ("wireframe", "WIRE")]:
            btn = QPushButton(label)
            btn.setFixedSize(72, 30)
            btn.clicked.connect(lambda _, m=mode: self._set_render_mode(m))
            self._mode_btns[mode] = btn
            lay.addWidget(btn)

        lay.addSpacing(12)

        self._theme_btn = QPushButton("☀")
        self._theme_btn.setFixedSize(36, 30)
        self._theme_btn.setToolTip("Toggle dark/light theme")
        self._theme_btn.clicked.connect(self._toggle_theme)
        lay.addWidget(self._theme_btn)

        return hdr

    def _build_viewport(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── View toolbar ──────────────────────────────────────────────────
        vtb = QWidget()
        vtb.setFixedHeight(32)
        vtb_lay = QHBoxLayout(vtb)
        vtb_lay.setContentsMargins(6, 2, 6, 2)
        vtb_lay.setSpacing(4)

        self._view_btns: dict[str, QPushButton] = {}
        for vname, vlabel in [("iso", "ISO"), ("top", "TOP"),
                               ("front", "FRONT"), ("side", "SIDE")]:
            btn = QPushButton(vlabel)
            btn.setFixedSize(54, 24)
            btn.clicked.connect(lambda _, v=vname: self._set_view(v))
            self._view_btns[vname] = btn
            vtb_lay.addWidget(btn)

        vtb_lay.addStretch()

        self._proj_btn = QPushButton("PERSP")
        self._proj_btn.setFixedSize(58, 24)
        self._proj_btn.setToolTip("透視投影 ↔ 正投影 切り替え")
        self._proj_btn.clicked.connect(self._toggle_projection)
        vtb_lay.addWidget(self._proj_btn)

        lay.addWidget(vtb)

        rw = self._renderer.widget
        if rw is not None:
            rw.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            lay.addWidget(rw)
        else:
            lbl = QLabel(
                "3D viewer unavailable\n\n"
                "pip install vispy PyOpenGL PySide6\n\n"
                f"backend tried: {_BACKEND or 'none'}"
            )
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color: #4a5568; font-size: 13px;")
            lay.addWidget(lbl)

        # Direction legend bar at the bottom of the viewport
        self._dir_legend = QLabel(
            '<span style="color:#00e5ff">▶ FRONT (+X方向)</span>'
            '&nbsp;&nbsp;&nbsp;'
            '<span style="color:#39d353">▲ UP (+Y方向)</span>'
            '&nbsp;&nbsp;&nbsp;'
            '<span style="color:#ff6b35">▼ BOTTOM (−Y方向)</span>'
        )
        self._dir_legend.setTextFormat(Qt.RichText)
        self._dir_legend.setAlignment(Qt.AlignCenter)
        self._dir_legend.setStyleSheet(
            "font-size: 11px; padding: 4px 8px;"
        )
        lay.addWidget(self._dir_legend)

        return panel

    def _build_sidebar(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFixedWidth(300)

        content = QWidget()
        scroll.setWidget(content)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # ── 00 Orientation ────────────────────────────────────────────────
        s0 = _Section("00  ORIENTATION")

        hint = QLabel("Meshyモデルの向きを調整してから\n座標を設定してください")
        hint.setStyleSheet("font-size: 10px; color: #4a5568;")
        hint.setWordWrap(True)
        s0.add(hint)

        self._e_rot_x = _NumEntry("Rot X", 0.0, "°", -9999, 9999)
        self._e_rot_y = _NumEntry("Rot Y", 0.0, "°", -9999, 9999)
        self._e_rot_z = _NumEntry("Rot Z", 0.0, "°", -9999, 9999)
        for e in (self._e_rot_x, self._e_rot_y, self._e_rot_z):
            s0.add(e)

        # +90° step buttons — each click adds 90° and immediately applies
        s0.addRow(
            self._rot_step_btn("+90 X", "x"),
            self._rot_step_btn("+90 Y", "y"),
            self._rot_step_btn("+90 Z", "z"),
        )

        # Presets (snap to fixed angles)
        s0.addRow(
            self._preset_btn("Reset",  0.0,   0.0, 0.0),
            self._preset_btn("Flip X", 180.0, 0.0, 0.0),
            self._preset_btn("→X",     0.0,  90.0, 0.0),
        )

        self._apply_rot_btn = QPushButton("✓  Apply Rotation")
        self._apply_rot_btn.setProperty("role", "accent")
        self._apply_rot_btn.setFixedHeight(36)
        self._apply_rot_btn.clicked.connect(self._apply_rotation)
        s0.add(self._apply_rot_btn)

        lay.addWidget(s0)

        # ── 01 Model ──────────────────────────────────────────────────────
        s1 = _Section("01  MODEL")
        self._file_lbl = QLabel("No file selected")
        self._file_lbl.setWordWrap(True)
        self._file_lbl.setStyleSheet("font-size: 10px; color: #4a5568;")
        s1.add(self._file_lbl)

        self._open_btn = QPushButton("Open Model File…")
        self._open_btn.setProperty("role", "accent")
        self._open_btn.setFixedHeight(36)
        self._open_btn.clicked.connect(self._open_file)
        s1.add(self._open_btn)

        self._size_lbl = QLabel("")
        self._size_lbl.setStyleSheet("font-size: 10px; color: #4a5568;")
        s1.add(self._size_lbl)

        self._blender_lbl = QLabel(
            f"Blender: {os.path.basename(self._blender_path)}"
            if self._blender_path else "Blender: not found"
        )
        self._blender_lbl.setStyleSheet("font-size: 10px; color: #4a5568;")
        s1.add(self._blender_lbl)

        blender_btn = QPushButton("Set Blender Path…")
        blender_btn.clicked.connect(self._set_blender_path)
        s1.add(blender_btn)

        lay.addWidget(s1)

        # ── 02 Tires ──────────────────────────────────────────────────────
        s2 = _Section("02  TIRES")

        self._e_front_x  = _NumEntry("Front X",    85.0)
        self._e_rear_x   = _NumEntry("Rear X",     -85.0)
        self._e_offset_y = _NumEntry("Y Offset",    45.0)
        self._e_front_d  = _NumEntry("カット径 前", 52.0)
        self._e_rear_d   = _NumEntry("カット径 後", 52.0)

        for e in (self._e_front_x, self._e_rear_x, self._e_offset_y,
                  self._e_front_d, self._e_rear_d):
            s2.add(e)
            e.changed.connect(self._on_param_change)

        self._btn_front_x = self._pick_btn("▶ FRONT X", "front_x")
        self._btn_rear_x  = self._pick_btn("▶ REAR X",  "rear_x")
        s2.addRow(self._btn_front_x, self._btn_rear_x)

        # Current wheelbase readout
        self._wb_lbl = QLabel("現在のWB: — mm")
        self._wb_lbl.setStyleSheet("font-size: 10px; color: #4a5568;")
        s2.add(self._wb_lbl)
        # Update when either X entry changes
        self._e_front_x.changed.connect(lambda _: self._update_wb_label())
        self._e_rear_x.changed.connect(lambda _: self._update_wb_label())

        lay.addWidget(s2)

        # ── 03 Body ───────────────────────────────────────────────────────
        s3 = _Section("03  BODY")

        self._e_wheelbase   = _NumEntry("Target WB",    170.0)
        self._e_body_width  = _NumEntry("Body Width",   190.0)
        self._e_body_height = _NumEntry("Body Height",  100.0)
        self._e_thickness   = _NumEntry("Thickness",      1.5)
        self._e_cut_z       = _NumEntry("Cut Z",          10.0)

        for e in (self._e_wheelbase, self._e_body_width, self._e_body_height,
                  self._e_thickness, self._e_cut_z):
            s3.add(e)
            e.changed.connect(self._on_param_change)

        self._btn_cut_z = self._pick_btn("▶ PICK CUT Z", "cut_z")
        s3.add(self._btn_cut_z)
        lay.addWidget(s3)

        # ── 04 Execute ────────────────────────────────────────────────────
        s4 = _Section("04  EXECUTE")

        self._run_btn = QPushButton("▶  Blender で処理を実行")
        self._run_btn.setProperty("role", "success")
        self._run_btn.setFixedHeight(48)
        self._run_btn.clicked.connect(self._run_process)
        s4.add(self._run_btn)

        self._test_tire_btn = QPushButton("🔧  タイヤカットのみ（テスト）")
        self._test_tire_btn.setProperty("role", "accent")
        self._test_tire_btn.clicked.connect(lambda: self._run_process(mode="tire_cut_only"))
        s4.add(self._test_tire_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        s4.add(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("font-size: 12px;")
        self._status_lbl.setWordWrap(True)
        s4.add(self._status_lbl)

        self._clear_result_btn = QPushButton("✕  結果オーバーレイをクリア")
        self._clear_result_btn.setProperty("role", "accent2")
        self._clear_result_btn.setVisible(False)
        self._clear_result_btn.clicked.connect(self._clear_result_overlay)
        s4.add(self._clear_result_btn)

        # ── 貫通カット（04実行後に表示）────────────────────────────────────
        self._thru_sep = QLabel("── 貫通カット ──────────────")
        self._thru_sep.setStyleSheet("font-size: 10px; color: #4a5568; margin-top: 6px;")
        self._thru_sep.setVisible(False)
        s4.add(self._thru_sep)

        self._e_thru_front_d = _NumEntry("貫通径 前", 0.0)
        self._e_thru_rear_d  = _NumEntry("貫通径 後", 0.0)
        for e in (self._e_thru_front_d, self._e_thru_rear_d):
            e.setVisible(False)
            s4.add(e)
            e.changed.connect(self._on_param_change)

        self._thru_btn = QPushButton("⚡  貫通カット 実行")
        self._thru_btn.setProperty("role", "accent2")
        self._thru_btn.setFixedHeight(40)
        self._thru_btn.setVisible(False)
        self._thru_btn.setToolTip("スケール済み座標でタイヤ位置に円柱貫通カットを適用します。")
        self._thru_btn.clicked.connect(lambda: self._run_process(mode="through_cut"))
        s4.add(self._thru_btn)

        lay.addWidget(s4)

        # ── 05 Cleanup ────────────────────────────────────────────────────
        s5 = _Section("05  CLEANUP")

        self._parts_list = QListWidget()
        self._parts_list.setFixedHeight(100)
        s5.add(self._parts_list)

        del_btn = QPushButton("Delete Selected Parts")
        del_btn.setProperty("role", "accent2")
        del_btn.clicked.connect(self._delete_parts)
        s5.add(del_btn)

        lay.addWidget(s5)

        # ── 06 Export ─────────────────────────────────────────────────────
        s6 = _Section("06  EXPORT STL")

        exp_btn = QPushButton("Export STL…")
        exp_btn.setProperty("role", "accent")
        exp_btn.setFixedHeight(36)
        exp_btn.clicked.connect(self._export_stl)
        s6.add(exp_btn)

        lay.addWidget(s6)
        lay.addStretch()

        return scroll

    def _pick_btn(self, label: str, axis: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setProperty("role", "accent")
        btn.clicked.connect(lambda: self._start_pick(axis, btn))
        return btn

    def _preset_btn(self, label: str, rx: float, ry: float, rz: float) -> QPushButton:
        btn = QPushButton(label)
        def _apply():
            self._e_rot_x.set(rx)
            self._e_rot_y.set(ry)
            self._e_rot_z.set(rz)
            self._apply_rotation()
        btn.clicked.connect(_apply)
        return btn

    def _rot_step_btn(self, label: str, axis: str) -> QPushButton:
        """Button that adds 90° to the given axis entry and applies immediately."""
        btn = QPushButton(label)
        def _step():
            entry = {"x": self._e_rot_x, "y": self._e_rot_y, "z": self._e_rot_z}[axis]
            entry.set(entry.get() + 90.0)
            self._apply_rotation()
        btn.clicked.connect(_step)
        return btn

    # ── view presets & projection ───────────────────────────────────────────

    def _set_view(self, preset: str):
        """Switch to a named view preset (iso/top/front/side)."""
        if not self._renderer.available:
            return
        self._renderer.set_view_preset(preset)
        # Update button highlight
        for v, btn in self._view_btns.items():
            btn.setProperty("role", "active" if v == preset else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        # Update PERSP/ORTHO label
        self._proj_btn.setText("ORTHO" if self._renderer.is_ortho else "PERSP")
        self._proj_btn.setProperty("role", "active" if self._renderer.is_ortho else "")
        self._proj_btn.style().unpolish(self._proj_btn)
        self._proj_btn.style().polish(self._proj_btn)

    def _toggle_projection(self):
        """Toggle between perspective and orthographic projection."""
        if not self._renderer.available:
            return
        self._renderer.toggle_projection()
        is_o = self._renderer.is_ortho
        self._proj_btn.setText("ORTHO" if is_o else "PERSP")
        self._proj_btn.setProperty("role", "active" if is_o else "")
        self._proj_btn.style().unpolish(self._proj_btn)
        self._proj_btn.style().polish(self._proj_btn)

    # ── theme ──────────────────────────────────────────────────────────────

    def _apply_theme(self):
        t = THEMES[_CUR_THEME]
        _qapp.setStyleSheet(_build_qss(t))
        for w in self.findChildren(QWidget):
            w.style().unpolish(w)
            w.style().polish(w)
        if hasattr(self, "_dir_legend"):
            self._dir_legend.setStyleSheet(
                f"font-size: 11px; padding: 4px 8px;"
                f" background: {t['panel']}; border-top: 1px solid {t['border']};"
            )

    # ── orientation ────────────────────────────────────────────────────────

    def _apply_rotation(self):
        if not self._renderer.available:
            return
        self._renderer.apply_rotation(
            self._e_rot_x.get(),
            self._e_rot_y.get(),
            self._e_rot_z.get(),
        )
        self._update_viz()
        self._mark_btn_done(self._apply_rot_btn, "✓  回転適用済み")
        # Reset back to neutral after 2 seconds so it can be clicked again
        QTimer.singleShot(2000, lambda: (
            self._apply_rot_btn.setText("✓  Apply Rotation"),
            self._apply_rot_btn.setProperty("role", "accent"),
            self._apply_rot_btn.style().unpolish(self._apply_rot_btn),
            self._apply_rot_btn.style().polish(self._apply_rot_btn),
        ))

    def _toggle_theme(self):
        global _CUR_THEME
        _CUR_THEME = "light" if _CUR_THEME == "dark" else "dark"
        self._theme_btn.setText("☀" if _CUR_THEME == "dark" else "🌙")
        self._apply_theme()
        if self._renderer.available:
            self._renderer.set_bgcolor(THEMES[_CUR_THEME]["scene_bg"])

    # ── render mode ────────────────────────────────────────────────────────

    def _set_render_mode(self, mode: str):
        self._renderer.set_mode(mode)
        for m, btn in self._mode_btns.items():
            btn.setProperty("role", "active" if m == mode else "")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ── file open ──────────────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open 3D Model", "",
            "3D Models (*.glb *.obj *.stl *.fbx);;All files (*)"
        )
        if not path:
            return
        self._model_path = path
        self._file_lbl.setText(os.path.basename(path))
        self._open_btn.setText("読み込み中…")
        self._open_btn.setProperty("role", "")
        self._open_btn.style().unpolish(self._open_btn)
        self._open_btn.style().polish(self._open_btn)

        self._clear_result_btn.setVisible(False)
        self._front_axle_y = None
        self._rear_axle_y  = None
        self._result_cut_z = None
        if self._renderer.available:
            info = self._renderer.load(path)
            if info:
                self._model_size = info
                self._size_lbl.setText(
                    f"X:{info['X_mm']:.0f}  Y:{info['Y_mm']:.0f}  "
                    f"Z:{info['Z_mm']:.0f} mm  ({info['faces']:,} faces)"
                )
                self._update_viz()
                self._mark_btn_done(self._open_btn, "✓  モデル読み込み完了")
            else:
                self._open_btn.setText("Open Model File…")
                self._open_btn.setProperty("role", "accent")
                self._open_btn.style().unpolish(self._open_btn)
                self._open_btn.style().polish(self._open_btn)
        elif HAS_TRIMESH:
            self._load_size_only(path)
            self._mark_btn_done(self._open_btn, "✓  モデル読み込み完了")

    def _load_size_only(self, path: str):
        try:
            import numpy as np
            m   = _trimesh.load(path, force="mesh")
            v   = np.array(m.vertices, dtype=np.float32)
            ext = v.max(axis=0) - v.min(axis=0)
            if float(ext.max()) < 10.0:
                ext = ext * 1000.0
            self._size_lbl.setText(
                f"X:{ext[0]:.0f}  Y:{ext[1]:.0f}  Z:{ext[2]:.0f} mm"
            )
        except Exception as e:
            self._size_lbl.setText(f"Load error: {e}")

    # ── Blender path ───────────────────────────────────────────────────────

    def _set_blender_path(self):
        if sys.platform == "darwin":
            start = "/Applications"
        elif sys.platform.startswith("win"):
            start = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        else:
            start = "/usr/bin"

        path, _ = QFileDialog.getOpenFileName(
            self, "Select Blender Executable", start, "Executables (*)"
        )
        if not path:
            return

        # macOS: user may select Blender.app (a directory) instead of
        # the actual binary inside it — resolve automatically.
        if sys.platform == "darwin" and path.endswith(".app"):
            inner = os.path.join(path, "Contents", "MacOS", "Blender")
            if os.path.isfile(inner):
                path = inner

        if not os.path.isfile(path):
            QMessageBox.warning(self, "Invalid Path",
                                f"実行ファイルが見つかりません:\n{path}")
            return

        self._blender_path = path
        self._blender_lbl.setText(f"Blender: {os.path.basename(path)}")
        self._save_config()

    # ── parameter updates ──────────────────────────────────────────────────

    def _on_param_change(self, _val=None):
        QTimer.singleShot(0, self._update_viz)

    def _update_viz(self):
        if not self._renderer.available:
            return
        try:
            # 結果モデル表示中はスケール済み座標を計算して渡す
            sc_front_x = sc_rear_x = sc_offset_y = sc_front_cy = sc_rear_cy = None
            if self._has_result_displayed and self._scale_info:
                sx = self._scale_info.get("scale_x", 1.0)
                sy = self._scale_info.get("scale_y", 1.0)
                sz = self._scale_info.get("scale_z", 1.0)
                sc_front_x  = self._e_front_x.get()  * sx
                sc_rear_x   = self._e_rear_x.get()   * sx
                sc_offset_y = self._e_offset_y.get() * sz
                sc_front_cy = (self._front_axle_y * sy
                               if self._front_axle_y is not None else None)
                sc_rear_cy  = (self._rear_axle_y  * sy
                               if self._rear_axle_y  is not None else None)

            self._renderer.update_viz(
                front_x      = self._e_front_x.get(),
                rear_x       = self._e_rear_x.get(),
                offset_y     = self._e_offset_y.get(),
                front_cut_r  = self._e_front_d.get() / 2.0,
                rear_cut_r   = self._e_rear_d.get()  / 2.0,
                thru_front_r = self._e_thru_front_d.get() / 2.0 or None,
                thru_rear_r  = self._e_thru_rear_d.get()  / 2.0 or None,
                cut_z        = self._e_cut_z.get(),
                front_cy     = self._front_axle_y,
                rear_cy      = self._rear_axle_y,
                cut_z_result = self._result_cut_z,
                sc_front_x   = sc_front_x,
                sc_rear_x    = sc_rear_x,
                sc_offset_y  = sc_offset_y,
                sc_front_cy  = sc_front_cy,
                sc_rear_cy   = sc_rear_cy,
            )
        except Exception as e:
            print(f"[viz] {e}")

    def _clear_result_overlay(self):
        self._renderer.clear_result()
        self._clear_result_btn.setVisible(False)
        self._result_cut_z = None
        self._has_result_displayed = False
        self._thru_sep.setVisible(False)
        self._e_thru_front_d.setVisible(False)
        self._e_thru_rear_d.setVisible(False)
        self._thru_btn.setVisible(False)
        self._update_viz()

    def _update_wb_label(self):
        wb = abs(self._e_front_x.get() - self._e_rear_x.get())
        self._wb_lbl.setText(f"現在のWB: {wb:.1f} mm")

    # ── 3D picking ─────────────────────────────────────────────────────────

    def _mark_btn_done(self, btn: "QPushButton", text: str):
        """Change a button to the 'done' (green) state."""
        if btn is None:
            return
        btn.setText(text)
        btn.setProperty("role", "done")
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def _finish_pick(self, done_text: str = ""):
        """
        End pick mode.
        done_text: if provided, mark active button as done (green) with this label.
                   If empty, reset button back to accent (cancelled / no value).
        """
        if self._active_pick_btn is not None:
            if done_text:
                self._mark_btn_done(self._active_pick_btn, done_text)
            else:
                self._active_pick_btn.setProperty("role", "accent")
                self._active_pick_btn.style().unpolish(self._active_pick_btn)
                self._active_pick_btn.style().polish(self._active_pick_btn)
            self._active_pick_btn = None
        rw = self._renderer.widget
        if rw is not None:
            rw.setCursor(Qt.ArrowCursor)

    def _start_pick(self, axis: str, btn: "QPushButton | None" = None):
        # Auto-switch to SIDE view for X-axis picking (car side profile)
        if axis in ("front_x", "rear_x"):
            self._set_view("side")

        msg = {
            "front_x": "SIDE ビューでフロント車軸をクリック",
            "rear_x":  "SIDE ビューでリア車軸をクリック",
            "cut_z":   "ボディ底面の高さをクリック",
        }.get(axis, f"{axis} をクリック")

        # Deactivate previous pick button (restore to accent, not done)
        if self._active_pick_btn is not None:
            self._active_pick_btn.setProperty("role", "accent")
            self._active_pick_btn.style().unpolish(self._active_pick_btn)
            self._active_pick_btn.style().polish(self._active_pick_btn)

        # Activate new pick button — reset text and highlight
        self._active_pick_btn = btn
        _orig_labels = {
            "front_x": "▶  FRONT X",
            "rear_x":  "▶  REAR X",
            "cut_z":   "▶  PICK CUT Z",
        }
        if btn is not None:
            btn.setText(_orig_labels.get(axis, btn.text()))
            btn.setProperty("role", "active")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        # Crosshair cursor on the 3D canvas
        rw = self._renderer.widget
        if rw is not None:
            rw.setCursor(Qt.CrossCursor)

        def _cb(x, y, _z):
            if axis == "front_x":
                val = round(x, 1)
                self._e_front_x.set(val)
                self._front_axle_y = round(y, 1)
                self._finish_pick(done_text=f"✓  FRONT X  {val:.1f}mm")
            elif axis == "rear_x":
                val = round(x, 1)
                self._e_rear_x.set(val)
                self._rear_axle_y = round(y, 1)
                self._finish_pick(done_text=f"✓  REAR X  {val:.1f}mm")
            elif axis == "cut_z":
                # Y is height in vispy (Z is left-right); cut_z = cutting height
                val = round(y, 1)
                self._e_cut_z.set(val)
                self._finish_pick(done_text=f"✓  Cut Z  {val:.1f}mm")
            else:
                self._finish_pick()
            self._status_lbl.setText("✓ 設定しました")
            self._update_wb_label()

        def _miss():
            self._status_lbl.setText(f"ミス — モデル面をクリックしてください ({msg})")

        self._renderer.start_pick(_cb, _miss)
        self._status_lbl.setText(f"▶ {msg}…")

    # ── Blender process ────────────────────────────────────────────────────

    def _run_process(self, mode: str = "full"):
        if self._processing:
            return
        if not self._model_path:
            QMessageBox.warning(self, "No Model", "Please open a model file first.")
            return
        if not self._blender_path or not os.path.isfile(self._blender_path):
            QMessageBox.warning(self, "Blender Not Found",
                                "Please set the Blender executable path.")
            return

        params = {
            "input_file": self._model_path,
            "mode": mode,
            "orientation": {
                "rx": self._e_rot_x.get(),
                "ry": self._e_rot_y.get(),
                "rz": self._e_rot_z.get(),
            },
            "wheels": {
                "front_x":        self._e_front_x.get(),
                "rear_x":         self._e_rear_x.get(),
                "offset_y":       self._e_offset_y.get(),
                "front_diameter": self._e_front_d.get(),
                "rear_diameter":  self._e_rear_d.get(),
                "front_cy":       self._front_axle_y,   # タイヤ中心Y (mm, Noneなら自動)
                "rear_cy":        self._rear_axle_y,
            },
            "wheelbase_target": self._e_wheelbase.get(),
            "body_target": {
                "width_mm":  self._e_body_width.get(),
                "height_mm": self._e_body_height.get(),
            },
            "solidify": {
                "thickness": self._e_thickness.get(),
                "direction": "inner",
            },
            "through_cut": {
                "front_diameter": self._e_thru_front_d.get(),
                "rear_diameter":  self._e_thru_rear_d.get(),
            },
            "cut_z":        self._e_cut_z.get(),
            "output_stl":   os.path.join(PREVIEW_DIR, "result.stl"),
            "loose_json":   os.path.join(PREVIEW_DIR, "loose_parts.json"),
            "preview_dir":  PREVIEW_DIR,
            "remove_parts": [],
        }

        os.makedirs(os.path.dirname(PARAMS_PATH), exist_ok=True)
        with open(PARAMS_PATH, "w") as f:
            json.dump(params, f, indent=2)

        self._processing = True
        self._run_btn.setEnabled(False)
        self._test_tire_btn.setEnabled(False)
        self._thru_btn.setEnabled(False)   # 処理中は無効化（非表示でなくdisable）
        self._clear_result_btn.setVisible(False)
        self._renderer.hide_for_processing()   # 元モデル・結果モデルを非表示
        if mode == "tire_cut_only":
            self._run_btn.setText("処理中…")
            self._status_lbl.setText("⏳ タイヤカット処理中…")
        elif mode == "through_cut":
            self._thru_btn.setText("処理中…")
            self._status_lbl.setText("⏳ 貫通カット処理中…")
        else:
            self._run_btn.setText("処理中…")
            self._status_lbl.setText("⏳ 処理中です。しばらくお待ちください…")
        self._progress.setVisible(True)
        self._status_lbl.setStyleSheet("font-size: 12px;")

        self._signals = _WorkerSignals()
        self._signals.done.connect(self._on_done)
        cmd = [self._blender_path, "--background", "--python", SCRIPT_PATH]
        signals = self._signals

        def _worker():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                signals.done.emit(result.returncode, result.stdout, result.stderr)
            except subprocess.TimeoutExpired:
                signals.done.emit(-1, "", "Timeout after 5 minutes")
            except Exception as ex:
                signals.done.emit(-1, "", str(ex))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_done(self, code: int, stdout: str, stderr: str):
        self._processing = False
        self._run_btn.setEnabled(True)
        self._run_btn.setText("▶  Blender で処理を実行")
        self._test_tire_btn.setEnabled(True)
        self._thru_btn.setText("⚡  貫通カット 実行")
        self._progress.setVisible(False)

        if code != 0:
            self._renderer.clear_result()   # エラー時は元モデルを再表示
            self._has_result_displayed = False
            self._thru_btn.setEnabled(True)   # 処理完了で再有効化（非表示のまま）
            self._status_lbl.setStyleSheet("font-size: 12px; color: #ff6b35;")
            self._status_lbl.setText(f"❌ エラーが発生しました (code {code})")
            QMessageBox.critical(
                self, "Blender エラー",
                f"処理に失敗しました (終了コード {code})。\n\nタイヤ位置の設定を見直してください。\n\n詳細:\n{stderr[-1200:]}"
            )
            return

        self._status_lbl.setStyleSheet("font-size: 12px; color: #39d353;")
        self._status_lbl.setText("✅ 処理が完了しました！")

        # スケール情報を読み込み（フルパイプライン時のみ保存される）
        scale_info_path   = os.path.join(PREVIEW_DIR, "scale_info.json")
        intermediate_path = os.path.join(PREVIEW_DIR, "intermediate.blend")
        if os.path.isfile(scale_info_path):
            try:
                with open(scale_info_path) as f:
                    self._scale_info = json.load(f)
            except Exception:
                self._scale_info = {}
        # 貫通カットセクションは intermediate.blend が存在する場合のみ表示
        has_intermediate = os.path.isfile(intermediate_path)
        self._thru_sep.setVisible(has_intermediate)
        self._e_thru_front_d.setVisible(has_intermediate)
        self._e_thru_rear_d.setVisible(has_intermediate)
        self._thru_btn.setVisible(has_intermediate)
        self._thru_btn.setEnabled(True)

        loose_json = os.path.join(PREVIEW_DIR, "loose_parts.json")
        self._loose_parts = []
        self._parts_list.clear()
        if os.path.isfile(loose_json):
            try:
                with open(loose_json) as f:
                    self._loose_parts = json.load(f)
                for p in self._loose_parts:
                    self._parts_list.addItem(
                        QListWidgetItem(
                            f"{p['name']}  vol: {p.get('volume_mm3', 0):.0f} mm³"
                        )
                    )
            except Exception:
                pass

        result_stl = os.path.join(PREVIEW_DIR, "result.stl")
        if self._renderer.available and os.path.isfile(result_stl):
            self._renderer.load_result(result_stl)
            self._has_result_displayed = True
            # スケール後のCut Z: cut_z * scale_y（Yスケール適用後の実際のカット位置）
            original_height = self._model_size.get('Y_mm', 0)
            target_height   = self._e_body_height.get()
            cut_z_val = self._e_cut_z.get()
            if original_height > 0 and target_height > 0:
                scale_y = target_height / original_height
                self._result_cut_z = cut_z_val * scale_y
            else:
                self._result_cut_z = cut_z_val  # スケールなし
            self._update_viz()
            self._clear_result_btn.setVisible(True)

    # ── cleanup ────────────────────────────────────────────────────────────

    def _delete_parts(self):
        rows = [i.row() for i in self._parts_list.selectedIndexes()]
        if not rows:
            QMessageBox.information(self, "Nothing Selected",
                                    "Select parts in the list to delete.")
            return

        to_remove = [self._loose_parts[r]["name"] for r in rows
                     if r < len(self._loose_parts)]
        try:
            with open(PARAMS_PATH) as f:
                params = json.load(f)
            params["remove_parts"] = to_remove
            with open(PARAMS_PATH, "w") as f:
                json.dump(params, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self._run_btn.click()

    # ── export ─────────────────────────────────────────────────────────────

    def _export_stl(self):
        src = os.path.join(PREVIEW_DIR, "result.stl")
        if not os.path.isfile(src):
            QMessageBox.warning(self, "No Output",
                                "Run the Blender process first.")
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "Save STL", OUTPUTS_DIR, "STL files (*.stl)"
        )
        if dst:
            shutil.copy2(src, dst)
            QMessageBox.information(self, "Saved", f"Saved to:\n{dst}")


# ── entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    window = MainWindow()
    window.show()
    sys.exit(_qapp.exec())
