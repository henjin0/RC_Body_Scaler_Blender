"""
RC Car Body Creator - 3D Model Viewer
Embedded matplotlib viewer; click 2D projections to set tire positions etc.
"""

import tkinter as tk
from tkinter import ttk

import numpy as np

try:
    import trimesh
    HAS_TRIMESH = True
except ImportError:
    HAS_TRIMESH = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    from matplotlib.gridspec import GridSpec
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

FONT_NORMAL = ("Yu Gothic UI", 13)
FONT_BOLD   = ("Yu Gothic UI", 13, "bold")
BG     = "#F5F5F5"
ACCENT = "#1565C0"

# (key, label, color, applicable views)
MODES = [
    ("front_x",  "Front Wheel X",  "#1565C0", {"side", "top"}),
    ("rear_x",   "Rear Wheel X",   "#0D47A1", {"side", "top"}),
    ("offset_y", "Wheel Y Offset", "#2E7D32", {"top",  "front"}),
    ("cut_z",    "Cut Height Z",   "#E65100", {"side", "front"}),
]


def _detect_scale(vertices: np.ndarray) -> float:
    """
    Estimate scale factor to convert vertices to mm.
    Heuristic: if max extent < 10, assume meters; otherwise assume mm.
    """
    ext_max = float(np.ptp(vertices, axis=0).max())
    if ext_max < 10.0:
        return 1000.0   # meters → mm
    return 1.0          # already mm (or similar)


class ModelViewer(tk.Toplevel):

    def __init__(self, parent, model_path: str, initial_params: dict, on_apply):
        super().__init__(parent)
        self.title("3D Viewer — Click to set positions")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(1050, 700)

        self.model_path    = model_path
        self.on_apply      = on_apply
        self.pick_mode     = tk.StringVar(value="front_x")

        self.values = {
            "front_x":  tk.DoubleVar(value=float(initial_params.get("front_x",   85.0))),
            "rear_x":   tk.DoubleVar(value=float(initial_params.get("rear_x",   -85.0))),
            "offset_y": tk.DoubleVar(value=float(initial_params.get("offset_y",  45.0))),
            "cut_z":    tk.DoubleVar(value=float(initial_params.get("cut_z",     10.0))),
        }
        for v in self.values.values():
            v.trace_add("write", lambda *_: self._redraw_2d())

        # mesh data (all in mm)
        self.verts_mm:   np.ndarray | None = None   # (N,3) all vertices
        self.verts_disp: np.ndarray | None = None   # subset for 3D rendering
        self.faces_disp: np.ndarray | None = None   # subset faces for 3D rendering

        if not HAS_TRIMESH or not HAS_MPL:
            missing = [n for n, ok in [("trimesh", HAS_TRIMESH), ("matplotlib", HAS_MPL)] if not ok]
            tk.Label(self,
                     text=f"Required libraries missing: {', '.join(missing)}\n"
                          f"pip install {' '.join(missing)}",
                     font=FONT_NORMAL, bg=BG, fg="red").pack(pady=40)
            return

        self._load_mesh()
        self._build_ui()
        self._draw_3d()
        self._draw_2d()
        self.canvas.draw()

    # ------------------------------------------------------------------ #
    #  Mesh loading
    # ------------------------------------------------------------------ #

    def _load_mesh(self):
        try:
            mesh = trimesh.load(self.model_path, force="mesh")
            v    = np.array(mesh.vertices, dtype=np.float64)
            f    = np.array(mesh.faces,    dtype=np.int32)

            scale          = _detect_scale(v)
            self.verts_mm  = v * scale

            # Subsample faces for 3D rendering (keep coordinates intact)
            max_faces = 6000
            if len(f) > max_faces:
                idx              = np.random.default_rng(0).choice(len(f), max_faces, replace=False)
                self.faces_disp  = f[idx]
            else:
                self.faces_disp  = f
            self.verts_disp = self.verts_mm   # same vertices, just fewer faces

        except Exception as e:
            print(f"[Viewer] mesh load error: {e}")

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        main = tk.Frame(self, bg=BG, padx=6, pady=6)
        main.pack(fill=tk.BOTH, expand=True)

        # ── matplotlib figure ──
        self.fig = Figure(figsize=(13, 7), facecolor="#FAFAFA")
        gs = GridSpec(3, 2, figure=self.fig,
                      width_ratios=[1.8, 1],
                      left=0.04, right=0.97, top=0.95, bottom=0.07,
                      wspace=0.32, hspace=0.45)

        self.ax3d    = self.fig.add_subplot(gs[:, 0], projection="3d")
        self.ax_side = self.fig.add_subplot(gs[0, 1])   # X-Z side view
        self.ax_top  = self.fig.add_subplot(gs[1, 1])   # X-Y top view
        self.ax_front= self.fig.add_subplot(gs[2, 1])   # Y-Z front view

        self.canvas = FigureCanvasTkAgg(self.fig, master=main)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas.mpl_connect("button_press_event", self._on_click)

        # ── control panel ──
        ctrl = tk.Frame(main, bg=BG)
        ctrl.pack(fill=tk.X, pady=(6, 0))

        mode_frm = tk.LabelFrame(ctrl, text="Parameter to set (click on 2D view)",
                                 font=FONT_BOLD, bg=BG, fg=ACCENT,
                                 bd=2, relief=tk.GROOVE, padx=8, pady=4)
        mode_frm.pack(side=tk.LEFT, padx=(0, 12))

        view_label = {"side": "Side", "top": "Top", "front": "Front"}
        for key, label, color, views in MODES:
            views_str = "/".join(view_label[v] for v in sorted(views))
            rb = tk.Radiobutton(
                mode_frm,
                text=f"{label}\n({views_str} view)",
                variable=self.pick_mode, value=key,
                font=("Yu Gothic UI", 12), bg=BG,
                activebackground=BG, selectcolor="#E3F2FD",
                justify=tk.LEFT,
            )
            rb.pack(side=tk.LEFT, padx=6)

        # current values
        val_frm = tk.LabelFrame(ctrl, text="Current values",
                                font=FONT_BOLD, bg=BG, fg=ACCENT,
                                bd=2, relief=tk.GROOVE, padx=8, pady=4)
        val_frm.pack(side=tk.LEFT, padx=(0, 12), fill=tk.Y)

        for key, label, color, _ in MODES:
            col = tk.Frame(val_frm, bg=BG)
            col.pack(side=tk.LEFT, padx=8)
            tk.Label(col, text=label, font=("Yu Gothic UI", 10), bg=BG).pack()
            tk.Label(col, textvariable=self.values[key],
                     font=("Yu Gothic UI", 14, "bold"),
                     bg=BG, fg=color, width=6).pack()
            tk.Label(col, text="mm", font=("Yu Gothic UI", 10), bg=BG).pack()

        tk.Button(ctrl, text="Apply to main window",
                  font=("Yu Gothic UI", 14, "bold"),
                  bg="#2E7D32", fg="white", relief=tk.FLAT, padx=14, pady=6,
                  command=self._apply).pack(side=tk.RIGHT, padx=6)

        tk.Label(main,
                 text="3D view: drag to rotate, scroll to zoom  |  "
                      "Click on Side/Top/Front view to set the selected parameter",
                 font=("Yu Gothic UI", 11), bg=BG, fg="#666").pack(pady=(4, 0))

    # ------------------------------------------------------------------ #
    #  Drawing
    # ------------------------------------------------------------------ #

    def _draw_3d(self):
        ax = self.ax3d
        ax.cla()
        ax.set_title("3D View (drag to rotate)", fontsize=10)
        ax.set_xlabel("X (mm)", fontsize=7)
        ax.set_ylabel("Y (mm)", fontsize=7)
        ax.set_zlabel("Z (mm)", fontsize=7)
        ax.tick_params(labelsize=6)

        if self.verts_disp is not None and self.faces_disp is not None and len(self.faces_disp):
            v, f = self.verts_disp, self.faces_disp
            try:
                tris = v[f]
                poly = Poly3DCollection(tris, alpha=0.20, linewidth=0.05,
                                        edgecolor="#90A4AE", facecolor="#78909C")
                ax.add_collection3d(poly)
                ax.set_xlim(v[:, 0].min(), v[:, 0].max())
                ax.set_ylim(v[:, 1].min(), v[:, 1].max())
                ax.set_zlim(v[:, 2].min(), v[:, 2].max())
            except Exception as e:
                print(f"[Viewer] 3D draw error: {e}")
                return

            # Markers for current parameter values
            fx = self.values["front_x"].get()
            rx = self.values["rear_x"].get()
            oy = self.values["offset_y"].get()
            cz = self.values["cut_z"].get()
            mid_z = (v[:, 2].max() + v[:, 2].min()) / 2

            for xi, col in [(fx, "#1565C0"), (rx, "#0D47A1")]:
                ax.scatter([xi, xi], [oy, -oy], [mid_z, mid_z],
                           c=col, s=60, zorder=5, depthshade=False)

            # Cut height plane
            xr = [v[:, 0].min(), v[:, 0].max()]
            yr = [v[:, 1].min(), v[:, 1].max()]
            xx, yy = np.meshgrid(xr, yr)
            ax.plot_surface(xx, yy, np.full_like(xx, cz),
                            alpha=0.15, color="#E65100")

    def _redraw_2d(self):
        if not hasattr(self, "canvas"):
            return
        self._draw_2d()
        self.canvas.draw_idle()

    def _draw_2d(self):
        self._draw_side()
        self._draw_top()
        self._draw_front()

    def _scatter(self, ax, xs, ys):
        if self.verts_mm is None:
            return
        v    = self.verts_mm
        step = max(1, len(v) // 8000)
        ax.scatter(xs[::step], ys[::step],
                   s=0.5, c="#90A4AE", alpha=0.4, rasterized=True)

    def _draw_side(self):
        ax = self.ax_side
        ax.cla()
        ax.set_title("Side View (X-Z)  Front/Rear X | Cut Z", fontsize=8.5)
        ax.set_xlabel("X (mm)", fontsize=7)
        ax.set_ylabel("Z (mm)", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3)
        ax.set_aspect("equal", adjustable="datalim")

        if self.verts_mm is not None:
            self._scatter(ax, self.verts_mm[:, 0], self.verts_mm[:, 2])

        fx = self.values["front_x"].get()
        rx = self.values["rear_x"].get()
        cz = self.values["cut_z"].get()
        ax.axvline(fx, color="#1565C0", lw=1.5, label=f"FrontX {fx:.1f}")
        ax.axvline(rx, color="#0D47A1", lw=1.5, ls="--", label=f"RearX {rx:.1f}")
        ax.axhline(cz, color="#E65100", lw=1.5, label=f"CutZ {cz:.1f}")
        ax.legend(fontsize=7, loc="upper right", framealpha=0.7)

    def _draw_top(self):
        ax = self.ax_top
        ax.cla()
        ax.set_title("Top View (X-Y)  Front/Rear X | Y Offset", fontsize=8.5)
        ax.set_xlabel("X (mm)", fontsize=7)
        ax.set_ylabel("Y (mm)", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3)
        ax.set_aspect("equal", adjustable="datalim")

        if self.verts_mm is not None:
            self._scatter(ax, self.verts_mm[:, 0], self.verts_mm[:, 1])

        fx = self.values["front_x"].get()
        rx = self.values["rear_x"].get()
        oy = self.values["offset_y"].get()
        ax.axvline(fx, color="#1565C0", lw=1.5, label=f"FrontX {fx:.1f}")
        ax.axvline(rx, color="#0D47A1", lw=1.5, ls="--", label=f"RearX {rx:.1f}")
        ax.axhline( oy, color="#2E7D32", lw=1.5, label=f"Y +/-{oy:.1f}")
        ax.axhline(-oy, color="#2E7D32", lw=1.5, ls="--")
        ax.legend(fontsize=7, loc="upper right", framealpha=0.7)

    def _draw_front(self):
        ax = self.ax_front
        ax.cla()
        ax.set_title("Front View (Y-Z)  Y Offset | Cut Z", fontsize=8.5)
        ax.set_xlabel("Y (mm)", fontsize=7)
        ax.set_ylabel("Z (mm)", fontsize=7)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.3)
        ax.set_aspect("equal", adjustable="datalim")

        if self.verts_mm is not None:
            self._scatter(ax, self.verts_mm[:, 1], self.verts_mm[:, 2])

        oy = self.values["offset_y"].get()
        cz = self.values["cut_z"].get()
        ax.axvline( oy, color="#2E7D32", lw=1.5, label=f"Y +/-{oy:.1f}")
        ax.axvline(-oy, color="#2E7D32", lw=1.5, ls="--")
        ax.axhline(cz,  color="#E65100", lw=1.5, label=f"CutZ {cz:.1f}")
        ax.legend(fontsize=7, loc="upper right", framealpha=0.7)

    # ------------------------------------------------------------------ #
    #  Click handler
    # ------------------------------------------------------------------ #

    def _on_click(self, event):
        if event.inaxes is None or event.button != 1:
            return
        x, y = event.xdata, event.ydata
        if x is None or y is None:
            return

        ax   = event.inaxes
        mode = self.pick_mode.get()
        updated = False

        if ax == self.ax_side:    # X-Z
            if mode == "front_x":
                self.values["front_x"].set(round(x, 1));  updated = True
            elif mode == "rear_x":
                self.values["rear_x"].set(round(x, 1));   updated = True
            elif mode == "cut_z":
                self.values["cut_z"].set(round(y, 1));    updated = True

        elif ax == self.ax_top:   # X-Y
            if mode == "front_x":
                self.values["front_x"].set(round(x, 1));         updated = True
            elif mode == "rear_x":
                self.values["rear_x"].set(round(x, 1));          updated = True
            elif mode == "offset_y":
                self.values["offset_y"].set(round(abs(y), 1));   updated = True

        elif ax == self.ax_front:  # Y-Z
            if mode == "offset_y":
                self.values["offset_y"].set(round(abs(x), 1));   updated = True
            elif mode == "cut_z":
                self.values["cut_z"].set(round(y, 1));           updated = True

        if updated:
            self._draw_3d()
            self._draw_2d()
            self.canvas.draw_idle()

    # ------------------------------------------------------------------ #
    #  Apply
    # ------------------------------------------------------------------ #

    def _apply(self):
        self.on_apply({k: v.get() for k, v in self.values.items()})
        self.destroy()
