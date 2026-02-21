import argparse
import json
import re
from typing import Any, Dict, List, Optional


REQUIRED_FIELDS = ("PKG_ID", "PN", "QTY", "POSITION_CODE", "AREA_CODE")

POSITION_CODE_PATTERNS = (
    re.compile(r"^[A-Z]-\d+-\d+-\d+-\d+_[A-Z]$"),
    re.compile(r"^L\d+R\d+_\d+_[A-Z]$"),
)

AREA_CODE_PATTERN = re.compile(r"^W[T]?\d{2}$")

ALNUM_DASH_PATTERN = re.compile(r"^[A-Z0-9-]+$")


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == "" or value.strip().lower() in {"null", "none", "na", "n/a"}
    return False


def _is_int_like(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return value.is_integer()
    if isinstance(value, str) and value.strip().isdigit():
        return True
    return False


def _matches_any(patterns: List[re.Pattern], value: str) -> bool:
    return any(p.match(value) for p in patterns)


def validate_swh_json(json_path: str) -> Dict[str, Any]:
    """
    Read a JSON file and validate each record to find nulls or abnormal fields.
    Returns a dict with 'errors', 'warnings', and 'summary'.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not isinstance(data, list):
        return {
            "errors": [{"index": None, "field": None, "issue": "root_not_list", "value": type(data).__name__}],
            "warnings": [],
            "summary": {"records": 0, "errors": 1, "warnings": 0},
        }

    for idx, record in enumerate(data):
        if not isinstance(record, dict):
            errors.append({
                "index": idx,
                "pkg_id": None,
                "field": None,
                "issue": "record_not_object",
                "value": type(record).__name__,
            })
            continue

        pkg_id = record.get("PKG_ID")

        # Missing required fields
        for field in REQUIRED_FIELDS:
            if field not in record:
                errors.append({
                    "index": idx,
                    "pkg_id": pkg_id,
                    "field": field,
                    "issue": "missing_field",
                    "value": None,
                })

        # Null/empty fields
        for field in REQUIRED_FIELDS:
            if field in record and _is_null(record.get(field)):
                errors.append({
                    "index": idx,
                    "pkg_id": pkg_id,
                    "field": field,
                    "issue": "null_or_empty",
                    "value": record.get(field),
                })

        # PKG_ID
        if "PKG_ID" in record and not _is_null(pkg_id):
            pkg_str = str(pkg_id).strip().upper()
            if not ALNUM_DASH_PATTERN.match(pkg_str):
                warnings.append({
                    "index": idx,
                    "pkg_id": pkg_id,
                    "field": "PKG_ID",
                    "issue": "abnormal_format",
                    "value": pkg_id,
                })

        # PN
        pn = record.get("PN")
        if "PN" in record and not _is_null(pn):
            pn_str = str(pn).strip().upper()
            if not ALNUM_DASH_PATTERN.match(pn_str):
                warnings.append({
                    "index": idx,
                    "pkg_id": pkg_id,
                    "field": "PN",
                    "issue": "abnormal_format",
                    "value": pn,
                })

        # QTY
        qty = record.get("QTY")
        if "QTY" in record and not _is_null(qty):
            if not _is_int_like(qty):
                errors.append({
                    "index": idx,
                    "pkg_id": pkg_id,
                    "field": "QTY",
                    "issue": "not_integer",
                    "value": qty,
                })
            else:
                qty_int = int(float(qty))
                if qty_int <= 0:
                    errors.append({
                        "index": idx,
                        "pkg_id": pkg_id,
                        "field": "QTY",
                        "issue": "non_positive",
                        "value": qty,
                    })

        # POSITION_CODE
        pos = record.get("POSITION_CODE")
        if "POSITION_CODE" in record and not _is_null(pos):
            pos_str = str(pos).strip().upper()
            if not _matches_any(list(POSITION_CODE_PATTERNS), pos_str):
                warnings.append({
                    "index": idx,
                    "pkg_id": pkg_id,
                    "field": "POSITION_CODE",
                    "issue": "abnormal_format",
                    "value": pos,
                })

        # AREA_CODE
        area = record.get("AREA_CODE")
        if "AREA_CODE" in record and not _is_null(area):
            area_str = str(area).strip().upper()
            if not AREA_CODE_PATTERN.match(area_str):
                warnings.append({
                    "index": idx,
                    "pkg_id": pkg_id,
                    "field": "AREA_CODE",
                    "issue": "abnormal_format",
                    "value": area,
                })

    return {
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "records": len(data),
            "errors": len(errors),
            "warnings": len(warnings),
        },
    }


def print_warnings(result: Dict[str, Any]) -> None:
    warnings = result.get("warnings", [])
    if not warnings:
        print("No warnings.")
        return

    for item in warnings:
        idx = item.get("index")
        pkg_id = item.get("pkg_id")
        field = item.get("field")
        issue = item.get("issue")
        value = item.get("value")
        print(f"[{idx}] PKG_ID={pkg_id} FIELD={field} ISSUE={issue} VALUE={value}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate SWH JSON and print warnings.")
    parser.add_argument(
        "json_path",
        nargs="?",
        default=r"C:\data\ie_tool_v2\db\planing_db\swh_data.json",
        help="Path to swh_data.json",
    )
    args = parser.parse_args()

    result = validate_swh_json(args.json_path)
    print_warnings(result)
