from getnear.logging import info
from getnear.config import Tagged, Untagged, Ignore

def sync(config, switch):
    ports, pvids, vlans = config

    vlan_ids = set(pvids) | set(vlans)
    for vlan_id in sorted(vlan_ids):
        info(f'adding vlan {vlan_id}')
        switch.add_vlan(vlan_id)

    for port, pvid in zip(ports, pvids):
        info(f'setting port {port} to PVID {pvid}')
        switch.set_port_pvid(port, pvid)

    for vlan_id, membership in vlans.items():
        info(f'vlan {vlan_id}')
        for port, status in zip(ports, membership):
            if status == Ignore:
                info(f'  port {port} off')
                switch.set_port_vlan_participation(port, vlan_id, False)
            else:
                is_tagged = status == Tagged
                symbol = 'T' if is_tagged else 'U'
                info(f'  port {port} {symbol}')
                switch.set_port_vlan_participation(port, vlan_id, True)
                switch.set_port_vlan_tagging(port, vlan_id, is_tagged)