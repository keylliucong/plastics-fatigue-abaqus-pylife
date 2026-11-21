"""ODB→pyLife 桌面桥接工具（项目层级 GUI，tkinter，无需额外依赖）。

使用场景（PRD 方案 A）：用户在 Abaqus 提交作业生成 ODB 后，打开本工具：
  ① 文件与环境：配置 abaqus.bat、选择 ODB、测试连接并扫描
  ② 数据选择：分析步、区域、应力分量、帧范围
  ③ 预览与单位：源应力/时间单位、应力基底确认、预览材料点历程与校验汇总
  ④ 疲劳参数：查看已拟合曲线 JSON（k1/ND/SD、试验区间、参考 R）
  ⑤ 校验与导出：探测→提取→结构校验→发布桥接包（重复导出默认拒绝）
  ⑥ 计算与出图：对桥接包强制校验+单位换算后算损伤，输出 per_point.csv / summary.json / PNG

GUI 运行在与 Abaqus 隔离的 Python（项目 venv）。ODB 读取通过 subprocess 调用
`abaqus python bridge/odb_probe.py` 与 `odb_extract.py` 完成，GUI 不直接加载 odbAccess。
损伤计算需要该 Python 环境装有 pyLife；出图另需 matplotlib。

启动（Windows 可双击）：
  bridge\\start_gui.bat
或
  <venv>/Scripts/pythonw.exe bridge/gui.py
"""

from __future__ import annotations

import csv
import json
import queue
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent

STRESS_UNITS = ["MPa", "Pa", "kPa", "GPa"]
TIME_UNITS = ["s", "ms"]
TIME_MEANINGS = ["physical", "pseudo", "unknown"]
BASES = ["unknown", "global", "local"]


def _default_analysis_python() -> str:
    """pythonw 下起子进程时优先用同目录 python.exe，保证 stdout 可捕获。"""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = Path(exe).with_name("python.exe")
        if cand.exists():
            return str(cand)
    return exe


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ODB → pyLife 桥接工具（项目层级，PRD v1）")
        self.geometry("940x700")
        self.abaqus = tk.StringVar(value=r"E:\SIMULIA\Commands\abaqus.bat")
        self.odb = tk.StringVar()
        self.step = tk.StringVar()
        self.region = tk.StringVar(value="")
        self.component = tk.StringVar(value="S11")
        self.frames = tk.StringVar(value="0:-1")
        self.src_stress_unit = tk.StringVar(value="MPa")
        self.src_time_unit = tk.StringVar(value="s")
        self.time_meaning = tk.StringVar(value="physical")
        self.basis = tk.StringVar(value="unknown")
        self.curve_json = tk.StringVar(value="")
        self.out_dir = tk.StringVar()
        self.analysis_python = tk.StringVar(value=_default_analysis_python())
        self.damage_dir = tk.StringVar(value="")
        self.inventory = None
        self.msgq = queue.Queue()
        self._build()
        self.after(150, self._drain)

    # ---------- UI ----------
    def _build(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.pages = {}
        for name, builder in [
            ("① 文件与环境", self._page_files),
            ("② 数据选择", self._page_select),
            ("③ 预览与单位", self._page_units),
            ("④ 疲劳参数", self._page_curve),
            ("⑤ 校验与导出", self._page_export),
            ("⑥ 计算与出图", self._page_compute),
        ]:
            f = ttk.Frame(nb)
            nb.add(f, text=name)
            builder(f)
            self.pages[name] = f

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", side="bottom", padx=8, pady=6)
        ttk.Button(bottom, text="保存工程配置", command=self._save_config).pack(side="left", padx=4)
        ttk.Button(bottom, text="打开工程配置", command=self._load_config).pack(side="left", padx=4)
        self.status = tk.StringVar(value="就绪")
        ttk.Label(bottom, textvariable=self.status, foreground="#444").pack(side="left", padx=12)

    def _row(self, parent, label, var, browse=None, row=0):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=5)
        ttk.Entry(parent, textvariable=var, width=62).grid(row=row, column=1, sticky="w", padx=4, pady=5)
        if browse:
            ttk.Button(parent, text="浏览…", command=lambda: browse(var)).grid(
                row=row, column=2, sticky="w", padx=4, pady=5)

    def _combo(self, parent, label, var, values, row=0):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=5)
        ttk.Combobox(parent, textvariable=var, values=values, state="readonly",
                     width=18).grid(row=row, column=1, sticky="w", padx=4, pady=5)

    def _pick_file(self, var, types):
        p = filedialog.askopenfilename(filetypes=types)
        if p:
            var.set(p)

    def _pick_dir(self, var):
        p = filedialog.askdirectory()
        if p:
            var.set(p)

    def _page_files(self, f):
        self._row(f, "Abaqus 启动程序:", self.abaqus,
                  lambda v: self._pick_file(v, [("abaqus.bat", "abaqus.bat"), ("all", "*.*")]), 0)
        self._row(f, "ODB 文件:", self.odb,
                  lambda v: self._pick_file(v, [("ODB", "*.odb"), ("all", "*.*")]), 1)
        ttk.Button(f, text="测试连接并扫描 ODB", command=self._scan).grid(
            row=2, column=1, sticky="w", padx=4, pady=10)
        self.scan_out = tk.Text(f, height=18, width=100)
        self.scan_out.grid(row=3, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
        f.rowconfigure(3, weight=1)

    def _page_select(self, f):
        self._row(f, "分析步:", self.step, row=0)
        self._row(f, "区域(实例/单元集, 空=全部):", self.region, row=1)
        self._row(f, "应力分量:", self.component, row=2)
        self._row(f, "帧范围(start:end):", self.frames, row=3)
        ttk.Button(f, text="从扫描结果填入默认分析步", command=self._fill_steps).grid(
            row=4, column=1, sticky="w", padx=4, pady=8)
        ttk.Label(f, text="说明：实体保留全部积分点；壳截面点按 ODB 实际编号保留，不平均、不取最大值。",
                  foreground="#a00").grid(row=5, column=0, columnspan=3, sticky="w", padx=6)

    def _page_units(self, f):
        self._combo(f, "源应力单位:", self.src_stress_unit, STRESS_UNITS, row=0)
        self._combo(f, "源时间单位:", self.src_time_unit, TIME_UNITS, row=1)
        self._combo(f, "时间含义:", self.time_meaning, TIME_MEANINGS, row=2)
        self._combo(f, "应力基底:", self.basis, BASES, row=3)
        ttk.Label(f, text="导出保留源数值，计算时按源单位换算为 MPa；单位未确认将拒绝计算。\n"
                          "基底 unknown 时壳/梁截面点不能直接算损伤；实体全局分量可声明 global。",
                  foreground="#a00", justify="left").grid(
            row=4, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))
        ttk.Button(f, text="预览材料点历程与校验汇总", command=self._preview).grid(
            row=5, column=1, sticky="w", padx=4, pady=6)
        self.preview_out = tk.Text(f, height=14, width=100)
        self.preview_out.grid(row=6, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
        f.rowconfigure(6, weight=1)

    def _page_curve(self, f):
        self._row(f, "已拟合曲线 JSON:", self.curve_json,
                  lambda v: self._pick_file(v, [("JSON", "*.json"), ("all", "*.*")]), 0)
        ttk.Label(f, text="曲线须来自匹配牌号/工艺的试验拟合；⑥ 用它计算损伤，并检查幅值/应力比是否落在试验区间。",
                  foreground="#a00").grid(row=1, column=0, columnspan=3, sticky="w", padx=6)
        ttk.Button(f, text="查看曲线参数", command=self._show_curve).grid(
            row=2, column=1, sticky="w", padx=4, pady=8)
        self.curve_out = tk.Text(f, height=14, width=100)
        self.curve_out.grid(row=3, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
        f.rowconfigure(3, weight=1)

    def _page_export(self, f):
        self._row(f, "输出目录:", self.out_dir, lambda v: self._pick_dir(v), 0)
        ttk.Button(f, text="执行：探测 → 提取 → 独立重读核对 → 导出", command=self._export).grid(
            row=1, column=1, sticky="w", padx=4, pady=10)
        ttk.Label(f, text="同一目录重复导出默认拒绝（防止旧行追加造成行数与清单不符）；"
                          "确认覆盖后会先清掉旧分块再发布。",
                  foreground="#a00").grid(row=2, column=0, columnspan=3,
                                          sticky="w", padx=6, pady=(0, 4))
        self.export_out = tk.Text(f, height=16, width=100)
        self.export_out.grid(row=3, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
        f.rowconfigure(3, weight=1)

    def _page_compute(self, f):
        self._row(f, "分析 Python(需 pyLife):", self.analysis_python,
                  lambda v: self._pick_file(v, [("Python", "python*"), ("all", "*.*")]), 0)
        self._row(f, "损伤输出目录:", self.damage_dir, lambda v: self._pick_dir(v), 1)
        ttk.Label(f, text="使用 ⑤ 的桥接包与 ④ 的曲线；留空时输出到 桥接包/damage_results，图存 桥接包/figures。\n"
                          "计算入口会强制校验清单/缺帧/失效标记/单位/基底；出图另需 matplotlib。",
                  foreground="#a00", justify="left").grid(
            row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(0, 6))
        ttk.Button(f, text="① 校验桥接包", command=self._verify_bundle).grid(
            row=3, column=1, sticky="w", padx=4, pady=6)
        ttk.Button(f, text="② 计算损伤并出图", command=self._compute).grid(
            row=4, column=1, sticky="w", padx=4, pady=6)
        self.compute_out = tk.Text(f, height=16, width=100)
        self.compute_out.grid(row=5, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
        f.rowconfigure(5, weight=1)

    # ---------- actions ----------
    def _log(self, widget, text):
        widget.insert("end", text + "\n")
        widget.see("end")
        self.update_idletasks()

    def _run_abaqus_python(self, script: str, args: list[str]):
        cmd = [self.abaqus.get(), "python", str(script), *args]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    def _scan(self):
        odb = self.odb.get()
        if not odb or not Path(odb).exists():
            messagebox.showerror("错误", "请先选择存在的 ODB 文件")
            return
        self.status.set("正在扫描 ODB…")
        inv_path = PROJECT / "data" / "derived" / "gui_inventory.json"
        inv_path.parent.mkdir(parents=True, exist_ok=True)
        code, out = self._run_abaqus_python(
            str(HERE / "odb_probe.py"), [odb, "--out", str(inv_path)])
        self._log(self.scan_out, out[-4000:])
        if code != 0 or not inv_path.exists():
            self.status.set("扫描失败")
            messagebox.showerror("扫描失败", "请查看输出；确认 abaqus.bat 路径与 ODB 兼容性")
            return
        self.inventory = json.loads(inv_path.read_text(encoding="utf-8"))
        self.status.set(f"扫描完成: {len(self.inventory['steps'])} 步骤")
        self._fill_steps()

    def _fill_steps(self):
        if not self.inventory:
            messagebox.showinfo("提示", "请先在『文件与环境』扫描 ODB")
            return
        names = [s["name"] for s in self.inventory["steps"]]
        if names:
            self.step.set(names[0])

    def _units_meta(self):
        meaning = {"physical": "physical", "pseudo": "pseudo", "unknown": "unknown"}.get(
            self.time_meaning.get(), "unknown")
        return {"units": {"stress_source": self.src_stress_unit.get(),
                          "stress_standard": "MPa",
                          "time_source": self.src_time_unit.get(),
                          "time_meaning": meaning}}

    def _extract_args(self, odb, out_dir):
        """构造 odb_extract 参数；region 为空时不传该选项（argparse 不接受空串）。"""
        args = [odb, self.step.get()]
        region = self.region.get().strip()
        if region:
            args += ["--region", region]
        args += ["--component", self.component.get(),
                 "--frames", self.frames.get(),
                 "--basis", self.basis.get(),
                 "--overwrite",
                 "--out", str(out_dir),
                 "--meta", str(PROJECT / "data" / "derived" / "gui_units.json")]
        return args

    def _write_units_meta(self) -> Path:
        meta_path = PROJECT / "data" / "derived" / "gui_units.json"
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(self._units_meta()), encoding="utf-8")
        return meta_path

    def _preview(self):
        if not self.inventory or not self.step.get():
            messagebox.showinfo("提示", "请先扫描并选择分析步")
            return
        self.status.set("预览中…")
        odb = self.odb.get()
        bundle = PROJECT / "data" / "derived" / "gui_preview"
        self._write_units_meta()
        code, out = self._run_abaqus_python(str(HERE / "odb_extract.py"),
                                              self._extract_args(odb, bundle))
        self._log(self.preview_out, out[-3000:])
        if code != 0 or not (bundle / "fields").exists():
            self.status.set("预览失败")
            return
        try:
            from bundle_validation import validate_bundle
            report = validate_bundle(bundle, component=self.component.get())
        except Exception as exc:  # noqa: BLE001 - GUI 必须把异常显示给用户
            self._log(self.preview_out, f"校验无法完成: {exc}")
            self.status.set("预览校验失败")
            return

        units = report["units"]
        basis = report["basis"]
        stats = report["stats"]
        self._log(self.preview_out,
                  f"—— 校验汇总 ——\n点数={report['n_points']}  "
                  f"帧={report['n_frames_expected']}  行={report['rows']}  "
                  f"分量={report['component']}")
        self._log(self.preview_out,
                  f"源应力单位={units['stress_source']} → MPa 系数="
                  f"{units['stress_scale_to_MPa']}  "
                  f"源时间单位={units['time_source']} 基底={basis['coordinate_system']}")
        self._log(self.preview_out,
                  f"分量范围(源单位)=[{stats['component_min']}, {stats['component_max']}]  "
                  f"失效行={stats['invalid_rows']}  非有限行={stats['nonfinite_rows']}  "
                  f"缺帧点={stats['n_points_missing_frames']}  "
                  f"失效点={stats['n_points_invalid_frames']}")
        if report["errors"]:
            for e in report["errors"][:8]:
                self._log(self.preview_out, f"[校验失败] {e}")
            self.status.set("预览完成，但校验未通过")
            return
        if units["stress_scale_to_MPa"] is None:
            self._log(self.preview_out, "[警告] 单位未确认，⑥ 将拒绝计算")
        if not basis["resolved"] and basis["shell_section_points"]:
            self._log(self.preview_out, "[警告] 壳/梁截面点基底未解析，⑥ 将拒绝计算")

        self._log(self.preview_out, "—— 材料点样例（最多 3 点 × 8 帧，源单位）——")
        for pid, rows in self._preview_samples(bundle).items():
            self._log(self.preview_out, f"[{pid}]")
            for r in rows:
                self._log(self.preview_out,
                          f"  frame={r['frame_id']:>4}  time={r['step_time']:>10}  "
                          f"{self.component.get()}={r.get(self.component.get(), ''):>14}  "
                          f"valid={r['valid']}")
        self.status.set("预览完成")

    @staticmethod
    def _preview_samples(bundle: Path) -> dict:
        samples: dict[str, list] = {}
        for f in sorted((bundle / "fields").glob("*.csv")):
            with open(f, newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    pid = row["point_id"]
                    if pid not in samples and len(samples) >= 3:
                        continue
                    rows = samples.setdefault(pid, [])
                    if len(rows) < 8:
                        rows.append(row)
                    if len(samples) >= 3 and all(len(v) >= 8 for v in samples.values()):
                        return samples
        return samples

    def _show_curve(self):
        p = self.curve_json.get()
        if not p or not Path(p).exists():
            messagebox.showinfo("提示", "请先选择曲线 JSON")
            return
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        missing = [k for k in ("k_1", "ND", "SD") if d.get(k) is None]
        if missing:
            self._log(self.curve_out, f"[错误] 曲线缺少参数: {missing}，不能用于计算")
            return
        for k in ("material", "k_1", "ND", "SD", "k_2", "R", "frequency",
                  "finite_load_levels", "source_csv"):
            if k in d:
                self._log(self.curve_out, f"{k}: {d[k]}")
        if d.get("source_csv") and not Path(str(d["source_csv"])).exists():
            self._log(self.curve_out, "[警告] source_csv 在本机不存在，出图将跳过 S-N 图")

    def _export(self):
        if not self.inventory or not self.step.get():
            messagebox.showinfo("提示", "请先扫描并选择分析步")
            return
        out = self.out_dir.get()
        if not out:
            messagebox.showinfo("提示", "请选择输出目录")
            return
        outp = Path(out)
        has_old = (outp / "manifest.json").exists() or (
            (outp / "fields").is_dir() and any((outp / "fields").glob("part-*.csv")))
        if has_old and not messagebox.askyesno(
                "覆盖确认", f"目录中已有桥接包：\n{outp}\n\n覆盖会替换旧包，是否继续？"):
            return
        self.status.set("导出中…")
        odb = self.odb.get()
        outp.mkdir(parents=True, exist_ok=True)
        self._write_units_meta()
        # 提取（--overwrite 已在 _extract_args 中，发布前会自动校验）
        code, msg = self._run_abaqus_python(str(HERE / "odb_extract.py"),
                                              self._extract_args(odb, outp))
        self._log(self.export_out, msg[-3000:])
        if code != 0:
            self.status.set("导出失败")
            messagebox.showerror("导出失败", "请查看输出（校验不过时不会发布半成品包）")
            return
        # 独立重读核对（用当前 Python，与 Abaqus 进程隔离）
        verify = subprocess.run([self.analysis_python.get(),
                                 str(HERE / "run_bridge_flow.py"),
                                 "--verify-only", str(outp)],
                                capture_output=True, text=True)
        self._log(self.export_out, (verify.stdout or "") + (verify.stderr or ""))
        if verify.returncode == 0:
            self.status.set("导出并核对完成")
            messagebox.showinfo("完成",
                                f"桥接包已导出并通过核对:\n{outp}\n\n"
                                "可到『⑥ 计算与出图』执行损伤计算。")
        else:
            self.status.set("核对未通过")

    def _verify_bundle(self):
        out = self.out_dir.get()
        if not out or not (Path(out) / "manifest.json").exists():
            messagebox.showinfo("提示", "请先在 ⑤ 导出桥接包，或选择包含 manifest.json 的目录")
            return
        proc = subprocess.run([self.analysis_python.get(),
                               str(HERE / "run_bridge_flow.py"),
                               "--verify-only", out],
                              capture_output=True, text=True)
        self._log(self.compute_out, (proc.stdout or "") + (proc.stderr or ""))
        self.status.set("校验通过" if proc.returncode == 0 else "校验未通过")
        if proc.returncode != 0:
            messagebox.showwarning("校验未通过", "详见输出；未通过前不要使用该包计算")

    def _compute(self):
        out = self.out_dir.get()
        curve = self.curve_json.get()
        if not out or not (Path(out) / "manifest.json").exists():
            messagebox.showinfo("提示", "请先在 ⑤ 导出桥接包")
            return
        if not curve or not Path(curve).exists():
            messagebox.showinfo("提示", "请在 ④ 选择已拟合曲线 JSON")
            return
        bundle = Path(out)
        damage = Path(self.damage_dir.get().strip() or (bundle / "damage_results"))
        figures = damage.parent / "figures"
        py = self.analysis_python.get()
        self.status.set("计算损伤中…")
        cmd = [py, str(PROJECT / "fatigue" / "analyze_real_bundle.py"),
               str(bundle), "--curve", curve,
               "--component", self.component.get(), "--out", str(damage)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        self._log(self.compute_out, (proc.stdout or "") + (proc.stderr or ""))
        if proc.returncode != 0:
            self.status.set("损伤计算未完成")
            messagebox.showerror("损伤计算未完成",
                                 "详见输出。常见原因：单位未确认、缺帧/失效点被排除、"
                                 "桥接包校验失败，或该 Python 未安装 pyLife。")
            return

        sn_csv = ""
        try:
            sn_csv = str(json.loads(Path(curve).read_text(encoding="utf-8"))
                         .get("source_csv") or "")
        except Exception:  # noqa: BLE001
            sn_csv = ""
        plot_cmd = [py, str(PROJECT / "fatigue" / "plot_results.py"),
                    "--history", str(bundle), "--damage", str(damage),
                    "--out", str(figures)]
        if sn_csv and Path(sn_csv).exists():
            plot_cmd += ["--sn-curve", curve, "--sn-data", sn_csv]
        plot = subprocess.run(plot_cmd, capture_output=True, text=True)
        self._log(self.compute_out, (plot.stdout or "") + (plot.stderr or ""))
        if plot.returncode == 0:
            self.status.set("计算与出图完成")
            messagebox.showinfo("完成",
                                f"损伤结果: {damage}\n图表: {figures}")
        else:
            self.status.set("损伤完成，出图失败")
            messagebox.showwarning(
                "出图失败",
                "损伤 CSV 已生成；出图失败通常是该 Python 缺 matplotlib 或 S-N 数据缺失。\n"
                f"结果目录: {damage}")

    def _save_config(self):
        d = {"abaqus": self.abaqus.get(), "odb": self.odb.get(), "step": self.step.get(),
             "region": self.region.get(), "component": self.component.get(),
             "frames": self.frames.get(), "units": self._units_meta(),
             "basis": self.basis.get(), "curve_json": self.curve_json.get(),
             "out_dir": self.out_dir.get(),
             "analysis_python": self.analysis_python.get(),
             "damage_dir": self.damage_dir.get()}
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                         filetypes=[("JSON", "*.json")])
        if p:
            Path(p).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_config(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not p:
            return
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for k, var in [("abaqus", self.abaqus), ("odb", self.odb), ("step", self.step),
                       ("region", self.region), ("component", self.component),
                       ("frames", self.frames), ("curve_json", self.curve_json),
                       ("out_dir", self.out_dir), ("basis", self.basis),
                       ("analysis_python", self.analysis_python),
                       ("damage_dir", self.damage_dir)]:
            if k in d and d[k] is not None:
                var.set(d[k])
        u = d.get("units", {}).get("units", {})
        if u:
            self.src_stress_unit.set(u.get("stress_source", "MPa"))
            self.src_time_unit.set(u.get("time_source", "s"))
            self.time_meaning.set(u.get("time_meaning", "unknown"))

    def _drain(self):
        try:
            while True:
                self.msgq.get_nowait()
        except queue.Empty:
            pass
        self.after(150, self._drain)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
