"""DLCP batch analyzer.

Pure-Python/Tkinter application for organizing DLCP CSV files, fitting
C(Vac) with a second-order polynomial, smoothing, differentiating, and
exporting auditable CSV results.
"""

from __future__ import annotations

import csv
import math
import os
import re
import statistics
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageTk


Q_E = 1.602176634e-19
EPS0 = 8.8541878128e-12  # F/m
VAC_MODE_PP = "Peak-to-peak (paper dV)"
VAC_MODE_PEAK = "AC peak amplitude"
VAC_MODE_RMS = "AC RMS amplitude"
VAC_MODES = [VAC_MODE_PP, VAC_MODE_PEAK, VAC_MODE_RMS]
X_FILENAME_VAC = "[Filename] Vac"
Y_AUTO_CAP = "[Auto-average capacitance]"


def vac_factor(mode: str) -> float:
    """Convert the user's Vac convention to the paper's peak-to-peak dV."""
    return {VAC_MODE_PP: 1.0, VAC_MODE_PEAK: 2.0, VAC_MODE_RMS: 2.0 * math.sqrt(2.0)}.get(mode, 1.0)


def parse_number(value: object) -> Optional[float]:
    """Parse common CSV numeric formats, returning None for non-numbers."""
    if value is None:
        return None
    text = str(value).strip().replace("\u00a0", "")
    if not text:
        return None
    text = text.replace("−", "-")
    # Handle decimal-comma files after delimiter detection.
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    text = re.sub(r"[^0-9eE+\-.]", "", text)
    try:
        result = float(text)
        return result if math.isfinite(result) else None
    except ValueError:
        return None


def _looks_numeric_row(row: Sequence[str]) -> bool:
    values = [parse_number(cell) for cell in row]
    return sum(v is not None for v in values) >= 2


def read_csv_file(path: str) -> Tuple[List[str], List[List[str]]]:
    """Read a CSV/TSV/semicolon-delimited file with optional header."""
    raw = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    sample = raw[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
        if "\t" in sample and sample.count("\t") >= sample.count(","):
            dialect = csv.excel_tab
        elif sample.count(";") > sample.count(","):
            dialect.delimiter = ";"
    rows = [row for row in csv.reader(raw.splitlines(), dialect) if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError("CSV 파일에 데이터가 없습니다.")
    if _looks_numeric_row(rows[0]):
        width = len(rows[0])
        headers = [f"Column {i + 1}" for i in range(width)]
        data = rows
    else:
        headers = [cell.strip() or f"Column {i + 1}" for i, cell in enumerate(rows[0])]
        data = rows[1:]
    return headers, data


def numeric_columns(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> List[str]:
    result: List[str] = []
    for idx, header in enumerate(headers):
        count = 0
        for row in rows[:2000]:
            if idx < len(row) and parse_number(row[idx]) is not None:
                count += 1
        if count >= 2:
            result.append(header)
    return result


def column_values(headers: Sequence[str], rows: Sequence[Sequence[str]], column: str) -> List[float]:
    idx = list(headers).index(column)
    values = []
    for row in rows:
        if idx >= len(row):
            continue
        number = parse_number(row[idx])
        if number is not None:
            values.append(number)
    return values


def fit_poly2(x: Sequence[float], y: Sequence[float]) -> Tuple[float, float, float]:
    """Least-squares fit y = c0 + c1*x + c2*x^2."""
    if len(x) != len(y) or len(x) < 3:
        raise ValueError("2차 fitting에는 최소 3개의 유효한 데이터 점이 필요합니다.")
    x_mean = statistics.fmean(x)
    x_scale = max(max(abs(v - x_mean) for v in x), 1.0)
    u = [(v - x_mean) / x_scale for v in x]
    sums = [sum(1.0 for _ in u), sum(v for v in u), sum(v * v for v in u), sum(v ** 3 for v in u), sum(v ** 4 for v in u)]
    rhs = [sum(v for v in y), sum(a * b for a, b in zip(u, y)), sum(a * a * b for a, b in zip(u, y))]
    matrix = [[sums[0], sums[1], sums[2], rhs[0]], [sums[1], sums[2], sums[3], rhs[1]], [sums[2], sums[3], sums[4], rhs[2]]]
    for pivot in range(3):
        best = max(range(pivot, 3), key=lambda r: abs(matrix[r][pivot]))
        if abs(matrix[best][pivot]) < 1e-15:
            raise ValueError("x 데이터가 충분히 변화하지 않아 2차 fitting을 할 수 없습니다.")
        matrix[pivot], matrix[best] = matrix[best], matrix[pivot]
        divisor = matrix[pivot][pivot]
        matrix[pivot] = [v / divisor for v in matrix[pivot]]
        for row in range(3):
            if row == pivot:
                continue
            factor = matrix[row][pivot]
            matrix[row] = [a - factor * b for a, b in zip(matrix[row], matrix[pivot])]
    a0, a1, a2 = [matrix[i][3] for i in range(3)]
    c2 = a2 / (x_scale ** 2)
    c1 = a1 / x_scale - 2.0 * a2 * x_mean / (x_scale ** 2)
    c0 = a0 - a1 * x_mean / x_scale + a2 * (x_mean ** 2) / (x_scale ** 2)
    return c0, c1, c2


def moving_average(values: Sequence[float], window: int) -> List[float]:
    if not values:
        return []
    window = max(1, int(window))
    if window % 2 == 0:
        window += 1
    if window <= 1:
        return list(values)
    radius = window // 2
    result = []
    for i in range(len(values)):
        start = max(0, i - radius)
        end = min(len(values), i + radius + 1)
        result.append(statistics.fmean(values[start:end]))
    return result


def derivative(x: Sequence[float], y: Sequence[float]) -> List[float]:
    """First derivative for possibly nonuniform x spacing."""
    if len(x) != len(y) or not x:
        return []
    if len(x) == 1:
        return [float("nan")]
    result = []
    for i in range(len(x)):
        if i == 0:
            dx = x[1] - x[0]
            result.append((y[1] - y[0]) / dx if dx else float("nan"))
        elif i == len(x) - 1:
            dx = x[-1] - x[-2]
            result.append((y[-1] - y[-2]) / dx if dx else float("nan"))
        else:
            dx = x[i + 1] - x[i - 1]
            result.append((y[i + 1] - y[i - 1]) / dx if dx else float("nan"))
    return result


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9가-힣._-]+", "_", value).strip("._") or "result"


@dataclass
class FileRecord:
    path: str
    bias: float = 0.0
    eps_r: float = 10.0
    area_cm2: float = 0.01
    vac_input: Optional[float] = None


def infer_voltage_tokens(path: str) -> List[float]:
    """Return voltage tokens in a filename, normalized to volts.

    Example: '-175mV 120mV_000_...' -> [-0.175, 0.120].
    The first token is treated as DC bias and the second as Vac.
    """
    stem = Path(path).stem
    tokens = []
    for match in re.finditer(r"(?<![A-Za-z])([+-]?\d+(?:\.\d+)?)\s*(mV|V)(?![A-Za-z])", stem, re.IGNORECASE):
        value = float(match.group(1))
        if match.group(2).lower() == "mv":
            value /= 1000.0
        tokens.append(value)
    return tokens


def infer_bias_and_vac(path: str, fallback_bias: float, fallback_vac: Optional[float] = None) -> Tuple[float, Optional[float]]:
    voltage_tokens = infer_voltage_tokens(path)
    if len(voltage_tokens) >= 2:
        return voltage_tokens[0], voltage_tokens[1]
    if len(voltage_tokens) == 1:
        return voltage_tokens[0], fallback_vac
    stem = Path(path).stem
    patterns = [r"(?:bias|dc|vb|voltage)[ _-]*([+-]?\d+(?:\.\d+)?)", r"(?:^|[_ -])([+-]?\d+(?:\.\d+)?)\s*v(?:$|[_ -])"]
    for pattern in patterns:
        match = re.search(pattern, stem, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1)), fallback_vac
            except ValueError:
                pass
    return fallback_bias, fallback_vac


def infer_bias(path: str, fallback: float) -> float:
    """Backward-compatible bias-only filename inference."""
    return infer_bias_and_vac(path, fallback)[0]


def find_csv_files(folder: str) -> List[str]:
    """Find CSV files below a selected Bias folder or common parent folder."""
    root = Path(folder)
    if not root.is_dir():
        return []
    return sorted(
        (str(path) for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".csv"),
        key=lambda value: (str(Path(value).parent).lower(), Path(value).name.lower()),
    )


def capacitance_columns(headers: Sequence[str]) -> List[str]:
    """Find likely capacitance columns without confusing conductance/impedance."""
    result = []
    for header in headers:
        lower = header.strip().lower()
        if "capacitance" in lower or lower in {"cap", "c", "c_f", "c_pf", "c_nf"} or re.search(r"(?:^|[_ -])c(?:[_ -]|\d|$)", lower):
            result.append(header)
    return result


def bias_columns(headers: Sequence[str]) -> List[str]:
    return [header for header in headers if header.strip().lower() in {"bias_v", "bias", "dc_bias_v", "vdc"}]


def extract_file_bias(record: FileRecord, parsed: Tuple[List[str], List[List[str]]]) -> float:
    """Use bias_V embedded in the CSV when available; otherwise use filename bias."""
    headers, rows = parsed
    candidates = bias_columns(headers)
    if not candidates:
        return record.bias
    index = headers.index(candidates[0])
    values = [parse_number(row[index]) for row in rows if index < len(row)]
    values = [value for value in values if value is not None]
    return statistics.fmean(values) if values else record.bias


def extract_record_points(record: FileRecord, x_col: str, y_col: str, y_scale: float, parsed: Optional[Tuple[List[str], List[List[str]]]] = None) -> List[Tuple[float, float]]:
    """Extract (Vac, capacitance) points and average duplicate measurements."""
    headers, rows = parsed if parsed is not None else read_csv_file(record.path)
    filename_x = x_col == X_FILENAME_VAC
    if filename_x and record.vac_input is None:
        raise ValueError(f"{Path(record.path).name}: 파일명에서 Vac를 찾지 못했습니다. 파일명에 예: 120mV를 포함하세요.")
    if not filename_x:
        xi = headers.index(x_col)
    if y_col == Y_AUTO_CAP:
        y_columns = capacitance_columns(headers)
        if not y_columns:
            raise ValueError(f"{Path(record.path).name}: capacitance 열을 자동으로 찾지 못했습니다.")
    else:
        y_columns = [y_col]
    y_indices = [headers.index(column) for column in y_columns]
    grouped = {}
    for row in rows:
        if not filename_x and xi >= len(row):
            continue
        if any(index >= len(row) for index in y_indices):
            continue
        xv = record.vac_input if filename_x else parse_number(row[xi])
        y_values = [parse_number(row[index]) for index in y_indices]
        y_values = [value for value in y_values if value is not None]
        yv = statistics.fmean(y_values) if y_values else None
        if xv is not None and yv is not None:
            grouped.setdefault(xv, []).append(yv * y_scale)
    if not grouped:
        raise ValueError(f"{Path(record.path).name}: 유효한 x/y 데이터가 없습니다. x는 Vac, y는 capacitance 열인지 확인하세요.")
    # For filename Vac mode, all rows in one CSV share the same x and are
    # averaged here. This handles the instrument's two repeated capacitance rows.
    return sorted((xv, statistics.fmean(values)) for xv, values in grouped.items())


def process_batch(records: Sequence[FileRecord], x_col: str, y_col: str, y_scale: float, vac_scale: float = 1.0, detail_smoothing_window: int = 5, parsed_lookup=None) -> dict:
    """Fit all Vac files belonging to one DC bias as one DLCP curve."""
    if not records:
        raise ValueError("분석할 파일이 없습니다.")
    grouped = {}
    grouped_bias = {}
    for record in records:
        parsed = parsed_lookup(record.path) if parsed_lookup is not None else None
        if parsed is None:
            parsed = read_csv_file(record.path)
        file_bias = extract_file_bias(record, parsed)
        for x_input, y in extract_record_points(record, x_col, y_col, y_scale, parsed):
            grouped.setdefault(x_input, []).append(y)
            grouped_bias.setdefault(x_input, []).append(file_bias)
    if len(grouped) < 3:
        raise ValueError(f"Bias {records[0].bias:g} V: polynomial fitting에는 서로 다른 Vac 데이터가 3개 이상 필요합니다. 현재 {len(grouped)}개입니다.")
    averaged = sorted((xv, statistics.fmean(values), statistics.fmean(grouped_bias[xv])) for xv, values in grouped.items())
    x_input = [point[0] for point in averaged]
    x = [value * vac_scale for value in x_input]
    y = [point[1] for point in averaged]
    bias_points = [point[2] for point in averaged]
    c0, c1, c2 = fit_poly2(x, y)
    fit_y = [c0 + c1 * value + c2 * value * value for value in x]
    representative = records[0]
    return {"record": representative, "records": list(records), "x": x, "x_input": x_input, "y": y, "bias_points": bias_points, "fit_y": fit_y, "smooth_y": moving_average(y, detail_smoothing_window), "derivative_fit": [c1 + 2 * c2 * value for value in x], "c0": c0, "c1": c1, "c2": c2}


def process_record(record: FileRecord, x_col: str, y_col: str, y_scale: float, vac_scale: float = 1.0, detail_smoothing_window: int = 5, parsed: Optional[Tuple[List[str], List[List[str]]]] = None) -> dict:
    """Backward-compatible wrapper for a CSV that contains multiple Vac rows."""
    return process_batch([record], x_col, y_col, y_scale, vac_scale, detail_smoothing_window, lambda _path: parsed) if parsed is not None else process_batch([record], x_col, y_col, y_scale, vac_scale, detail_smoothing_window)


def density_from_cv(capacitance_f: float, dcap_dv: float, eps: float, area_m2: float) -> float:
    if not all(math.isfinite(value) for value in (capacitance_f, dcap_dv, eps, area_m2)) or capacitance_f == 0 or dcap_dv == 0 or eps <= 0 or area_m2 <= 0:
        return float("nan")
    return (2.0 * capacitance_f ** 3) / (Q_E * eps * area_m2 ** 2 * dcap_dv) / 1e6


def build_summary(results: Sequence[dict], smoothing_window: int, calculate_ndlcp: bool = True) -> List[dict]:
    ordered = sorted(results, key=lambda item: item["record"].bias)
    biases = [item["record"].bias for item in ordered]
    c0 = [item["c0"] for item in ordered]
    c1 = [item["c1"] for item in ordered]
    c0_smoothed = moving_average(c0, smoothing_window)
    c1_smoothed = moving_average(c1, smoothing_window)
    dc0_dbias = derivative(biases, c0_smoothed)
    d_inv_c02_dbias = derivative(biases, [1.0 / (v * v) if v else float("nan") for v in c0_smoothed])
    summary = []
    for idx, item in enumerate(ordered):
        rec = item["record"]
        c0s = c0_smoothed[idx]
        eps = rec.eps_r * EPS0
        area_m2 = rec.area_cm2 * 1e-4
        width_raw_nm = eps * area_m2 / item["c0"] * 1e9 if item["c0"] else float("nan")
        width_smooth_nm = eps * area_m2 / c0s * 1e9 if c0s else float("nan")
        ncv_global = density_from_cv(c0s, dc0_dbias[idx], eps, area_m2) if calculate_ndlcp else float("nan")

        # Fallback/local C-V profile from the bias_V values embedded in the CSV.
        local_pairs = sorted(zip(item.get("bias_points", []), item["y"]), key=lambda pair: pair[0])
        local_grouped = {}
        for local_bias, local_cap in local_pairs:
            local_grouped.setdefault(local_bias, []).append(local_cap)
        local_biases = sorted(local_grouped)
        local_caps = [statistics.fmean(local_grouped[value]) for value in local_biases]
        local_caps_smooth = moving_average(local_caps, smoothing_window)
        local_derivative = derivative(local_biases, local_caps_smooth)
        local_idx = min(range(len(local_biases)), key=lambda position: abs(local_biases[position] - rec.bias)) if local_biases else 0
        ncv_local = density_from_cv(local_caps_smooth[local_idx], local_derivative[local_idx], eps, area_m2) if calculate_ndlcp and len(local_biases) >= 2 else float("nan")
        ncv_signed = ncv_global if math.isfinite(ncv_global) else ncv_local
        ncv_method = "C0 vs nominal Bias" if math.isfinite(ncv_global) else ("CSV bias_V vs C" if math.isfinite(ncv_local) else "insufficient bias points")

        nd_signed = float("nan")
        if calculate_ndlcp and item["c1"] and rec.eps_r and rec.area_cm2:
            nd_m3 = (item["c0"] ** 3) / (2.0 * Q_E * eps * area_m2 ** 2 * item["c1"])
            nd_signed = nd_m3 / 1e6
        summary.append({"bias_V": rec.bias, "eps_r": rec.eps_r, "area_cm2": rec.area_cm2, "C0_F": item["c0"], "C1_F_per_V": item["c1"], "C2_F_per_V2": item["c2"], "C0_smooth_F": c0s, "C1_smooth_F_per_V": c1_smoothed[idx], "dC0smooth_dBias_F_per_V": dc0_dbias[idx], "dInvC0sq_dBias_1_per_F2V": d_inv_c02_dbias[idx], "depletion_width_raw_nm": width_raw_nm, "depletion_width_smooth_nm": width_smooth_nm, "depletion_width_nm": width_smooth_nm, "N_CV_method": ncv_method, "N_CV_signed_cm-3": ncv_signed, "N_CV_abs_cm-3": abs(ncv_signed) if math.isfinite(ncv_signed) else float("nan"), "N_CV_global_signed_cm-3": ncv_global, "N_CV_local_signed_cm-3": ncv_local, "N_DL_signed_cm-3": nd_signed, "N_DL_abs_cm-3": abs(nd_signed) if math.isfinite(nd_signed) else float("nan"), "N_CL_abs_cm-3": abs(nd_signed) if math.isfinite(nd_signed) else float("nan")})
    return summary


def fmt(value: object) -> str:
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.8g}"
    return str(value)


class DLCPApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("DLCP Batch Analyzer")
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.records: List[FileRecord] = []
        self.results: List[dict] = []
        self.summary: List[dict] = []
        self.history_results = {}
        self.headers: List[str] = []
        self.rows: List[List[str]] = []
        self.csv_cache = {}
        self.x_var = tk.StringVar()
        self.y_var = tk.StringVar()
        self.device_var = tk.StringVar(value="DLCP_device")
        self.eps_var = tk.StringVar(value="10")
        self.area_var = tk.StringVar(value="0.01")
        self.bias_var = tk.StringVar(value="0")
        self.vac_input_var = tk.StringVar(value="")
        self.default_eps_r = 10.0
        self.default_area_cm2 = 0.01
        self.window_var = tk.StringVar(value="5")
        self.y_unit_var = tk.StringVar(value="pF")
        self.vac_mode_var = tk.StringVar(value=VAC_MODE_PP)
        self.ndlcp_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="CSV 파일을 추가하세요.")
        self.saved_bias_var = tk.StringVar()
        self.plot_window = None
        self._build_ui()

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="Device / batch name").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.device_var, width=24).grid(row=0, column=1, padx=6, sticky="w")
        ttk.Label(top, text="C unit").grid(row=0, column=2, sticky="e")
        ttk.Combobox(top, textvariable=self.y_unit_var, values=["F", "mF", "uF", "nF", "pF", "fF", "aF"], width=7, state="readonly").grid(row=0, column=3, padx=6, sticky="w")
        ttk.Label(top, text="Vac convention").grid(row=0, column=4, sticky="e")
        vac_combo = ttk.Combobox(top, textvariable=self.vac_mode_var, values=VAC_MODES, width=23, state="readonly")
        vac_combo.grid(row=0, column=5, padx=6, sticky="w")
        vac_combo.bind("<<ComboboxSelected>>", lambda _event: self.draw_preview_for_selected())
        ttk.Label(top, text="Smooth window").grid(row=0, column=6, sticky="e")
        ttk.Spinbox(top, from_=1, to=99, textvariable=self.window_var, width=6).grid(row=0, column=7, padx=6, sticky="w")
        ttk.Checkbutton(top, text="N_CV / N_DL / W 계산", variable=self.ndlcp_var).grid(row=0, column=8, padx=8, sticky="w")

        files = ttk.LabelFrame(self, text="1. Bias별 CSV 입력", padding=8)
        files.pack(fill="x", padx=10, pady=(0, 8))
        buttons = ttk.Frame(files)
        buttons.pack(fill="x", pady=(0, 6))
        ttk.Button(buttons, text="CSV 추가", command=self.add_files).pack(side="left")
        ttk.Button(buttons, text="Bias 폴더 추가", command=self.add_folder).pack(side="left", padx=5)
        ttk.Button(buttons, text="선택 삭제", command=self.remove_selected).pack(side="left", padx=5)
        ttk.Button(buttons, text="현재 CSV 전체 삭제", command=self.clear_files).pack(side="left")
        ttk.Button(buttons, text="저장 결과 초기화", command=self.clear_history).pack(side="left", padx=5)
        self.file_tree = ttk.Treeview(files, columns=("file", "bias", "vac", "eps", "area"), show="headings", height=5)
        for col, title, width in [("file", "File", 520), ("bias", "Bias (V)", 90), ("vac", "Vac input", 90), ("eps", "epsilon_r", 100), ("area", "Area (cm²)", 100)]:
            self.file_tree.heading(col, text=title)
            self.file_tree.column(col, width=width, anchor="w" if col == "file" else "e")
        self.file_tree.pack(fill="x", side="left", expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self.select_file)
        editor = ttk.Frame(files, padding=(10, 0, 0, 0))
        editor.pack(side="left", fill="y")
        ttk.Label(editor, text="선택 파일 설정").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))
        for row, label, var in [(1, "Bias (V)", self.bias_var), (2, "Vac input", self.vac_input_var), (3, "epsilon_r", self.eps_var), (4, "Area (cm²)", self.area_var)]:
            ttk.Label(editor, text=label).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(editor, textvariable=var, width=14).grid(row=row, column=1, padx=5, pady=2)
        ttk.Button(editor, text="선택 파일에 적용", command=self.apply_file_settings).grid(row=5, column=0, columnspan=2, pady=(6, 2))
        ttk.Button(editor, text="전체 파일에 ε/Area 적용", command=self.apply_all_file_settings).grid(row=6, column=0, columnspan=2, pady=2)

        mapping = ttk.LabelFrame(self, text="2. CSV 열 선택", padding=8)
        mapping.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(mapping, text="x / Vac 열 또는 파일명").grid(row=0, column=0, sticky="w")
        self.x_combo = ttk.Combobox(mapping, textvariable=self.x_var, state="readonly", width=28)
        self.x_combo.grid(row=0, column=1, padx=6)
        ttk.Label(mapping, text="y / Capacitance 열").grid(row=0, column=2, sticky="w")
        self.y_combo = ttk.Combobox(mapping, textvariable=self.y_var, state="readonly", width=28)
        self.y_combo.grid(row=0, column=3, padx=6)
        ttk.Label(mapping, text="fitting x는 논문 기준 dV_pp로 변환").grid(row=0, column=4, padx=8, sticky="w")
        ttk.Button(mapping, text="미리보기 갱신", command=self.refresh_preview).grid(row=0, column=5, padx=6)

        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        left = ttk.LabelFrame(body, text="3. 선택 파일 Preview", padding=6)
        right = ttk.LabelFrame(body, text="4. Bias별 Summary", padding=6)
        body.add(left, weight=1)
        body.add(right, weight=2)
        preview_toolbar = ttk.Frame(left)
        preview_toolbar.pack(fill="x", pady=(0, 5))
        ttk.Label(preview_toolbar, text="저장된 Bias preview").pack(side="left")
        self.saved_bias_combo = ttk.Combobox(preview_toolbar, textvariable=self.saved_bias_var, state="readonly", width=13)
        self.saved_bias_combo.pack(side="left", padx=5)
        ttk.Button(preview_toolbar, text="불러오기", command=self.show_saved_preview).pack(side="left")
        self.canvas = tk.Canvas(left, background="white", highlightthickness=1, highlightbackground="#b0b0b0")
        self.canvas.pack(fill="both", expand=True)
        self.summary_tree = ttk.Treeview(right, columns=("bias", "c0", "c1", "c2", "width", "ncv", "ndl"), show="headings")
        for col, title, width in [("bias", "Bias", 75), ("c0", "C0 (F)", 105), ("c1", "C1 (F/Vpp)", 115), ("c2", "C2 (F/Vpp²)", 120), ("width", "W (nm)", 100), ("ncv", "N_CV (cm⁻³)", 135), ("ndl", "N_DL (cm⁻³)", 135)]:
            self.summary_tree.heading(col, text=title)
            self.summary_tree.column(col, width=width, anchor="w" if col == "file" else "e")
        self.summary_tree.pack(fill="both", expand=True)
        bottom = ttk.Frame(self, padding=(10, 0, 10, 8))
        bottom.pack(fill="x")
        ttk.Button(bottom, text="분석 실행", command=self.run_analysis).pack(side="left")
        ttk.Button(bottom, text="결과 CSV 저장", command=self.export_results).pack(side="left", padx=6)
        ttk.Button(bottom, text="N_CV / N_DL vs W 그래프", command=self.draw_profile_plot).pack(side="left", padx=6)
        ttk.Label(bottom, textvariable=self.status_var).pack(side="left", padx=12)

    def append_files(self, paths: Sequence[str], source_label: str = "CSV") -> None:
        """Append unique CSV paths while applying the current device defaults."""
        existing = {os.path.normcase(os.path.abspath(record.path)) for record in self.records}
        unique_paths = []
        for path in paths:
            normalized = os.path.normcase(os.path.abspath(path))
            if normalized not in existing:
                existing.add(normalized)
                unique_paths.append(path)
        if not unique_paths:
            self.status_var.set("새로 추가할 CSV가 없습니다. 이미 추가된 파일은 제외되었습니다.")
            return
        start = len(self.records)
        for i, path in enumerate(unique_paths):
            bias, vac = infer_bias_and_vac(path, float(start + i))
            self.records.append(FileRecord(path=path, bias=bias, eps_r=self.default_eps_r, area_cm2=self.default_area_cm2, vac_input=vac))
        self.refresh_file_tree()
        if not self.headers:
            self.load_first_file_columns()
        self.status_var.set(f"{len(unique_paths)}개 CSV가 추가되었습니다. (현재 총 {len(self.records)}개, {source_label})")

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(title="DLCP CSV 파일 선택", filetypes=[("CSV/TSV", "*.csv *.tsv *.txt"), ("All files", "*.*")])
        if not paths:
            return
        self.append_files(paths)

    def add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Bias 폴더 또는 Bias 폴더들이 들어 있는 상위 폴더 선택")
        if not folder:
            return
        paths = find_csv_files(folder)
        if not paths:
            messagebox.showinfo("CSV 없음", "선택한 폴더와 하위 폴더에서 CSV 파일을 찾지 못했습니다.")
            return
        self.append_files(paths, source_label=f"폴더: {Path(folder).name}")

    def refresh_file_tree(self) -> None:
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)
        for idx, rec in enumerate(self.records):
            self.file_tree.insert("", "end", iid=str(idx), values=(Path(rec.path).name, fmt(rec.bias), fmt(rec.vac_input) if rec.vac_input is not None else "", fmt(rec.eps_r), fmt(rec.area_cm2)))

    def select_file(self, _event=None) -> None:
        selected = self.file_tree.selection()
        if not selected:
            return
        rec = self.records[int(selected[0])]
        self.bias_var.set(fmt(rec.bias))
        self.vac_input_var.set(fmt(rec.vac_input) if rec.vac_input is not None else "")
        self.eps_var.set(fmt(rec.eps_r))
        self.area_var.set(fmt(rec.area_cm2))
        if not self.headers:
            self.load_first_file_columns()
        self.draw_preview_for_selected()

    def apply_file_settings(self) -> None:
        selected = self.file_tree.selection()
        if not selected:
            messagebox.showinfo("알림", "설정할 파일을 먼저 선택하세요.")
            return
        try:
            rec = self.records[int(selected[0])]
            rec.bias = float(self.bias_var.get())
            vac_text = self.vac_input_var.get().strip()
            rec.vac_input = float(vac_text) if vac_text else None
            rec.eps_r = float(self.eps_var.get())
            rec.area_cm2 = float(self.area_var.get())
            if rec.eps_r <= 0 or rec.area_cm2 <= 0:
                raise ValueError
            self.default_eps_r = rec.eps_r
            self.default_area_cm2 = rec.area_cm2
        except ValueError:
            messagebox.showerror("입력 오류", "Bias, Vac, epsilon_r, Area는 유효한 숫자여야 하며 epsilon_r/Area는 0보다 커야 합니다.")
            return
        self.refresh_file_tree()
        self.file_tree.selection_set(selected[0])

    def apply_all_file_settings(self) -> None:
        if not self.records:
            messagebox.showinfo("알림", "먼저 CSV 파일을 추가하세요.")
            return
        try:
            eps_r = float(self.eps_var.get())
            area_cm2 = float(self.area_var.get())
            if eps_r <= 0 or area_cm2 <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("입력 오류", "epsilon_r와 Area는 0보다 큰 숫자여야 합니다.")
            return
        for rec in self.records:
            rec.eps_r = eps_r
            rec.area_cm2 = area_cm2
        self.default_eps_r = eps_r
        self.default_area_cm2 = area_cm2
        self.refresh_file_tree()
        self.status_var.set(f"{len(self.records)}개 파일에 epsilon_r/Area를 일괄 적용했습니다. Bias와 Vac는 파일명에서 자동 인식합니다.")

    def clear_files(self) -> None:
        self.records.clear()
        self.headers.clear()
        self.rows.clear()
        self.csv_cache.clear()
        self.refresh_file_tree()
        self.x_combo["values"] = []
        self.y_combo["values"] = []
        self.canvas.delete("all")
        self.status_var.set(f"현재 CSV 입력을 삭제했습니다. 저장된 Bias 결과 {len(self.history_results)}개는 유지됩니다.")

    def clear_history(self) -> None:
        if not self.history_results:
            return
        if not messagebox.askyesno("저장 결과 초기화", "분석 결과로 저장된 모든 Bias history를 삭제할까요?"):
            return
        self.history_results.clear()
        self.results.clear()
        self.summary.clear()
        self.refresh_saved_biases()
        self.clear_summary()
        self.canvas.delete("all")
        self.status_var.set("저장된 Bias 결과를 모두 초기화했습니다.")

    def remove_selected(self) -> None:
        selected = sorted((int(i) for i in self.file_tree.selection()), reverse=True)
        for index in selected:
            self.records.pop(index)
        self.refresh_file_tree()

    def refresh_saved_biases(self) -> None:
        values = [fmt(key) for key in sorted(self.history_results)]
        self.saved_bias_combo["values"] = values
        if values and self.saved_bias_var.get() not in values:
            self.saved_bias_var.set(values[-1])
        elif not values:
            self.saved_bias_var.set("")

    def show_saved_preview(self) -> None:
        try:
            bias = float(self.saved_bias_var.get())
            key = min(self.history_results, key=lambda value: abs(value - bias))
            item = self.history_results[key]
            self.draw_plot(item["x"], item["y"], item["fit_y"])
            self.status_var.set(f"저장된 Bias {fmt(key)} V의 preview를 표시했습니다.")
        except (ValueError, TypeError):
            messagebox.showinfo("알림", "먼저 분석된 Bias를 선택하세요.")

    def load_first_file_columns(self) -> None:
        if not self.records:
            return
        try:
            self.headers, self.rows = self.load_cached_csv(self.records[0].path)
            values = numeric_columns(self.headers, self.rows)
            cap_values = capacitance_columns(self.headers)
            x_values = [X_FILENAME_VAC] + values
            y_values = [Y_AUTO_CAP] + values
            self.x_combo["values"] = x_values
            self.y_combo["values"] = y_values
            self.x_var.set(X_FILENAME_VAC if all(rec.vac_input is not None for rec in self.records) else (values[0] if values else ""))
            self.y_var.set(Y_AUTO_CAP if cap_values else (values[1] if len(values) > 1 else (values[0] if values else "")))
            self.draw_preview_for_selected()
        except Exception as exc:
            messagebox.showerror("CSV 읽기 오류", str(exc))

    def refresh_preview(self) -> None:
        if self.records:
            self.load_first_file_columns()

    def records_with_same_bias(self, bias: float) -> List[FileRecord]:
        return [record for record in self.records if abs(record.bias - bias) <= 1e-12]

    def draw_preview_for_selected(self) -> None:
        selected = self.file_tree.selection()
        if not selected or not self.x_var.get() or not self.y_var.get():
            return
        try:
            rec = self.records[int(selected[0])]
            scale = {"F": 1.0, "mF": 1e-3, "uF": 1e-6, "nF": 1e-9, "pF": 1e-12, "fF": 1e-15, "aF": 1e-18}[self.y_unit_var.get()]
            group = self.records_with_same_bias(rec.bias)
            data = process_batch(group, self.x_var.get(), self.y_var.get(), scale, vac_factor(self.vac_mode_var.get()), int(float(self.window_var.get())), self.load_cached_csv)
            self.draw_plot(data["x"], data["y"], data["fit_y"])
        except Exception as exc:
            self.canvas.delete("all")
            self.canvas.create_text(20, 20, anchor="nw", text=f"Preview 오류: {exc}", fill="red")

    def draw_plot(self, x: Sequence[float], y: Sequence[float], fit_y: Sequence[float]) -> None:
        self.canvas.delete("all")
        width = max(self.canvas.winfo_width(), 300)
        height = max(self.canvas.winfo_height(), 220)
        margin = 42
        xmin, xmax = min(x), max(x)
        ymin, ymax = min(y + list(fit_y)), max(y + list(fit_y))
        if xmax == xmin:
            xmax = xmin + 1
        if ymax == ymin:
            ymax = ymin + 1
        def xy(xv, yv):
            px = margin + (xv - xmin) / (xmax - xmin) * (width - 2 * margin)
            py = height - margin - (yv - ymin) / (ymax - ymin) * (height - 2 * margin)
            return px, py
        self.canvas.create_line(margin, height - margin, width - margin, height - margin, fill="#555")
        self.canvas.create_line(margin, margin, margin, height - margin, fill="#555")
        for xv, yv in zip(x, y):
            px, py = xy(xv, yv)
            self.canvas.create_oval(px - 2, py - 2, px + 2, py + 2, fill="#1f77b4", outline="")
        points = [coord for pair in (xy(a, b) for a, b in zip(x, fit_y)) for coord in pair]
        self.canvas.create_line(*points, fill="#d62728", width=2, smooth=False)
        self.canvas.create_text(margin, 12, anchor="w", text="blue: raw   red: order-2 fit", fill="#333")
        self.canvas.create_text(width / 2, height - 10, text="dV_pp (converted from " + self.vac_mode_var.get() + ")", fill="#333")
        self.canvas.create_text(10, height / 2, text=self.y_var.get(), angle=90, fill="#333")

    def run_analysis(self) -> None:
        if not self.records:
            messagebox.showinfo("알림", "CSV 파일을 먼저 추가하세요.")
            return
        if not self.x_var.get() or not self.y_var.get():
            messagebox.showerror("입력 오류", "x/Vac 열 또는 파일명 Vac와 y/Capacitance 열을 선택하세요.")
            return
        try:
            window = max(1, int(float(self.window_var.get())))
            scale = {"F": 1.0, "mF": 1e-3, "uF": 1e-6, "nF": 1e-9, "pF": 1e-12, "fF": 1e-15, "aF": 1e-18}[self.y_unit_var.get()]
            factor = vac_factor(self.vac_mode_var.get())
            groups = {}
            for rec in self.records:
                groups.setdefault(round(rec.bias, 12), []).append(rec)
            new_results = [process_batch(group, self.x_var.get(), self.y_var.get(), scale, factor, window, self.load_cached_csv) for group in groups.values()]
            for result in new_results:
                self.history_results[round(result["record"].bias, 12)] = result
            self.recalculate_history(window)
            self.refresh_saved_biases()
            self.status_var.set(f"분석 완료: {len(self.records)}개 CSV → 현재 {len(new_results)}개 Bias group, 저장된 전체 {len(self.results)}개 Bias group")
        except Exception as exc:
            messagebox.showerror("분석 오류", str(exc))

    def recalculate_history(self, smoothing_window: int) -> None:
        self.results = [self.history_results[key] for key in sorted(self.history_results)]
        self.summary = build_summary(self.results, smoothing_window, self.ndlcp_var.get()) if self.results else []
        self.populate_summary()

    def clear_summary(self) -> None:
        for item in self.summary_tree.get_children():
            self.summary_tree.delete(item)

    def populate_summary(self) -> None:
        self.clear_summary()
        for row in self.summary:
            self.summary_tree.insert("", "end", values=(fmt(row["bias_V"]), fmt(row["C0_F"]), fmt(row["C1_F_per_V"]), fmt(row["C2_F_per_V2"]), fmt(row["depletion_width_nm"]), fmt(row["N_CV_abs_cm-3"]), fmt(row["N_DL_abs_cm-3"])))

    def draw_profile_plot(self) -> None:
        if not self.summary:
            messagebox.showinfo("알림", "먼저 분석을 실행하세요.")
            return
        # Log y-axis uses positive absolute densities; signed values remain in Summary/CSV.
        points_cv = [(row["depletion_width_nm"], row["N_CV_abs_cm-3"]) for row in self.summary if math.isfinite(row["depletion_width_nm"]) and math.isfinite(row["N_CV_abs_cm-3"]) and 1e16 <= row["N_CV_abs_cm-3"] <= 1e19]
        points_dl = [(row["depletion_width_nm"], row["N_DL_abs_cm-3"]) for row in self.summary if math.isfinite(row["depletion_width_nm"]) and math.isfinite(row["N_DL_abs_cm-3"]) and 1e16 <= row["N_DL_abs_cm-3"] <= 1e19]
        if not points_cv and not points_dl:
            messagebox.showinfo("알림", "로그 스케일(10^16–10^19)에 표시할 수 있는 N_CV/N_DL 데이터가 없습니다.")
            return
        image = self.make_profile_image(points_cv, points_dl)
        if self.plot_window is None or not self.plot_window.winfo_exists():
            self.plot_window = tk.Toplevel(self)
            self.plot_window.title("DLCP Profile - N_CV / N_DL vs W")
            self.plot_window.geometry("1100x760")
            self.plot_window.minsize(800, 600)
            toolbar = ttk.Frame(self.plot_window, padding=8)
            toolbar.pack(fill="x")
            ttk.Button(toolbar, text="PNG 저장", command=self.save_profile_png).pack(side="left")
            ttk.Label(toolbar, text="발표/논문용 1600×1000 PNG, |N| log scale (10^16–10^19 cm^-3)").pack(side="left", padx=10)
            self.plot_label = ttk.Label(self.plot_window, anchor="center")
            self.plot_label.pack(fill="both", expand=True, padx=8, pady=8)
        photo = ImageTk.PhotoImage(image)
        self.plot_label.configure(image=photo)
        self.plot_label.image = photo
        self.plot_window.profile_image = image
        self.plot_window.lift()

    @staticmethod
    def _plot_font(size: int, bold: bool = False):
        candidates = [r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\malgun.ttf"]
        for candidate in candidates:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size)
        return ImageFont.load_default()

    def make_profile_image(self, points_cv, points_dl):
        width, height = 1600, 1000
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        left, top, right, bottom = 150, 70, 70, 145
        plot_w, plot_h = width - left - right, height - top - bottom
        all_points = list(points_cv) + list(points_dl)
        xmin = min(point[0] for point in all_points)
        xmax = max(point[0] for point in all_points)
        # Fixed publication range: a logarithmic axis cannot include zero.
        ymin, ymax = 1e16, 1e19
        if xmin == xmax:
            xmin -= 1.0
            xmax += 1.0
        xpad = max((xmax - xmin) * 0.04, 0.5)
        xmin, xmax = xmin - xpad, xmax + xpad
        def xy(x_value, y_value):
            px = left + (x_value - xmin) / (xmax - xmin) * plot_w
            log_min, log_max = math.log10(ymin), math.log10(ymax)
            log_value = math.log10(max(ymin, min(ymax, y_value)))
            py = top + (log_max - log_value) / (log_max - log_min) * plot_h
            return px, py
        axis = (35, 35, 35)
        grid = (220, 220, 220)
        draw.rectangle((left, top, left + plot_w, top + plot_h), outline=axis, width=3)
        tick_font = self._plot_font(24)
        label_font = self._plot_font(32)
        title_font = self._plot_font(34, True)
        for exponent in range(19, 15, -1):
            y_value = 10.0 ** exponent
            fraction = (19 - exponent) / 3.0
            py = top + fraction * plot_h
            draw.line((left, py, left + plot_w, py), fill=grid, width=1)
            label = f"10^{exponent}"
            draw.text((left - 16, py), label, font=tick_font, fill=axis, anchor="ra")
        for i in range(7):
            fraction = i / 6.0
            x_value = xmin + fraction * (xmax - xmin)
            px = left + fraction * plot_w
            draw.line((px, top, px, top + plot_h), fill=grid, width=1)
            draw.text((px, top + plot_h + 16), f"{x_value:.1f}", font=tick_font, fill=axis, anchor="ma")
        def draw_series(points, color, marker):
            points = sorted(points)
            if len(points) > 1:
                draw.line([xy(x_value, y_value) for x_value, y_value in points], fill=color, width=4, joint="curve")
            for x_value, y_value in points:
                px, py = xy(x_value, y_value)
                if marker == "triangle":
                    draw.polygon([(px, py - 12), (px - 12, py + 10), (px + 12, py + 10)], fill=color)
                else:
                    draw.ellipse((px - 9, py - 9, px + 9, py + 9), fill=color)
        draw_series(points_cv, (30, 65, 210), "triangle")
        draw_series(points_dl, (70, 70, 70), "circle")
        legend_x, legend_y = left + plot_w - 210, top + 20
        draw.rectangle((legend_x, legend_y, legend_x + 185, legend_y + 92), fill="white", outline=axis, width=2)
        draw.line((legend_x + 15, legend_y + 29, legend_x + 62, legend_y + 29), fill=(30, 65, 210), width=4)
        draw.polygon([(legend_x + 38, legend_y + 18), (legend_x + 26, legend_y + 40), (legend_x + 50, legend_y + 40)], fill=(30, 65, 210))
        draw.text((legend_x + 75, legend_y + 29), "N_CV", font=label_font, fill=axis, anchor="lm")
        draw.line((legend_x + 15, legend_y + 68, legend_x + 62, legend_y + 68), fill=(70, 70, 70), width=4)
        draw.ellipse((legend_x + 29, legend_y + 59, legend_x + 47, legend_y + 77), fill=(70, 70, 70))
        draw.text((legend_x + 75, legend_y + 68), "N_DL", font=label_font, fill=axis, anchor="lm")
        draw.text((width / 2, 28), "N_CV / N_DL Profile (log scale)", font=title_font, fill=axis, anchor="ma")
        draw.text((left + plot_w / 2, height - 42), "Profiling Distance W (nm)", font=label_font, fill=axis, anchor="ma")
        draw.text((36, top + plot_h / 2), "|Density| (cm^-3)", font=label_font, fill=axis, anchor="mm")
        return image

    def save_profile_png(self) -> None:
        if self.plot_window is None or not hasattr(self.plot_window, "profile_image"):
            return
        path = filedialog.asksaveasfilename(title="Profile PNG 저장", defaultextension=".png", initialfile="DLCP_NCV_NDL_vs_W.png", filetypes=[("PNG image", "*.png")])
        if path:
            self.plot_window.profile_image.save(path, dpi=(300, 300))
            self.status_var.set(f"그래프 PNG 저장 완료: {Path(path).name}")

    def export_results(self) -> None:
        if not self.results or not self.summary:
            messagebox.showinfo("알림", "먼저 분석을 실행하세요.")
            return
        folder = filedialog.askdirectory(title="결과 저장 폴더 선택")
        if not folder:
            return
        try:
            base = safe_name(self.device_var.get())
            summary_path = Path(folder) / f"{base}_summary.csv"
            detail_dir = Path(folder) / f"{base}_detail"
            detail_dir.mkdir(parents=True, exist_ok=True)
            self.write_csv(summary_path, self.summary, list(self.summary[0].keys()))
            detail_fields = ["bias_V", "Vac_input", "dV_pp", "C_raw_F", "C_smooth_F", "C_fit_F", "dCfit_dVpp_F_per_Vpp", "residual_F"]
            for item in self.results:
                rec = item["record"]
                rows = []
                for xin, xv, yv, sv, fv, dv in zip(item["x_input"], item["x"], item["y"], item["smooth_y"], item["fit_y"], item["derivative_fit"]):
                    rows.append({"bias_V": rec.bias, "Vac_input": xin, "dV_pp": xv, "C_raw_F": yv, "C_smooth_F": sv, "C_fit_F": fv, "dCfit_dVpp_F_per_Vpp": dv, "residual_F": yv - fv})
                path = detail_dir / f"{base}_bias_{rec.bias:+.6g}_{safe_name(Path(rec.path).stem)}.csv"
                self.write_csv(path, rows, detail_fields)
            settings = Path(folder) / f"{base}_settings.txt"
            settings.write_text("DLCP Batch Analyzer\n" + f"x column: {self.x_var.get()}\ny column: {self.y_var.get()}\ncapacitance unit: {self.y_unit_var.get()}\nVac convention: {self.vac_mode_var.get()}\ndV_pp conversion factor: {vac_factor(self.vac_mode_var.get()):.12g}\n" + "\n".join(f"{Path(r.path).name}\tbias={r.bias}\tepsilon_r={r.eps_r}\tarea_cm2={r.area_cm2}" for r in self.records), encoding="utf-8")
            self.status_var.set(f"저장 완료: {summary_path.name} 및 detail 폴더")
            messagebox.showinfo("저장 완료", f"요약 결과를 저장했습니다.\n{summary_path}")
        except Exception as exc:
            messagebox.showerror("저장 오류", str(exc))

    @staticmethod
    def write_csv(path: Path, rows: Sequence[dict], fields: Sequence[str]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: fmt(row.get(field, "")) for field in fields})

    def load_cached_csv(self, path: str) -> Tuple[List[str], List[List[str]]]:
        """Cache CSV parsing across preview and batch analysis.

        The cache is invalidated automatically when file size or modification time changes.
        This avoids reparsing large files while keeping the GUI safe for edited CSVs.
        """
        file_path = Path(path)
        stat = file_path.stat()
        signature = (stat.st_size, stat.st_mtime_ns)
        cached = self.csv_cache.get(path)
        if cached and cached[0] == signature:
            return cached[1], cached[2]
        headers, rows = read_csv_file(path)
        self.csv_cache[path] = (signature, headers, rows)
        return headers, rows


if __name__ == "__main__":
    app = DLCPApp()
    app.mainloop()
