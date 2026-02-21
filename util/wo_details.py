from __future__ import annotations

from collections import Counter
from typing import Dict, List

from pydantic import BaseModel
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

SAP_REQUIREMENT = "https://emdii-webtool.foxconn-na.com/api/get_wo_detail?workorder="


class Material(BaseModel):
    high_level_pn: str
    part_number: str
    is_primary: bool
    request_qty: int # Material request for this part number
    description: str
    item: str
    updated_by: str
    last_modified: str

    def to_summary(self):

        if self.request_qty == 0:
            return None
        return {
            "pn": self.part_number,
            "qty": self.request_qty,
            "is_primary": self.is_primary,
            "description": self.description,
            "item": self.item,
        }



class MaterialGroup(BaseModel):
    high_level_pn: str
    primary_pn: str
    request_qty: int # total of components needed for the total units to be produced
    consumption_qty: int # number of components consumed per unit
    attrition: int # extra components considering the scrapping
    total_consumption: int # total components needed for the total units to be produced plus scrapped components
    sku: str
    wo: str
    materials: List[Material]
    list_materials_str: List[str] = []
    pending_consumption: int = 0

    def to_summary(self):
        return {
            "pn": self.high_level_pn,
            "qty": self.request_qty,
            "consumption": self.consumption_qty,
            "attrition": self.attrition,
            "pending_consumption": self.pending_consumption,
            "materials": [
                material.to_summary() for material in self.materials if material.request_qty > 0
            ],
            "mat_list": self.list_materials_str
        }


def build_material_groups_from_details(details: List[Dict[str, str]]) -> List[MaterialGroup]:
    if not details:
        return []

    high_level_parts: List[Dict[str, str | int]] = []
    materials: List[Dict[str, str | int | bool]] = []
    group_request_qty: List[int] = []

    for item in details:
        if item["CONTAINER_NO"] == "X":
            high_level_parts.append(
                {
                    "high_level_pn": item["LINE_NAME"],
                    "request_qty": int(item["SECTION_NAME"]),
                    "consumption_qty": 0,
                    "sku": item["COL_15"],
                    "wo": item["WORK_ORDER"],
                }
            )
            group_request_qty.append(int(item["SECTION_NAME"]))
        else:
            materials.append(
                {
                    "high_level_pn": item["COL_15"],
                    "part_number": item["LINE_NAME"],
                    "is_primary": item["MODEL_NAME"] == "0010",
                    "request_qty": int(item["SECTION_NAME"]),
                    "description": item["PALLET_NO"],
                    "item": item["MODEL_NAME"],
                    "updated_by": item["COL_23"],
                    "last_modified": item["COL_24"],
                }
            )

    if not group_request_qty:
        return []

    total_pcb = Counter(group_request_qty).most_common(1)[0][0]

    for item in high_level_parts:
        item["consumption_qty"] = int(item["request_qty"] / total_pcb)

    groups: List[MaterialGroup] = []
    for item in high_level_parts:
        groups.append(
            MaterialGroup(
                high_level_pn=item["high_level_pn"],
                primary_pn="nan",
                request_qty=item["request_qty"],
                attrition=0,
                total_consumption=0,
                consumption_qty=int(item["consumption_qty"]),
                sku=item["sku"],
                wo=item["wo"],
                materials=[],
            )
        )

    for item in materials:
        for group in groups:
            if group.high_level_pn == item["high_level_pn"]:
                group.materials.append(Material(**item))
                group.total_consumption += int(item["request_qty"])

    for group in groups:
        group.attrition = group.total_consumption - group.request_qty
        for material in group.materials:
            group.list_materials_str.append(material.part_number)
            if material.is_primary:
                group.primary_pn = material.part_number

    return groups


def call_api(url: str, *, timeout: int = 10, retries: int = 3, backoff: float = 0.5):
    session = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))

    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.Timeout as e:
        raise RuntimeError(f"Request timed out after {timeout}s") from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error: {e.response.status_code}") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError("Request failed") from e
    except ValueError as e:
        raise RuntimeError("Invalid JSON response") from e


def get_wo_details(
    wo: str,
    base_url: str = SAP_REQUIREMENT,
) -> List[MaterialGroup]:
    response = call_api(f"{base_url}{wo}")
    return build_material_groups_from_details(response or [])
