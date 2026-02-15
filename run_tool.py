from cmd.baisc_api_to_mo import run_server
from cmd.loadind_list_ex import loading_list_init
from cmd.loading_list_ex_2 import run_extraction
from cmd.upload_loading_list_to_pb import run_ll_upload

if __name__ == '__main__':
    # loading_list_init()
    # run_server()
    # print(df)
    # run_extraction(r"C:\Users\skyli\Downloads\J03-G2-D14-DELTA-MFF-LOW-2ND-PCB-Dover Delta 2_79N7D-A00_Loading list_MECN007621_9-FEBRERO-2026.xlsx","J03_79N7D_A00")


    run_ll_upload(r"C:\data\ie_tool_v2\data\scm\loading_list\J02_79N7D_A00.json",ref="J02_79N7D_A00")
