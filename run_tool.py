from cmd.baisc_api_to_mo import run_server
from cmd.loadind_list_ex import loading_list_init
from cmd.loading_list_ex_2 import run_extraction
from cmd.upload_loading_list_to_pb import run_ll_upload
from pathlib import Path

if __name__ == '__main__':
    # loading_list_init()
    # run_server()
    # print(df)
    # name = "J01_XF2C1_A01"
    # run_extraction(r"C:\Users\jorgeortiza\OneDrive - Foxconn\IE\Materials\Loading List\{}.xlsx".format(name),name)
    #J03_J1WPC_A02

    run_ll_upload("http://10.13.32.220:8090",
                  r"C:\data\ie_tool_2_source\data\scm\loading_list\{}.json".format('J03_J1WPC_A02'), ref='J03_J1WPC_A02')
    # loading_dir = Path(r"C:\data\ie_tool_2_source\data\scm\loading_list")
    # file_names = sorted(p.stem for p in loading_dir.glob("*.json"))
    #
    # for n in file_names:
    #     run_ll_upload("http://10.13.32.220:8090",
    #                   r"C:\data\ie_tool_2_source\data\scm\loading_list\{}.json".format(n), ref=n)

    pass
