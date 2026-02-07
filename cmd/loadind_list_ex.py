import json
from typing import List, Dict

import pandas as pd
from numpy.core.multiarray import item
from pydantic import BaseModel, Field


class Material(BaseModel):
    material: str
    is_primary: bool


class MaterialGroup(BaseModel):
    primary_pn: str
    track: str
    feeder_type: str
    request_qty: int
    location: List[str]
    materials: List[Material]
    machine_key: str
    tracks_key: str
    sides_key: str
    table_key: str

    def to_dict(self):
        return self.model_dump()


class Track(BaseModel):
    track: str
    qry: int
    MaterialGroup: str


class Table(BaseModel):
    id: str
    machine: str
    side: str
    table: str
    total_reals: int = 0
    total_request: int = 0
    material_groups: List[MaterialGroup]

    def summary(self):
        # self.material_groups.sort(key=lambda x: x.request_qty, reverse=True)
        self.total_reals = len(self.material_groups)
        self.total_request = sum([record.request_qty for record in self.material_groups])

    def summary_to_dict(self):
        return {
            "id": self.id,
            "machine": self.machine,
            "side": self.side,
            "table": self.table,
            "total_reals": self.total_reals,
            "total_request": self.total_request,
            "pn": [f"{record.track}_{record.table_key}_{record.primary_pn}_{record.request_qty}" for record in self.material_groups]
            # "pn": [sub.material for record in self.material_groups for sub in record.materials]
        }


class LoadingList(BaseModel):
    tables: List[Table] = Field(default_factory=list)

    def add_group_material_to_table_by_id(self, machine_id: str, material_group: MaterialGroup):
        # Try to find an existing table
        for table in self.tables:
            if table.id == machine_id:
                table.material_groups.append(material_group)
                return

        # If not found, create a new one
        new_table = Table(
            id=machine_id,
            machine=material_group.machine_key,
            side=material_group.sides_key,
            table=material_group.table_key,
            material_groups=[material_group]
        )
        self.tables.append(new_table)

    def summary_to_dict(self):
        return [f.summary_to_dict() for f in self.tables]

    def summary(self):
        for table in self.tables:
            table.summary()


def loading_list_init():
    df = pd.read_excel(r"C:\Users\jorgeortiza\Downloads\XF2C1.xlsx", engine="openpyxl", sheet_name="Lista")

    _temp_machine_dict: Dict[str, List[MaterialGroup]] = {}

    _materials_groups_list: List[MaterialGroup] = []
    _temp_material_groups: MaterialGroup | None = None

    for idx, row in df.iterrows():

        if row["TRACK/Z NO"] != "@":
            if _temp_material_groups is not None:
                _materials_groups_list.append(_temp_material_groups)
            _temp_material_groups = MaterialGroup(primary_pn=row["DELL PN"], feeder_type=row["FEEDER TYPE"] if pd.notna(
                row["FEEDER TYPE"]) else "nan",
                                                  request_qty=row["QTY"], track=row["PRIMARY TRACK"],
                                                  location=row["LOCATION"].split(','), materials=[
                    Material(material=row["HON HAI PN"], is_primary=True if row["TRACK/Z NO"] != "@" else False)],
                                                  machine_key=row["MACHINE"], tracks_key=row["TRACK/Z NO"],
                                                  sides_key=row["BOARD SIDE"], table_key=row["GROUP"])
        else:
            _temp_material_groups.materials.append(
                Material(material=row["HON HAI PN"], is_primary=True if row["TRACK/Z NO"] != "@" else False))

    for item in _materials_groups_list:
        _key = f"{item.machine_key}_{item.sides_key}_{item.table_key}"
        if _key not in _temp_machine_dict:
            _temp_machine_dict[_key] = []

        _temp_machine_dict[_key].append(item)

        # print(json.dumps(item.model_dump(), indent=4))
    # print(json.dumps(_temp_machine_dict, indent=4))
    _temp_table: LoadingList = LoadingList(tables=[])

    for k, v in _temp_machine_dict.items():
        # print(f"{k}: {len(v)}")
        for item in v:
            _temp_table.add_group_material_to_table_by_id(machine_id=k, material_group=item)

    _temp_table.summary()

    print(json.dumps(_temp_table.summary_to_dict(), indent=4))
