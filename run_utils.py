import json
from datetime import datetime
from typing import List, Dict, Counter, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CONSUMPTION_URL = 'https://emdii-webtool.foxconn-na.com/api/getWO_PKGID?workorder='

def parse_created_date(value: str) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.strptime(value.strip(), "%a, %d %b %Y %H:%M:%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
def call_api(url, *, timeout=10, retries=3, backoff=0.5):
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


def summary_delivery(delivery_records: List[Dict[str, str]]):
    # Read a json file

    # {
    #     "CREATED_DATE": "Thu, 18 Dec 2025 11:55:42 GMT",
    #     "EMP_NUMBER": "45654",
    #     "HH_PN": "T-KMV0000-G",
    #     "LINE_NAME": "SMTJ11",
    #     "MFR_PN": "PM1A112-11DA3-4H",
    #     "PKG_ID": "MPT0002506032956",
    #     "QTY": 50,
    #     "REMAIN_QTY": 0,
    #     "REMARKS": "WH ASIGNATION",
    #     "WO": "000390018996",
    #     "rowNum": 1
    # }
    # Create a report

    _consumptionByPN = {i["HH_PN"]: {"items": [], "qtys": []} for i in delivery_records}

    for i in delivery_records:
        _consumptionByPN[i["HH_PN"]]["qtys"].append(i["QTY"])
        _consumptionByPN[i["HH_PN"]]["items"].append(f'{i["CREATED_DATE"]}@{i["EMP_NUMBER"]}@{i["PKG_ID"]}@{i["QTY"]}@{i["LINE_NAME"]}')

    _return_summary = []
    for pn, items in _consumptionByPN.items():
        _return_summary.append({"pn": pn, "reals": len(items["qtys"]), "qty": sum(items["qtys"]), "items": items["items"],
                                "std_pkg": Counter(items["qtys"]).most_common(1)[0][0]})

    print(json.dumps(_return_summary, indent=4))
    # save to file
    # with open("summary_consumption.json", "w") as f:
    #     json.dump(_return_summary, f, indent=4)
    # for pn, qtys in _consumptionByPN.items():
    #     print(pn, sum(qtys))


if __name__ == '__main__':

    _responds = call_api(CONSUMPTION_URL + '000390019075')

    if not _responds:
        print("No responds")

    summary_delivery(_responds)

