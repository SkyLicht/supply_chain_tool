from __future__ import annotations
import re
import json
from typing import Any, Dict, List, Optional, Hashable
import pandas as pd


# XLSX_PATH = r"/mnt/data/YOUR_FILE.xlsx"


# ----------------------------
# Utilities
# ----------------------------

def norm_col(c: Any) -> str:
    s = "" if c is None else str(c)
    s = s.replace("\n", " ").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def find_header_row(df_raw: pd.DataFrame) -> Hashable | None:
    for i, row in df_raw.iterrows():
        text = " | ".join([str(x) for x in row if pd.notna(x)]).lower()
        if "track" in text and "h.h" in text:
            return i
    return None


def extract_sheet_meta(df_raw: pd.DataFrame, sheet_name: str) -> Dict[str, Optional[str]]:
    text = "\n".join(
        " | ".join([str(x) for x in row if pd.notna(x)])
        for _, row in df_raw.head(25).iterrows()
    )

    def grab(pattern: str):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    return {
        "sheet": sheet_name,
        "file_coding": grab(r"file coding\s*:\s*([A-Za-z0-9\-_]+)"),
        "rev": grab(r"\brev\s*:\s*([A-Za-z0-9\-_]+)"),
        "line": grab(r"\bline\s*:\s*([A-Za-z0-9\-_]+)"),
        "board_side": grab(r"board side\s*:\s*([A-Za-z0-9\-_]+)"),
        "machine": grab(r"machine\s*:\s*([A-Za-z0-9\-_]+)"),
        # "station_label": grab(r"\b([BT]\d{1,2}|BIOS|PCB|MA)\b"),
        "station_label": sheet_name,
    }


def discover_target_sheets(xlsx_path: str) -> List[str]:
    xls = pd.ExcelFile(xlsx_path)
    sheets = xls.sheet_names

    excluded = {"ECN", "DES","List"}
    return [s for s in sheets if s not in excluded]

def to_str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return ""
    return str(v).strip()

def to_num(v):
    """Return float if v looks numeric else None."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s == "":
        return None
    # remove commas if any
    s2 = s.replace(",", "")
    try:
        return float(s2)
    except:
        return None

def extract_quantity(row: pd.Series, col_qty: Optional[str], col_plate: Optional[str], df_cols: List[str]) -> Optional[float]:
    # 1) direct
    if col_qty:
        q = to_num(row.get(col_qty))
        if q is not None:
            return q

    # 2) try "just before plate type" (qty column is usually right before plate)
    if col_plate and col_plate in df_cols:
        plate_idx = df_cols.index(col_plate)
        if plate_idx > 0:
            candidate = to_num(row.get(df_cols[plate_idx - 1]))
            if candidate is not None:
                return candidate

    # 3) scan entire row: pick the best numeric candidate
    nums = []
    for c in df_cols:
        n = to_num(row.get(c))
        if n is not None:
            nums.append((c, n))

    if not nums:
        return None

    # If there is only one numeric value in the row, that's almost always QUANTITY
    if len(nums) == 1:
        return nums[0][1]

    # Otherwise, prefer smaller integers (typical qty: 1..99) and ignore huge values
    # Pick the first "reasonable" qty
    for _, n in nums:
        if 0 < n <= 999:
            return n

    return nums[0][1]  # fallback
# ----------------------------
# Core Logic
# ----------------------------

def build_station_object(xlsx_path: str, sheet: str) -> Optional[Dict]:

    df_raw = pd.read_excel(xlsx_path, sheet_name=sheet, header=None, dtype=object)

    header_row = find_header_row(df_raw)

    if header_row is None:
        return None

    header = extract_sheet_meta(df_raw, sheet)

    df = pd.read_excel(xlsx_path, sheet_name=sheet, header=header_row, dtype=object)
    df.columns = [norm_col(c) for c in df.columns]
    df_cols = list(df.columns)

    col_track = next((c for c in df.columns if "track" in c.lower()), None)
    col_hh = next((c for c in df.columns if "h.h" in c.lower()), None)
    col_feeder = next((c for c in df.columns if "feeder" in c.lower()), None)
    col_parts = next((c for c in df.columns if "parts" in c.lower()), None)
    col_nozzle = next((c for c in df.columns if "nozzle" in c.lower()), None)
    col_qty = next((c for c in df.columns if "quantity" in c.lower()), None)
    col_plate = next((c for c in df.columns if "plate" in c.lower()), None)
    col_loc = next((c for c in df.columns if "location" in c.lower()), None)

    materials = []
    current_primary = None
    alternates = []

    def clean(value):
        if value is None:
            return ""
        if isinstance(value, float) and pd.isna(value):
            return ""
        if pd.isna(value):
            return ""
        return str(value).strip()

    def finalize():
        nonlocal current_primary, alternates
        if current_primary:
            materials.append({
                "primary_hh_pn": clean(current_primary["hh"]),
                "track": clean(current_primary["track"]),
                "alternates_hh_pn": [clean(a) for a in alternates],
                "feeder_type": clean(current_primary.get("feeder_type")),
                "parts_type": clean(current_primary.get("parts_type")),
                "nozzle_type": clean(current_primary.get("nozzle_type")),
                "quantity": current_primary.get("quantity"),
                "plate_type": clean(current_primary.get("plate_type")),
                "location": clean(current_primary.get("location")),
            })
        current_primary = None
        alternates = []

    for _, r in df.iterrows():
        track = to_str(r.get(col_track)) if col_track else ""
        hh = to_str(r.get(col_hh)) if col_hh else ""

        # ✅ remove the 2 header rows that appear inside the body
        if track.lower() in ("track/z.no", "track", "item") and hh.lower() in ("h.h p/n", "h.h material no", "h.h"):
            continue
        if hh.lower() in ("h.h p/n", "h.h material no", "h.h"):
            continue

        if hh == "":
            continue

        if track == "@":
            alternates.append(hh)
            continue

        finalize()

        qty = extract_quantity(r, col_qty, col_plate, df_cols)

        current_primary = {
            "hh": hh,
            "track": track,
            "feeder_type": to_str(r.get(col_feeder)) if col_feeder else "",
            "parts_type": to_str(r.get(col_parts)) if col_parts else "",
            "nozzle_type": to_str(r.get(col_nozzle)) if col_nozzle else "",
            "quantity": qty,
            "plate_type": to_str(r.get(col_plate)) if col_plate else "",
            "location": to_str(r.get(col_loc)) if col_loc else "",
        }

    finalize()

    # Create station ID
    machine = header.get("machine") or "UNKNOWN"
    station_id = f"{sheet}_{machine}"

    return {
        "id": station_id,
        "header": header,
        "materials": materials
    }


# ----------------------------
# Main
# ----------------------------

def run_extraction(xlsx_path: str,name: str):

    sheets = discover_target_sheets(xlsx_path)
    stations = []

    for sheet in sheets:
        obj = build_station_object(xlsx_path, sheet)
        if obj:
            stations.append(obj)
            print(f"{sheet} processed")

    with open(f"{name}.json", "w", encoding="utf-8") as f:
        json.dump(stations, f, indent=2, ensure_ascii=False)

    print(f"\nTotal stations: {len(stations)}")
    print(f"Saved: {name}.json")


