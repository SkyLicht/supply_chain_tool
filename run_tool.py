from cmd.baisc_api_to_mo import run_server
from cmd.loadind_list_ex import loading_list_init
from cmd.loading_list_ex_2 import run_extraction
from cmd.upload_loading_list_to_pb import run_ll_upload

if __name__ == '__main__':
    # loading_list_init()
    # run_server()
    # print(df)
    # run_extraction(r"C:\Users\jorgeortiza\OneDrive - Foxconn\IE\Materials\Loading List\J02_1P8W3_A02.xlsx","J02_1P8W3_A02")

    run_ll_upload("http://10.13.32.220:8090",
                  r"C:\data\ie_tool_2_source\data\scm\loading_list\J02_1P8W3_A02.json", ref="J02_1P8W3_A02")

    pass