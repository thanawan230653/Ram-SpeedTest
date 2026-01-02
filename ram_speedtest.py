#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ram_speedtest.py  —  RAM SpeedTest (Speedtest-like GUI)

แนวคิดเหมือน speedtest.net แต่ทดสอบ "ความเร็ว RAM"
- กดปุ่ม GO แล้วโปรแกรมจะพยายามใช้ RAM ให้ใกล้ 100% (จัดสรรเกือบทั้งหมด)
- เลือกเวลาเป็น "นาที" (ไม่ใช้วินาที)
- สรุปผล Write/Read/Total GB/s + การใช้ RAM

⚠️ คำเตือน: การใช้ RAM เกือบทั้งหมดอาจทำให้เครื่องหน่วง/ค้าง,
โปรแกรมอื่นปิดตัว, หรือมีการ swap/pagefile หนักมากได้
คุณสั่งให้ทำแบบนี้แล้ว — ใช้งานด้วยความระวัง
"""

import os
import sys
import time
import math
import queue
import ctypes
import platform
import threading
import datetime
import zlib
import tkinter as tk
from tkinter import ttk, messagebox

APP_NAME = "ram speedtest"
GiB = 1024 ** 3
MiB = 1024 ** 2

# ---------------------------- System / Memory helpers ----------------------------

def _try_import_psutil():
    try:
        import psutil  # type: ignore
        return psutil
    except Exception:
        return None

PSUTIL = _try_import_psutil()


def bytes_to_human(n: int) -> str:
    if n is None:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    f = float(n)
    i = 0
    while f >= 1024.0 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    if i == 0:
        return f"{int(f)} {units[i]}"
    return f"{f:.2f} {units[i]}"


def get_basic_specs() -> dict:
    info = {
        "OS": f"{platform.system()} {platform.release()}",
        "Machine": platform.machine(),
        "Processor": platform.processor() or "-",
        "CPU Threads": os.cpu_count() or "-",
        "Python": sys.version.split()[0],
    }
    if platform.system().lower() == "windows":
        try:
            import winreg  # type: ignore
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                val, _ = winreg.QueryValueEx(k, "ProcessorNameString")
                if val:
                    info["Processor"] = val
        except Exception:
            pass
    return info


def get_virtual_memory() -> dict:
    """Returns dict: total, available, used, percent"""
    if PSUTIL:
        vm = PSUTIL.virtual_memory()
        return {
            "total": int(vm.total),
            "available": int(vm.available),
            "used": int(vm.used),
            "percent": float(vm.percent),
        }

    sysname = platform.system().lower()
    if sysname == "windows":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        total = int(stat.ullTotalPhys)
        avail = int(stat.ullAvailPhys)
        used = total - avail
        percent = (used / total * 100.0) if total else 0.0
        return {"total": total, "available": avail, "used": used, "percent": percent}

    if os.path.exists("/proc/meminfo"):
        mt = ma = None
        with open("/proc/meminfo", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    mt = int(line.split()[1]) * 1024
                elif line.startswith("MemAvailable:"):
                    ma = int(line.split()[1]) * 1024
        if mt is not None and ma is not None:
            used = mt - ma
            percent = (used / mt * 100.0) if mt else 0.0
            return {"total": mt, "available": ma, "used": used, "percent": percent}

    return {"total": 0, "available": 0, "used": 0, "percent": 0.0}


def get_process_rss() -> int:
    """Best effort RSS bytes of current process"""
    if PSUTIL:
        try:
            p = PSUTIL.Process(os.getpid())
            return int(p.memory_info().rss)
        except Exception:
            pass

    if platform.system().lower() == "windows":
        try:
            psapi = ctypes.WinDLL("psapi")
            kernel32 = ctypes.WinDLL("kernel32")

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = kernel32.GetCurrentProcess()
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return int(counters.WorkingSetSize)
        except Exception:
            pass

    try:
        if os.path.exists("/proc/self/statm"):
            with open("/proc/self/statm", "r", encoding="utf-8") as f:
                parts = f.read().strip().split()
            if len(parts) >= 2:
                rss_pages = int(parts[1])
                page_size = os.sysconf("SC_PAGE_SIZE")
                return int(rss_pages * page_size)
    except Exception:
        pass

    return 0


def is_64bit_python() -> bool:
    return (ctypes.sizeof(ctypes.c_void_p) == 8)


def get_ctypes_memset():
    try:
        if platform.system().lower() == "windows":
            libc = ctypes.CDLL("msvcrt")
        else:
            libc = ctypes.CDLL(None)
        memset = libc.memset
        memset.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t)
        memset.restype = ctypes.c_void_p
        return memset
    except Exception:
        return None

MEMSET = get_ctypes_memset()


# ---------------------------- Benchmark core ----------------------------

class BenchmarkResult:
    def __init__(self):
        self.ok = False
        self.error = ""
        self.allocated_bytes = 0
        self.duration_s = 0.0
        self.write_bytes = 0
        self.read_bytes = 0
        self.write_time = 0.0
        self.read_time = 0.0
        self.checksum = 0
        self.loops = 0
        self.started_at = ""
        self.ended_at = ""

    @property
    def write_gbps(self) -> float:
        return (self.write_bytes / self.write_time / GiB) if self.write_time > 0 else 0.0

    @property
    def read_gbps(self) -> float:
        return (self.read_bytes / self.read_time / GiB) if self.read_time > 0 else 0.0

    @property
    def total_gbps(self) -> float:
        t = self.write_time + self.read_time
        b = self.write_bytes + self.read_bytes
        return (b / t / GiB) if t > 0 else 0.0


def choose_100_percent_allocation() -> int:
    """
    ผู้ใช้ต้องการ "100%" — ในทางปฏิบัติจะเว้นไว้เล็กน้อยเพื่อให้ OS ยังหายใจได้
    แต่เราจะพยายามให้ใกล้สุด ๆ
    """
    vm = get_virtual_memory()
    total = int(vm.get("total", 0))
    avail = int(vm.get("available", 0))

    if total <= 0:
        return 1 * GiB

    # Reserve เล็กมาก (เสี่ยงเครื่องค้างได้ แต่ตามที่ผู้ใช้ต้องการ)
    reserve = 128 * MiB

    # เป้าหมาย: total - reserve (อาจเกิน available ได้ ทำให้ swap/pagefile หนัก)
    target = max(256 * MiB, total - reserve)

    # ถ้า available น้อยมากจนจัดสรรไม่ได้ ให้ลดลง
    # (ยังคงพยายาม "ใกล้ 100% ของ available")
    hard_fallback = max(256 * MiB, avail - 64 * MiB) if avail > 0 else target
    return max(256 * MiB, min(target, hard_fallback if hard_fallback > 0 else target))


def run_benchmark(size_bytes: int, duration_s: float, stop_event: threading.Event, progress_cb=None) -> BenchmarkResult:
    """
    Allocate size_bytes and loop:
      - write full buffer (memset)
      - read full buffer (adler32)
    until duration elapsed or stop_event set.
    """
    res = BenchmarkResult()
    res.started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration_s = max(1.0, float(duration_s))
    res.duration_s = duration_s

    # Allocate
    try:
        buf = bytearray(size_bytes)
        res.allocated_bytes = len(buf)
    except MemoryError:
        res.error = "จัดสรร RAM ไม่สำเร็จ (MemoryError) — RAM/Virtual memory ไม่พอ"
        return res
    except Exception as e:
        res.error = f"จัดสรร RAM ไม่สำเร็จ: {e}"
        return res

    mv = memoryview(buf)
    ptr = None
    try:
        c_char_array = (ctypes.c_char * len(buf)).from_buffer(buf)
        ptr = ctypes.addressof(c_char_array)
    except Exception:
        ptr = None

    # Touch/commit pages (แรง)
    try:
        if MEMSET and ptr is not None:
            MEMSET(ptr, 0xAA, len(buf))
        else:
            chunk = b"\xAA" * (1 * MiB)
            for i in range(0, len(buf), len(chunk)):
                if stop_event.is_set():
                    break
                mv[i:i + len(chunk)] = chunk[:min(len(chunk), len(buf) - i)]
    except Exception:
        pass

    t0_global = time.perf_counter()
    t_end = t0_global + duration_s

    write_bytes = read_bytes = 0
    write_time = read_time = 0.0
    checksum = 0
    loops = 0

    # For instantaneous rates
    last_report = t0_global
    last_wb = last_rb = 0
    last_wt = last_rt = 0.0

    while not stop_event.is_set() and time.perf_counter() < t_end:
        # WRITE
        t0 = time.perf_counter()
        try:
            if MEMSET and ptr is not None:
                MEMSET(ptr, 0x5A, len(buf))
            else:
                chunk = b"\x5A" * (1 * MiB)
                for i in range(0, len(buf), len(chunk)):
                    if stop_event.is_set():
                        break
                    mv[i:i + len(chunk)] = chunk[:min(len(chunk), len(buf) - i)]
        except Exception as e:
            res.error = f"เขียน RAM ผิดพลาด: {e}"
            return res
        t1 = time.perf_counter()
        wt = (t1 - t0)
        write_time += wt
        write_bytes += len(buf)

        # READ (checksum)
        t2 = time.perf_counter()
        try:
            checksum = zlib.adler32(mv, checksum)
        except Exception as e:
            res.error = f"อ่าน RAM ผิดพลาด: {e}"
            return res
        t3 = time.perf_counter()
        rt = (t3 - t2)
        read_time += rt
        read_bytes += len(buf)

        loops += 1

        now = time.perf_counter()
        # Report ~5 times/sec max
        if progress_cb and (now - last_report) >= 0.2:
            d_wb = write_bytes - last_wb
            d_rb = read_bytes - last_rb
            d_wt = write_time - last_wt
            d_rt = read_time - last_rt

            inst_write = (d_wb / d_wt / GiB) if d_wt > 0 else 0.0
            inst_read  = (d_rb / d_rt / GiB) if d_rt > 0 else 0.0
            inst_total = 0.0
            if (d_wt + d_rt) > 0:
                inst_total = ((d_wb + d_rb) / (d_wt + d_rt) / GiB)

            progress_cb({
                "elapsed": max(0.0, now - t0_global),
                "remain": max(0.0, t_end - now),
                "loops": loops,
                "inst_write": inst_write,
                "inst_read": inst_read,
                "inst_total": inst_total,
                "avg_write": (write_bytes / write_time / GiB) if write_time > 0 else 0.0,
                "avg_read":  (read_bytes / read_time / GiB) if read_time > 0 else 0.0,
                "checksum": checksum & 0xFFFFFFFF,
            })

            last_report = now
            last_wb, last_rb, last_wt, last_rt = write_bytes, read_bytes, write_time, read_time

    res.ok = not bool(res.error)
    res.write_bytes = int(write_bytes)
    res.read_bytes = int(read_bytes)
    res.write_time = float(write_time)
    res.read_time = float(read_time)
    res.checksum = int(checksum & 0xFFFFFFFF)
    res.loops = int(loops)
    res.ended_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return res


# ---------------------------- GUI (Speedtest-like) ----------------------------

class Gauge(ttk.Frame):
    def __init__(self, master, size=320):
        super().__init__(master)
        self.size = size
        self.canvas = tk.Canvas(self, width=size, height=size, highlightthickness=0, bg="#0f1115")
        self.canvas.pack(fill="both", expand=True)
        self.max_value = 10.0
        self.value = 0.0

        self._draw_static()
        self._needle = None
        self._val_text = None
        self._label_text = None
        self._draw_dynamic()

    def _draw_static(self):
        s = self.size
        pad = 18
        x0, y0 = pad, pad
        x1, y1 = s - pad, s - pad
        # Outer ring
        self.canvas.create_oval(x0, y0, x1, y1, outline="#2a2f3a", width=8)
        # Arc (scale)
        self.canvas.create_arc(x0, y0, x1, y1, start=210, extent=300, style="arc", outline="#394152", width=10)
        # Tick marks
        cx, cy = s/2, s/2
        r_outer = (s - 2*pad)/2
        r_inner = r_outer - 14
        for i in range(0, 11):
            ang = math.radians(210 + (300 * i / 10))
            xA = cx + r_inner * math.cos(ang)
            yA = cy - r_inner * math.sin(ang)
            xB = cx + r_outer * math.cos(ang)
            yB = cy - r_outer * math.sin(ang)
            self.canvas.create_line(xA, yA, xB, yB, fill="#30384a", width=2)

    def _angle_for_value(self, v):
        # map 0..max to 210..510 degrees (wraps visually)
        v = max(0.0, float(v))
        m = max(1e-6, float(self.max_value))
        ratio = min(1.0, v / m)
        return 210 + 300 * ratio

    def _draw_dynamic(self):
        s = self.size
        cx, cy = s/2, s/2
        pad = 18
        r = (s - 2*pad)/2 - 24

        # remove old
        if self._needle is not None:
            self.canvas.delete(self._needle)
        if self._val_text is not None:
            self.canvas.delete(self._val_text)
        if self._label_text is not None:
            self.canvas.delete(self._label_text)

        ang_deg = self._angle_for_value(self.value)
        ang = math.radians(ang_deg)
        xN = cx + r * math.cos(ang)
        yN = cy - r * math.sin(ang)

        self._needle = self.canvas.create_line(cx, cy, xN, yN, fill="#7dd3fc", width=4, capstyle="round")
        self.canvas.create_oval(cx-6, cy-6, cx+6, cy+6, fill="#7dd3fc", outline="")

        self._val_text = self.canvas.create_text(cx, cy+36, text=f"{self.value:.2f} GB/s", fill="#e8edf6",
                                                 font=("Segoe UI", 16, "bold"))
        self._label_text = self.canvas.create_text(cx, cy+60, text="RAM SPEED", fill="#9aa6bd",
                                                   font=("Segoe UI", 10))

    def set_value(self, v, max_value=None):
        self.value = float(v)
        if max_value is not None:
            self.max_value = float(max_value)
        # auto scale up smoothly
        if self.value > self.max_value * 0.92:
            self.max_value = max(self.max_value * 1.25, self.value * 1.1, 5.0)
        self._draw_dynamic()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("720x560")
        self.minsize(720, 560)

        self.configure(bg="#0f1115")
        self._stop_event = threading.Event()
        self._worker_thread = None
        self._ui_q = queue.Queue()

        self._build_style()
        self._build_ui()
        self._refresh_specs()
        self._tick()

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(".", font=("Segoe UI", 10))
        style.configure("TFrame", background="#0f1115")
        style.configure("TLabelframe", background="#0f1115", foreground="#e8edf6")
        style.configure("TLabelframe.Label", background="#0f1115", foreground="#e8edf6", font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background="#0f1115", foreground="#e8edf6")
        style.configure("Muted.TLabel", foreground="#9aa6bd")
        style.configure("Danger.TLabel", foreground="#fca5a5")
        style.configure("TButton", padding=10)
        style.configure("GO.TButton", font=("Segoe UI", 14, "bold"), padding=14)

        style.configure("TEntry", padding=6)
        style.configure("TProgressbar", thickness=8)

    def _build_ui(self):
        root = ttk.Frame(self)
        root.pack(fill="both", expand=True, padx=16, pady=14)

        # Header
        top = ttk.Frame(root)
        top.pack(fill="x")

        ttk.Label(top, text="RAM SPEEDTEST", font=("Segoe UI", 18, "bold")).pack(side="left")
        self.lbl_status = ttk.Label(top, text="READY", style="Muted.TLabel", font=("Segoe UI", 11, "bold"))
        self.lbl_status.pack(side="right")

        ttk.Label(root, text="Local only • ใช้ RAM ใกล้ 100% เพื่อวัดความเร็วอ่าน/เขียน", style="Muted.TLabel").pack(anchor="w", pady=(6, 2))
        ttk.Label(root, text="⚠️ อาจทำให้เครื่องค้าง/หน่วงได้ (คุณสั่งให้ทำแบบ 100%)", style="Danger.TLabel").pack(anchor="w", pady=(0, 10))

        mid = ttk.Frame(root)
        mid.pack(fill="both", expand=True)

        # Left: gauge
        left = ttk.Frame(mid)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        self.gauge = Gauge(left, size=340)
        self.gauge.pack(pady=(8, 8))

        self.var_sub = tk.StringVar(value="Write: - GB/s   |   Read: - GB/s")
        ttk.Label(left, textvariable=self.var_sub, style="Muted.TLabel", font=("Segoe UI", 11)).pack(pady=(0, 8))

        self.var_time = tk.StringVar(value="เวลา: - / -")
        ttk.Label(left, textvariable=self.var_time, style="Muted.TLabel").pack()

        self.pbar = ttk.Progressbar(left, mode="determinate", maximum=100)
        self.pbar.pack(fill="x", pady=(10, 4))

        # Right: settings + specs + results
        right = ttk.Frame(mid)
        right.pack(side="right", fill="both", expand=True)

        box = ttk.Labelframe(right, text="ตั้งค่า")
        box.pack(fill="x", pady=(0, 10))

        row = ttk.Frame(box)
        row.pack(fill="x", padx=10, pady=10)

        ttk.Label(row, text="เวลาทดสอบ (นาที):").pack(side="left")
        self.var_minutes = tk.StringVar(value="1")
        self.ent_minutes = ttk.Entry(row, textvariable=self.var_minutes, width=8)
        self.ent_minutes.pack(side="left", padx=(8, 0))

        self.btn_go = ttk.Button(box, text="GO", style="GO.TButton", command=self.on_go)
        self.btn_go.pack(fill="x", padx=10, pady=(0, 10))

        self.btn_stop = ttk.Button(box, text="STOP", command=self.on_stop, state="disabled")
        self.btn_stop.pack(fill="x", padx=10, pady=(0, 10))

        specs = ttk.Labelframe(right, text="ข้อมูลเครื่อง / RAM")
        specs.pack(fill="x", pady=(0, 10))
        self.lbl_specs = ttk.Label(specs, text="", justify="left", style="Muted.TLabel")
        self.lbl_specs.pack(fill="x", padx=10, pady=10)

        out = ttk.Labelframe(right, text="สรุปผล")
        out.pack(fill="both", expand=True)
        self.txt_out = tk.Text(out, height=8, wrap="word", bg="#0b0d11", fg="#e8edf6", insertbackground="#e8edf6",
                               relief="flat")
        self.txt_out.pack(fill="both", expand=True, padx=10, pady=10)

    def _refresh_specs(self):
        specs = get_basic_specs()
        vm = get_virtual_memory()
        specs_lines = [
            f"OS: {specs.get('OS','-')}",
            f"CPU: {specs.get('Processor','-')}",
            f"Threads: {specs.get('CPU Threads','-')}",
            f"RAM Total: {bytes_to_human(vm.get('total',0))}",
            f"RAM Used: {bytes_to_human(vm.get('used',0))} ({vm.get('percent',0.0):.1f}%)",
            f"RAM Available: {bytes_to_human(vm.get('available',0))}",
            f"Python: {specs.get('Python','-')} ({'64-bit' if is_64bit_python() else '32-bit'})",
        ]
        self.lbl_specs.configure(text="\n".join(specs_lines))

    def _append_out(self, s: str):
        self.txt_out.insert("end", s + "\n")
        self.txt_out.see("end")

    def _set_status(self, s: str):
        self.lbl_status.configure(text=s)

    def _fmt_mmss(self, seconds: float) -> str:
        seconds = max(0, int(seconds))
        m = seconds // 60
        s = seconds % 60
        return f"{m:02d}:{s:02d}"

    def on_go(self):
        if self._worker_thread and self._worker_thread.is_alive():
            return

        try:
            minutes = float(self.var_minutes.get().strip())
            if minutes <= 0:
                raise ValueError()
        except Exception:
            messagebox.showerror("ค่าผิดพลาด", "กรุณาใส่ 'เวลาทดสอบ (นาที)' เป็นตัวเลขมากกว่า 0")
            return

        duration_s = minutes * 60.0
        alloc = choose_100_percent_allocation()
        vm = get_virtual_memory()

        # 32-bit guard
        if not is_64bit_python() and alloc > (2 * GiB):
            messagebox.showwarning(
                "ข้อจำกัด 32-bit",
                "Python ของคุณเป็น 32-bit\n"
                "การจัดสรร RAM ขนาดใหญ่อาจล้มเหลว/ค้างได้\n"
                "แนะนำติดตั้ง Python 64-bit"
            )

        # UI state
        self._stop_event.clear()
        self.btn_go.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.ent_minutes.configure(state="disabled")
        self._set_status("TESTING")
        self.pbar.configure(value=0)
        self.gauge.set_value(0.0, max_value=10.0)
        self.var_sub.set("Write: - GB/s   |   Read: - GB/s")
        self.var_time.set("เวลา: 00:00 / " + self._fmt_mmss(duration_s))

        self._append_out(f"--- START {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
        self._append_out(f"Target allocation (near 100%): {bytes_to_human(alloc)}")
        self._append_out(f"System RAM total: {bytes_to_human(vm.get('total',0))} | available: {bytes_to_human(vm.get('available',0))}")
        self._append_out(f"Duration: {minutes:.2f} minutes")
        self._append_out("")

        start_perf = time.perf_counter()

        def progress_cb(d):
            self._ui_q.put({"type": "progress", "data": d, "t0": start_perf, "dur": duration_s})

        def worker():
            try:
                res = run_benchmark(alloc, duration_s, self._stop_event, progress_cb=progress_cb)
                self._ui_q.put({"type": "done", "result": res, "dur": duration_s})
            except Exception as e:
                self._ui_q.put({"type": "error", "error": str(e)})

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def on_stop(self):
        self._stop_event.set()
        self._set_status("STOPPING")

    def _tick(self):
        try:
            while True:
                msg = self._ui_q.get_nowait()
                typ = msg.get("type")
                if typ == "progress":
                    d = msg["data"]
                    dur = float(msg.get("dur", 1.0))
                    elapsed = float(d.get("elapsed", 0.0))
                    remain = float(d.get("remain", max(0.0, dur - elapsed)))
                    # progress bar
                    pct = min(100.0, max(0.0, (elapsed / dur) * 100.0))
                    self.pbar.configure(value=pct)

                    inst_total = float(d.get("inst_total", 0.0))
                    inst_w = float(d.get("inst_write", 0.0))
                    inst_r = float(d.get("inst_read", 0.0))

                    self.gauge.set_value(inst_total)
                    self.var_sub.set(f"Write: {inst_w:.2f} GB/s   |   Read: {inst_r:.2f} GB/s")
                    self.var_time.set(f"เวลา: {self._fmt_mmss(elapsed)} / {self._fmt_mmss(dur)}  (เหลือ {self._fmt_mmss(remain)})")

                    # refresh specs occasionally
                    if int(elapsed * 5) % 10 == 0:
                        self._refresh_specs()

                elif typ == "done":
                    self._on_done(msg["result"], float(msg.get("dur", 1.0)))
                elif typ == "error":
                    self._on_error(msg.get("error", "unknown error"))
        except queue.Empty:
            pass

        self.after(120, self._tick)

    def _on_error(self, err: str):
        self.btn_go.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.ent_minutes.configure(state="normal")
        self._set_status("ERROR")
        messagebox.showerror("Error", err)
        self._append_out(f"[ERROR] {err}\n")

    def _on_done(self, r: BenchmarkResult, dur: float):
        self.btn_go.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.ent_minutes.configure(state="normal")

        status = "STOPPED" if self._stop_event.is_set() and r.ok else ("DONE" if r.ok else "FAILED")
        self._set_status(status)

        vm = get_virtual_memory()
        rss = get_process_rss()

        # set gauge to avg total
        self.gauge.set_value(r.total_gbps)
        self.var_sub.set(f"Write(avg): {r.write_gbps:.2f} GB/s   |   Read(avg): {r.read_gbps:.2f} GB/s")
        self.pbar.configure(value=100)

        self._append_out("สรุปผล")
        self._append_out(f"Start: {r.started_at}")
        self._append_out(f"End  : {r.ended_at}")
        self._append_out(f"Allocated RAM: {bytes_to_human(r.allocated_bytes)}")
        self._append_out(f"Loops: {r.loops}")
        self._append_out(f"WRITE avg: {r.write_gbps:.2f} GB/s   (data={bytes_to_human(r.write_bytes)}, time={r.write_time:.3f}s)")
        self._append_out(f"READ  avg: {r.read_gbps:.2f} GB/s   (data={bytes_to_human(r.read_bytes)}, time={r.read_time:.3f}s)")
        self._append_out(f"TOTAL avg: {r.total_gbps:.2f} GB/s")
        self._append_out(f"Checksum: 0x{r.checksum:08X}")
        self._append_out(f"System RAM used: {vm.get('percent',0.0):.1f}% | available: {bytes_to_human(vm.get('available',0))}")
        self._append_out(f"Process RSS: {bytes_to_human(rss)}")
        if not r.ok:
            self._append_out(f"ERROR: {r.error}")
        self._append_out("--- END ---\n")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
