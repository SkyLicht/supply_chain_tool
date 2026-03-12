import asyncio
import json
from collections import Counter
import pandas as pd
import requests

DFMS_GET_WO_PN_URL = 'https://emdii-webtool.foxconn-na.com/api/getWO_PKGID?'
POCKET_BASE_URL = "http://10.13.32.220:8090/api/collections/STD_PKG/records"
POCKET_BASE_GET_WO_URL = "http://10.13.32.220:8090/api/collections/WO_STATUS/records?perPage=1000"

# def get_wo_pn_deliver_to_production(wo: str):
#
#     res  = requests.get(f'{DFMS_GET_WO_PN_URL}workorder={wo}')
#     if res.status_code == 200:
#
#         return res.json()
#
#     else:
#         return []

async def get_wo_pn_deliver_to_production(wo: str):
    res = await asyncio.to_thread(requests.get, f"{DFMS_GET_WO_PN_URL}workorder={wo}")
    await asyncio.sleep(0.01)

    if res.status_code == 200:
        print("success ->",wo)
        return res.json()
    return []



async def get_all_wo() -> list[str]:
    res = await asyncio.to_thread(requests.get, POCKET_BASE_GET_WO_URL)
    if res.status_code != 200:
        return []
    _data = res.json()['items']
    extract_wo = [record['MO_NUMBER'] for record in _data]
    return extract_wo


async def update_std_pkg():
    def most_common_number(nums):
        if not nums:
            return None  # or raise ValueError
        return Counter(nums).most_common(1)[0][0]
    wos = await get_all_wo()

    # wos= ['000390019307']

    complete_data = []

    for wo in wos:
        data = await get_wo_pn_deliver_to_production(wo)

        for item in data:


            complete_data.append({
                'part_number': item['HH_PN'],
                'qty': item['QTY'],
                'pkg_id': item['PKG_ID'],
                'emp': item['EMP_NUMBER'],
                'line': item['LINE_NAME'],
                'date': item['CREATED_DATE'],
                'wo': item['WO'],
                'remark': item['REMARKS'],
            })

    # save in json file
    pd.DataFrame(complete_data).to_excel('pn_deliver_to_production.xlsx', index=False)


    unique_pn = set(item['part_number'] for item in complete_data)

    pn_dict = {pn: [] for pn in unique_pn}

    for item in complete_data:
        if item['pkg_id'][:2] in ['XR', 'HL']:
            continue
        pn_dict[item['part_number']].append(item['qty'])

    for pn, qtys in pn_dict.items():
        _mc = most_common_number(qtys)
        if not _mc:
            continue
        await asyncio.to_thread(
            requests.post,
            POCKET_BASE_URL,
            json={"part_number": pn, "std_pkg": _mc},
        )


    print('susccess')
