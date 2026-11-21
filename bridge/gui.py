"""ODB→pyLife 桌面桥接工具（项目层级 GUI，tkinter，无需额外依赖）。

使用场景（PRD 方案 A）：用户在 Abaqus 提交作业生成 ODB 后，打开本工具：
  ① 文件与环境：配置 abaqus.bat、选择 ODB、测试连接并扫描
  ② 数据选择：分析步、区域、应力分量、帧范围
  ③ 预览与单位：源应力/时间单位确认、预览固定材料点历程
  ④ 疲劳参数：录入或用已拟合曲线 JSON（首版不计算损伤）
  ⑤ 校验与导出：执行探测→提取→独立重读核对→导出桥接包

GUI 运行在与 Abaqus 隔离的 Python（项目 venv）。ODB 读取通过 subprocess 调用
`abaqus python bridge/odb_probe.py` 与 `odb_extract.py` 完成，GUI 不直接加载 odbAccess。

运行：
  <venv>/Scripts/pythonw.exe bridge/gui.py
  或 <venv>/Scripts/python.exe bridge/gui.py
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ODB → pyLife 桥接工具（项目层级，PRD v1）")
        self.geometry("880x620")
        self.abaqus = tk.StringVar(value=r"E:\SIMULIA\Commands\abaqus.bat")
        self.odb = tk.StringVar()
        self.step = tk.StringVar()
        self.region = tk.StringVar(value="")
        self.component = tk.StringVar(value="S11")
        self.frames = tk.StringVar(value="0:-1")
        self.src_stress_unit = tk.StringVar(value="MPa")
        self.src_time_unit = tk.StringVar(value="s")
        self.time_meaning = tk.StringVar(value="physical")
        self.curve_json = tk.StringVar(value="")
        self.out_dir = tk.StringVar()
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
        self.scan_out = tk.Text(f, height=18, width=96)
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
        self._row(f, "源应力单位:", self.src_stress_unit, row=0)
        ttk.Label(f, text="  目标标准应力单位：MPa").grid(row=1, column=1, sticky="w")
        self._row(f, "源时间单位:", self.src_time_unit, row=2)
        ttk.Label(f, text="  时间含义：physical=物理时间 / pseudo=加载参数 / unknown=未确认").grid(
            row=3, column=1, sticky="w")
        self._row(f, "时间含义:", self.time_meaning, row=4)
        ttk.Button(f, text="预览选中材料点历程（第一步）", command=self._preview).grid(
            row=5, column=1, sticky="w", padx=4, pady=8)
        self.preview_out = tk.Text(f, height=14, width=96)
        self.preview_out.grid(row=6, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
        f.rowconfigure(6, weight=1)

    def _page_curve(self, f):
        self._row(f, "已拟合曲线 JSON(可选):", self.curve_json,
                  lambda v: self._pick_file(v, [("JSON", "*.json"), ("all", "*.*")]), 0)
        ttk.Label(f, text="首版只关联一条曲线、不计算损伤。曲线须来自匹配牌号/工艺的试验拟合。",
                  foreground="#a00").grid(row=1, column=0, columnspan=3, sticky="w", padx=6)
        ttk.Button(f, text="查看曲线参数", command=self._show_curve).grid(
            row=2, column=1, sticky="w", padx=4, pady=8)
        self.curve_out = tk.Text(f, height=14, width=96)
        self.curve_out.grid(row=3, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
        f.rowconfigure(3, weight=1)

    def _page_export(self, f):
        self._row(f, "输出目录:", self.out_dir, lambda v: self._pick_dir(v), 0)
        ttk.Button(f, text="执行：探测 → 提取 → 独立重读核对 → 导出", command=self._export).grid(
            row=1, column=1, sticky="w", padx=4, pady=10)
        self.export_out = tk.Text(f, height=18, width=96)
        self.export_out.grid(row=2, column=0, columnspan=3, padx=6, pady=6, sticky="nsew")
        f.rowconfigure(2, weight=1)

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
                 "--out", str(out_dir),
                 "--meta", str(PROJECT / "data" / "derived" / "gui_units.json")]
        return args

    def _preview(self):
        if not self.inventory or not self.step.get():
            messagebox.showinfo("提示", "请先扫描并选择分析步")
            return
        self.status.set("预览中…")
        odb = self.odb.get()
        bundle = PROJECT / "data" / "derived" / "gui_preview"
        meta_path = PROJECT / "data" / "derived" / "gui_units.json"
        meta_path.write_text(json.dumps(self._units_meta()), encoding="utf-8")
        code, out = self._run_abaqus_python(str(HERE / "odb_extract.py"),
                                              self._extract_args(odb, bundle))
        self._log(self.preview_out, out[-3000:])
        if code != 0 or not (bundle / "fields").exists():
            self.status.set("预览失败")
            return
        fields = sorted((bundle / "fields").glob("*.csv"))
        if not fields:
            return
        import csv
        rows = list(csv.DictReader(open(fields[0])))
        comp = self.component.get()
        sample = [r for r in rows if r["point_id"] == rows[0]["point_id"]][:12]
        for r in sample:
            self._log(self.preview_out,
                      f"frame={r['frame_id']:>3}  time={r['step_time']:>8}  "
                      f"{comp}={r.get(comp, ''):>12}  valid={r['valid']}")
        self.status.set("预览完成")

    def _show_curve(self):
        p = self.curve_json.get()
        if not p or not Path(p).exists():
            messagebox.showinfo("提示", "请先选择曲线 JSON")
            return
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for k in ("material", "k_1", "ND", "SD", "k_2", "R", "frequency", "source_csv"):
            if k in d:
                self._log(self.curve_out, f"{k}: {d[k]}")

    def _export(self):
        if not self.inventory or not self.step.get():
            messagebox.showinfo("提示", "请先扫描并选择分析步")
            return
        out = self.out_dir.get()
        if not out:
            messagebox.showinfo("提示", "请选择输出目录")
            return
        self.status.set("导出中…")
        odb = self.odb.get()
        outp = Path(out)
        outp.mkdir(parents=True, exist_ok=True)
        meta_path = PROJECT / "data" / "derived" / "gui_units.json"
        meta_path.write_text(json.dumps(self._units_meta()), encoding="utf-8")
        # 提取
        code, msg = self._run_abaqus_python(str(HERE / "odb_extract.py"),
                                              self._extract_args(odb, outp))
        self._log(self.export_out, msg[-3000:])
        if code != 0:
            self.status.set("导出失败")
            messagebox.showerror("导出失败", "请查看输出")
            return
        # 独立重读核对（用当前 Python，与 Abaqus 进程隔离）
        verify = subprocess.run([os.sys.executable, str(HERE / "run_bridge_flow.py"),
                                 "--verify-only", str(outp)],
                                capture_output=True, text=True)
        self._log(self.export_out, (verify.stdout or "") + (verify.stderr or ""))
        if verify.returncode == 0:
            self.status.set("导出并核对完成")
            messagebox.showinfo("完成", f"桥接包已导出并通过核对:\n{outp}")
        else:
            self.status.set("核对未通过")

    def _save_config(self):
        d = {"abaqus": self.abaqus.get(), "odb": self.odb.get(), "step": self.step.get(),
             "region": self.region.get(), "component": self.component.get(),
             "frames": self.frames.get(), "units": self._units_meta(),
             "curve_json": self.curve_json.get(), "out_dir": self.out_dir.get()}
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
                       ("out_dir", self.out_dir)]:
            if k in d:
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
