import pandas as pd


def report_swh_vs_sap():
    sap_inventory = pd.read_excel(
        r"C:\data\ie_tool_2_source\db\planing_db\ref_data\sLOC_1001.xlsx"
    )

    sap_inventory = sap_inventory[["Material", "Unrestricted"]]

    swh_inventory = pd.read_json(
        r"C:\data\ie_tool_2_source\db\planing_db\ref_data\swh_data.json"
    )
    swh_inventory = swh_inventory[swh_inventory["AREA_CODE"].isin(["W01", "W02"])]

    by_pn = swh_inventory.groupby("PN", as_index=False).agg(total_qty=("QTY", "sum"))

    sap_discrepancies = sap_inventory.merge(
        by_pn, left_on="Material", right_on="PN", how="left"
    )
    sap_discrepancies["total_qty"] = sap_discrepancies["total_qty"].fillna(0)
    sap_discrepancies["discrepancy"] = (
        sap_discrepancies["Unrestricted"] - sap_discrepancies["total_qty"]
    )

    sap_discrepancies = sap_discrepancies.sort_values(by="discrepancy", ascending=False)
    sap_discrepancies.reset_index(drop=True, inplace=True)

    sap_discrepancies = sap_discrepancies.drop(columns=["PN"])

    sap_discrepancies = sap_discrepancies.rename(
        columns={
            "Material": "pn",
            "Unrestricted": "sapQty",
            "total_qty": "swhQty",
            "discrepancy": "diff",
        }
    )
    #C:\data\ie_tool_2_source\db\planing_db\ref_data
    sap_discrepancies.to_json(
        r"C:\data\ie_tool_2_source\db\planing_db\ref_data\sap_discrepancies.json",
        orient="records",
    )
