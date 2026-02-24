
import asyncio

from cmd.smw_demand import step_1, ana_main
from migrate.swh_to_pkg_id import swh_to_pkg_id
from util.get_wo_pn_deliver_to_production import get_wo_pn_deliver_to_production, update_std_pkg

if __name__ == '__main__':
    # ana_main()
    # swh_to_pkg_id()
    asyncio.run(update_std_pkg())
