import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.gridspec import GridSpec
import time
import csv
import os
from datetime import datetime

from core.fpga_sim   import FPGASimulator
from core.ai_engine  import AnomalyDetector
from core.nlp_parser import NLPParser
C = {
    "bg":        "
    "panel":     "
    "border":    "
    "accent":    "
    "accent2":   "
    "accent3":   "
    "text":      "
    "text_dim":  "
    "critical":  "
    "warning":   "
    "normal":    "
    "plot_bg":   "
    "plot_grid": "
}

FONT_MONO  = ("Courier New", 10)
FONT_LABEL = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 11, "bold")
FONT_BIG   = ("Segoe UI", 13, "bold")

UPDATE_MS = 250
matplotlib.rcParams.update({
    "figure.facecolor":  C["plot_bg"],
    "axes.facecolor":    C["plot_bg"],
    "axes.edgecolor":    C["border"],
    "axes.labelcolor":   C["text_dim"],
    "axes.titlecolor":   C["text"],
    "xtick.color":       C["text_dim"],
    "ytick.color":       C["text_dim"],
    "grid.color":        C["plot_grid"],
    "grid.linewidth":    0.5,
    "text.color":        C["text"],
    "lines.linewidth":   1.4,
    "font.family":       "monospace",
    "font.size":         8,
})

class StatusBar(tk.Frame):

    def __init__(self, parent, fpga: FPGASimulator, **kw):
        super().__init__(parent, bg=C["panel"], pady=6, **kw)
        self.fpga = fpga
        self._labels = {}
        fields = [
            ("CLK",  "Clock",  "MHz"),
            ("TEMP", "Temp",   "°C"),
            ("VOLT", "Vcc",    "V"),
            ("PWR",  "Power",  "W"),
            ("MODE", "Mode",   ""),
        ]
        for key, label, unit in fields:
            frm = tk.Frame(self, bg=C["panel"])
            frm.pack(side=tk.LEFT, padx=18)
            tk.Label(frm, text=label, font=("Segoe UI", 8), fg=C["text_dim"],
                     bg=C["panel"]).pack()
            lbl = tk.Label(frm, text="—", font=("Segoe UI", 14, "bold"),
                           fg=C["accent"], bg=C["panel"])
            lbl.pack()
            if unit:
                tk.Label(frm, text=unit, font=("Segoe UI", 8), fg=C["text_dim"],
                         bg=C["panel"]).pack()
            self._labels[key] = lbl
        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)

    def refresh(self):
        fpga = self.fpga
        self._labels["CLK"].config(text=f"{fpga.clk_freq_mhz:.1f}")
        self._labels["TEMP"].config(text=f"{fpga.temperature_c:.0f}",
            fg=C["critical"] if fpga.temperature_c > 60 else C["accent"])
        self._labels["VOLT"].config(text=f"{fpga.voltage_v:.2f}",
            fg=C["warning"] if abs(fpga.voltage_v - 3.3) > 0.2 else C["accent"])
        self._labels["PWR"].config(text=f"{fpga.power_w:.2f}")
        if fpga.anomaly_mode:
            self._labels["MODE"].config(text="FAULT", fg=C["critical"])
        else:
            self._labels["MODE"].config(text="NORMAL", fg=C["normal"])

class RegisterTab(tk.Frame):

    COLUMNS = ("addr", "name", "hex", "dec", "desc")
    COL_HEADERS = ("Address", "Name", "Hex", "Dec", "Description")
    COL_WIDTHS  = (70, 110, 60, 60, 260)

    def __init__(self, parent, fpga: FPGASimulator, parser: NLPParser,
                 console_fn, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self.fpga       = fpga
        self.parser     = parser
        self.console_fn = console_fn
        self._build()

    def _build(self):
        bar = tk.Frame(self, bg=C["panel"], pady=6)
        bar.pack(fill=tk.X)
        tk.Label(bar, text="FPGA Register Map", font=FONT_TITLE,
                 fg=C["accent"], bg=C["panel"]).pack(side=tk.LEFT, padx=12)
        tk.Button(bar, text="Reset All", font=FONT_LABEL,
                  bg=C["border"], fg=C["text"], relief=tk.FLAT, padx=8,
                  command=self._reset_all).pack(side=tk.RIGHT, padx=8)
        tk.Button(bar, text="Export CSV", font=FONT_LABEL,
                  bg=C["border"], fg=C["text"], relief=tk.FLAT, padx=8,
                  command=self._export_csv).pack(side=tk.RIGHT, padx=4)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Reg.Treeview",
                        background=C["panel"],
                        fieldbackground=C["panel"],
                        foreground=C["text"],
                        rowheight=28,
                        font=FONT_MONO,
                        borderwidth=0)
        style.configure("Reg.Treeview.Heading",
                        background=C["border"],
                        foreground=C["accent"],
                        relief=tk.FLAT,
                        font=FONT_TITLE)
        style.map("Reg.Treeview",
                  background=[("selected", C["accent"])],
                  foreground=[("selected", C["bg"])])

        tree_frame = tk.Frame(self, bg=C["bg"])
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        self.tree = ttk.Treeview(tree_frame, style="Reg.Treeview",
                                  columns=self.COLUMNS, show="headings",
                                  selectmode="browse")
        for col, hdr, w in zip(self.COLUMNS, self.COL_HEADERS, self.COL_WIDTHS):
            self.tree.heading(col, text=hdr)
            self.tree.column(col, width=w, anchor=tk.CENTER
                             if col in ("addr","hex","dec") else tk.W)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)
        self._populate()
        leg = tk.Frame(self, bg=C["bg"])
        leg.pack(fill=tk.X, padx=10, pady=(0, 6))
        tk.Label(leg, text="● Writable", fg=C["accent"],   bg=C["bg"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=6)
        tk.Label(leg, text="● Read-only", fg=C["text_dim"], bg=C["bg"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=6)
        tk.Label(leg, text="Double-click a writable row to edit",
                 fg=C["text_dim"], bg=C["bg"],
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=6)

    def _populate(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for addr, reg in self.fpga.regs.items():
            v = reg["value"]
            fg = C["accent"] if reg["writable"] else C["text_dim"]
            self.tree.insert("", tk.END, iid=addr, tags=(addr,),
                             values=(addr, reg["name"], f"0x{v:02X}",
                                     str(v), reg["desc"]))
            self.tree.tag_configure(addr, foreground=fg)

    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        reg = self.fpga.regs.get(item)
        if not reg or not reg["writable"]:
            self.console_fn(f"  {reg['name']} is read-only.", error=True)
            return
        self._edit_dialog(item, reg)

    def _edit_dialog(self, addr, reg):
        dlg = tk.Toplevel(self)
        dlg.title(f"Edit {reg['name']}")
        dlg.configure(bg=C["panel"])
        dlg.resizable(False, False)
        dlg.grab_set()

        tk.Label(dlg, text=f"Set {reg['name']}  ({addr})",
                 font=FONT_TITLE, fg=C["accent"], bg=C["panel"]).pack(padx=20, pady=(16, 4))
        tk.Label(dlg, text=f"Current: 0x{reg['value']:02X}  ({reg['value']})",
                 font=FONT_MONO, fg=C["text_dim"], bg=C["panel"]).pack()
        tk.Label(dlg, text=reg["desc"], font=("Segoe UI", 9),
                 fg=C["text_dim"], bg=C["panel"]).pack(pady=(0, 10))

        var = tk.StringVar(value=f"0x{reg['value']:02X}")
        entry = tk.Entry(dlg, textvariable=var, font=FONT_MONO,
                         bg=C["border"], fg=C["text"], insertbackground=C["accent"],
                         width=12, justify=tk.CENTER, relief=tk.FLAT)
        entry.pack(padx=20, pady=4)
        entry.select_range(0, tk.END)
        entry.focus()

        def apply():
            raw = var.get().strip()
            ok, msg = True, ""
            try:
                val = int(raw, 16) if raw.lower().startswith("0x") else int(raw)
            except ValueError:
                ok, msg = False, f"Invalid value: {raw}"
            if ok:
                ok, msg = self.fpga.write_register(addr, val)
            self.console_fn(f"  {msg}", error=not ok)
            if ok:
                self.refresh()
                dlg.destroy()

        btn_frame = tk.Frame(dlg, bg=C["panel"])
        btn_frame.pack(pady=12)
        tk.Button(btn_frame, text="Apply", font=FONT_LABEL,
                  bg=C["accent"], fg=C["bg"], relief=tk.FLAT, width=8,
                  command=apply).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_frame, text="Cancel", font=FONT_LABEL,
                  bg=C["border"], fg=C["text"], relief=tk.FLAT, width=8,
                  command=dlg.destroy).pack(side=tk.LEFT, padx=6)
        entry.bind("<Return>", lambda e: apply())

    def _reset_all(self):
        msg = self.fpga.reset_registers()
        self.console_fn(f"  {msg}")
        self.refresh()

    def _export_csv(self):
        path = os.path.join(os.path.dirname(__file__), "..", "fpga_config_export.csv")
        path = os.path.abspath(path)
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Address", "Name", "Hex", "Dec", "Writable", "Description"])
            for addr, reg in self.fpga.regs.items():
                v = reg["value"]
                w.writerow([addr, reg["name"], f"0x{v:02X}", v,
                            "Yes" if reg["writable"] else "No", reg["desc"]])
        self.console_fn(f"  Config exported → {path}")

    def refresh(self):
        for addr, reg in self.fpga.regs.items():
            v = reg["value"]
            self.tree.item(addr, values=(addr, reg["name"], f"0x{v:02X}",
                                         str(v), reg["desc"]))

class SignalTab(tk.Frame):

    SIGNALS  = ["CLK", "GPIO", "ADC", "VOLTAGE"]
    COLORS   = ["
    Y_LABELS = ["Logic", "Logic", "Volts", "Volts"]

    def __init__(self, parent, fpga: FPGASimulator, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self.fpga  = fpga
        self._data = {s: np.zeros(120) for s in self.SIGNALS}
        self._build()

    def _build(self):
        bar = tk.Frame(self, bg=C["panel"], pady=6)
        bar.pack(fill=tk.X)
        tk.Label(bar, text="Live Signal Monitor  (4-channel)",
                 font=FONT_TITLE, fg=C["accent"], bg=C["panel"]).pack(side=tk.LEFT, padx=12)
        tk.Label(bar, text="Refresh: 250 ms", font=("Segoe UI", 9),
                 fg=C["text_dim"], bg=C["panel"]).pack(side=tk.RIGHT, padx=12)

        self.fig = Figure(figsize=(9, 5), tight_layout=True)
        self.axes = []
        gs = GridSpec(4, 1, hspace=0.1, figure=self.fig)
        for i, (sig, col, ylbl) in enumerate(
                zip(self.SIGNALS, self.COLORS, self.Y_LABELS)):
            ax = self.fig.add_subplot(gs[i])
            ax.set_ylabel(ylbl, fontsize=7)
            ax.set_title(sig, loc="left", fontsize=8, color=col, pad=2)
            ax.grid(True, axis="y")
            ax.set_xticks([])
            self.axes.append(ax)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
        leg = tk.Frame(self, bg=C["bg"])
        leg.pack(fill=tk.X, padx=10, pady=(0, 6))
        for sig, col in zip(self.SIGNALS, self.COLORS):
            tk.Label(leg, text=f"■ {sig}", fg=col, bg=C["bg"],
                     font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=10)

    def update_plot(self, sigs: dict):
        n = len(sigs["CLK"])
        for ax, sig, col in zip(self.axes, self.SIGNALS, self.COLORS):
            ax.cla()
            ax.plot(sigs["time"], sigs[sig], color=col, linewidth=1.2)
            ax.set_xlim(sigs["time"][0], sigs["time"][-1])
            ax.set_xticks([])
            ax.grid(True, alpha=0.3)
            ax.set_ylabel(self.Y_LABELS[self.SIGNALS.index(sig)], fontsize=7)
            ax.set_title(sig, loc="left", fontsize=8, color=col, pad=2)
        self.canvas.draw_idle()

class AITab(tk.Frame):

    def __init__(self, parent, detector: AnomalyDetector, **kw):
        super().__init__(parent, bg=C["bg"], **kw)
        self.detector = detector
        self._build()

    def _build(self):
        bar = tk.Frame(self, bg=C["panel"], pady=6)
        bar.pack(fill=tk.X)
        tk.Label(bar, text="AI Anomaly Monitor  (Isolation Forest)",
                 font=FONT_TITLE, fg=C["accent"], bg=C["panel"]).pack(side=tk.LEFT, padx=12)
        badge_frame = tk.Frame(bar, bg=C["panel"])
        badge_frame.pack(side=tk.RIGHT, padx=12)
        tk.Label(badge_frame, text="Status:", font=FONT_LABEL,
                 fg=C["text_dim"], bg=C["panel"]).pack(side=tk.LEFT)
        self.severity_lbl = tk.Label(badge_frame, text="TRAINING",
                                      font=FONT_BIG, fg=C["accent"], bg=C["panel"],
                                      width=12)
        self.severity_lbl.pack(side=tk.LEFT, padx=6)
        self.fig_ai = Figure(figsize=(9, 2.8), tight_layout=True)
        self.ax_ai  = self.fig_ai.add_subplot(111)
        self.ax_ai.set_title("Anomaly Score (Isolation Forest)", fontsize=9)
        self.ax_ai.set_ylabel("Score")
        self.ax_ai.set_xlabel("Samples")
        self.ax_ai.axhline(-0.25, color=C["warning"], linewidth=0.9,
                            linestyle="--", label="Warning threshold")
        self.ax_ai.axhline(-0.45, color=C["critical"], linewidth=0.9,
                            linestyle="--", label="Critical threshold")
        self.ax_ai.legend(fontsize=7, loc="lower right")
        self.ax_ai.grid(True, alpha=0.3)

        self.canvas_ai = FigureCanvasTkAgg(self.fig_ai, master=self)
        self.canvas_ai.get_tk_widget().pack(fill=tk.X, padx=10, pady=(6, 4))
        self.prog_var = tk.DoubleVar(value=0)
        self.prog_frame = tk.Frame(self, bg=C["bg"])
        self.prog_frame.pack(fill=tk.X, padx=10)
        tk.Label(self.prog_frame, text="Collecting training data:",
                 font=("Segoe UI", 9), fg=C["text_dim"], bg=C["bg"]).pack(side=tk.LEFT)
        self.prog_bar = ttk.Progressbar(self.prog_frame, variable=self.prog_var,
                                         maximum=1.0, length=200)
        self.prog_bar.pack(side=tk.LEFT, padx=8)
        self.prog_lbl = tk.Label(self.prog_frame, text="0 %", font=("Segoe UI", 9),
                                  fg=C["text_dim"], bg=C["bg"])
        self.prog_lbl.pack(side=tk.LEFT)
        log_label = tk.Frame(self, bg=C["bg"])
        log_label.pack(fill=tk.X, padx=10, pady=(8, 0))
        tk.Label(log_label, text="Alert Log", font=FONT_TITLE,
                 fg=C["accent"], bg=C["bg"]).pack(side=tk.LEFT)

        self.alert_text = tk.Text(self, height=7, font=FONT_MONO,
                                   bg=C["panel"], fg=C["text"],
                                   insertbackground=C["accent"],
                                   relief=tk.FLAT, state=tk.DISABLED,
                                   selectbackground=C["accent"])
        self.alert_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 8))
        sb = ttk.Scrollbar(self.alert_text, command=self.alert_text.yview)
        self.alert_text.configure(yscrollcommand=sb.set)

    def update_plot(self, scores, labels, severity, progress):
        self.prog_var.set(progress)
        self.prog_lbl.config(text=f"{int(progress * 100)} %")
        if progress >= 1.0:
            self.prog_frame.pack_forget()
        self.ax_ai.cla()
        if scores:
            xs = list(range(len(scores)))
            ys = scores
            colors = [C["critical"] if s < -0.45 else
                      C["warning"]  if s < -0.25 else
                      C["normal"] for s in ys]
            self.ax_ai.scatter(xs, ys, c=colors, s=6, zorder=3)
            self.ax_ai.plot(xs, ys, color=C["text_dim"], linewidth=0.8, alpha=0.5)
            self.ax_ai.fill_between(xs, ys, 0,
                                     where=[s < -0.25 for s in ys],
                                     color=C["critical"], alpha=0.15)
        self.ax_ai.axhline(-0.25, color=C["warning"], linewidth=0.9,
                            linestyle="--", label="Warning")
        self.ax_ai.axhline(-0.45, color=C["critical"], linewidth=0.9,
                            linestyle="--", label="Critical")
        self.ax_ai.set_ylim(-0.7, 0.2)
        self.ax_ai.set_ylabel("Score")
        self.ax_ai.set_xlabel("Samples")
        self.ax_ai.set_title("Anomaly Score (Isolation Forest)", fontsize=9)
        self.ax_ai.legend(fontsize=7, loc="lower right")
        self.ax_ai.grid(True, alpha=0.3)
        self.canvas_ai.draw_idle()
        col_map = {"NORMAL": C["normal"], "WARNING": C["warning"],
                   "CRITICAL": C["critical"]}
        color = col_map.get(severity, C["accent"])
        self.severity_lbl.config(text=severity, fg=color)

    def append_alert(self, ts: str, msg: str, level: str = "INFO"):
        col_map = {"INFO": C["text"], "WARN": C["warning"], "ERROR": C["critical"]}
        self.alert_text.config(state=tk.NORMAL)
        self.alert_text.insert(tk.END, f"[{ts}] [{level:5s}] {msg}\n",
                                level.lower())
        self.alert_text.tag_configure("warn",  foreground=C["warning"])
        self.alert_text.tag_configure("error", foreground=C["critical"])
        self.alert_text.tag_configure("info",  foreground=C["text"])
        self.alert_text.see(tk.END)
        self.alert_text.config(state=tk.DISABLED)

class FPGAInsightApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("FPGA-Insight  —  AI-Driven FPGA Monitor")
        self.configure(bg=C["bg"])
        self.geometry("1000x780")
        self.minsize(800, 600)
        self.fpga     = FPGASimulator()
        self.detector = AnomalyDetector()
        self.parser   = NLPParser(self.fpga)
        self._severity    = "TRAINING"
        self._last_anom   = False
        self._anom_streak = 0

        self._build_ui()
        self._schedule_update()
    def _build_ui(self):
        title_frm = tk.Frame(self, bg=C["panel"], pady=8)
        title_frm.pack(fill=tk.X)
        tk.Label(title_frm,
                 text="⬡  FPGA-Insight",
                 font=("Segoe UI", 16, "bold"),
                 fg=C["accent"], bg=C["panel"]).pack(side=tk.LEFT, padx=16)
        tk.Label(title_frm,
                 text="AI-Driven FPGA Register Monitor & Anomaly Detector",
                 font=("Segoe UI", 10),
                 fg=C["text_dim"], bg=C["panel"]).pack(side=tk.LEFT)
        tk.Label(title_frm,
                 text="Isolation Forest  •  Python  •  Tkinter  •  Matplotlib",
                 font=("Segoe UI", 8),
                 fg=C["border"], bg=C["panel"]).pack(side=tk.RIGHT, padx=16)
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)
        self.status_bar = StatusBar(self, self.fpga)
        self.status_bar.pack(fill=tk.X)
        style = ttk.Style()
        style.configure("Dark.TNotebook",      background=C["bg"],    borderwidth=0)
        style.configure("Dark.TNotebook.Tab",  background=C["panel"], foreground=C["text_dim"],
                        padding=[14, 6], font=FONT_LABEL)
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", C["bg"])],
                  foreground=[("selected", C["accent"])])

        self.nb = ttk.Notebook(self, style="Dark.TNotebook")
        self.nb.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self.reg_tab  = RegisterTab(self.nb, self.fpga, self.parser, self._console)
        self.sig_tab  = SignalTab(self.nb, self.fpga)
        self.ai_tab   = AITab(self.nb, self.detector)

        self.nb.add(self.reg_tab,  text="  Register Map  ")
        self.nb.add(self.sig_tab,  text="  Signal Monitor  ")
        self.nb.add(self.ai_tab,   text="  AI Diagnostics  ")
        cmd_frame = tk.Frame(self, bg=C["panel"], pady=6)
        cmd_frame.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(cmd_frame, text=">_", font=FONT_MONO,
                 fg=C["accent"], bg=C["panel"]).pack(side=tk.LEFT, padx=(10, 4))
        self._cmd_var = tk.StringVar()
        cmd_entry = tk.Entry(cmd_frame, textvariable=self._cmd_var,
                             font=FONT_MONO, bg=C["border"], fg=C["text"],
                             insertbackground=C["accent"], relief=tk.FLAT,
                             width=60)
        cmd_entry.pack(side=tk.LEFT, padx=4, ipady=4)
        cmd_entry.bind("<Return>", self._on_cmd)
        tk.Button(cmd_frame, text="Run", font=FONT_LABEL,
                  bg=C["accent"], fg=C["bg"], relief=tk.FLAT, padx=10,
                  command=self._on_cmd).pack(side=tk.LEFT, padx=4)
        tk.Button(cmd_frame, text="Help", font=FONT_LABEL,
                  bg=C["border"], fg=C["text"], relief=tk.FLAT, padx=8,
                  command=lambda: self._run_cmd("help")).pack(side=tk.LEFT, padx=2)
        tk.Button(cmd_frame, text="Inject Fault", font=FONT_LABEL,
                  bg=C["accent2"], fg=C["bg"], relief=tk.FLAT, padx=8,
                  command=lambda: self._run_cmd("inject anomaly")).pack(side=tk.RIGHT, padx=4)
        tk.Button(cmd_frame, text="Clear Fault", font=FONT_LABEL,
                  bg=C["normal"], fg=C["bg"], relief=tk.FLAT, padx=8,
                  command=lambda: self._run_cmd("clear anomaly")).pack(side=tk.RIGHT, padx=4)
        self.console = tk.Text(self, height=5, font=FONT_MONO,
                               bg=C["bg"], fg=C["text"], relief=tk.FLAT,
                               state=tk.DISABLED, insertbackground=C["accent"])
        self.console.pack(fill=tk.X, side=tk.BOTTOM, padx=6, pady=(0, 2))
        tk.Frame(self, bg=C["border"], height=1).pack(side=tk.BOTTOM, fill=tk.X)

        self._console("  FPGA-Insight ready. Type 'help' for commands. Press [Inject Fault] to demo AI detection.", level="INFO")
    def _console(self, msg: str, error: bool = False, level: str = ""):
        ts = datetime.now().strftime("%H:%M:%S")
        color = C["critical"] if error else C["text"]
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, f"[{ts}]  {msg}\n")
        last_line = f"{int(self.console.index('end').split('.')[0]) - 1}.0"
        self.console.tag_add("last", last_line, tk.END)
        self.console.tag_configure("last", foreground=color)
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)
    def _on_cmd(self, event=None):
        raw = self._cmd_var.get().strip()
        if not raw:
            return
        self._cmd_var.set("")
        self._run_cmd(raw)

    def _run_cmd(self, raw: str):
        result = self.parser.parse(raw)
        msg = result.get("message", "")
        ok  = result.get("success", False)
        self._console(f"  > {raw}", level="CMD")
        for line in msg.splitlines():
            self._console(f"  {line}", error=not ok)
        if result.get("cmd") == "export":
            self.reg_tab._export_csv()
        if result.get("cmd") in ("set", "reset"):
            self.reg_tab.refresh()
    def _schedule_update(self):
        self._update()
        self.after(UPDATE_MS, self._schedule_update)

    def _update(self):
        self.fpga.tick_sensors()
        self.status_bar.refresh()
        sigs = self.fpga.get_signals()
        if self.nb.index(self.nb.select()) == 1:
            self.sig_tab.update_plot(sigs)
        features = self.fpga.get_feature_vector()
        if not self.detector.trained:
            self.detector.add_training_sample(features)
        is_anom, score, severity = self.detector.score(features)
        self._severity = severity
        scores, labels = self.detector.get_score_history()
        progress = self.detector.training_progress()
        if self.nb.index(self.nb.select()) == 2:
            self.ai_tab.update_plot(scores, labels, severity, progress)
        ts = datetime.now().strftime("%H:%M:%S")
        if is_anom and not self._last_anom:
            self._anom_streak = 1
            msg = f"Anomaly detected! Score={score:.3f}"
            self.ai_tab.append_alert(ts, msg, "WARN")
            self._console(f"  ⚠  {msg}", error=True)
            self.detector.log_alert(ts, msg)
        elif is_anom:
            self._anom_streak += 1
            if self._anom_streak % 8 == 0:
                lvl = "error" if score < -0.45 else "warn"
                msg = f"Anomaly persisting — streak {self._anom_streak}  Score={score:.3f}"
                self.ai_tab.append_alert(ts, msg, "ERROR" if lvl == "error" else "WARN")
        elif self._last_anom and not is_anom:
            self.ai_tab.append_alert(ts, "Returned to normal operation.", "INFO")
            self._console("  ✔  FPGA returned to normal.", error=False)
            self._anom_streak = 0

        self._last_anom = is_anom
