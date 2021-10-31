import tabulate

def format_config(config):
    buf = []
    ports, pvids, vlans = config
    vlan_ids = sorted(vlans.keys())
    headers = ['PORT', 'PVID', *vlan_ids]
    rows = []
    for port, pvid in zip(ports, pvids):
        i = ports.index(port)
        row = [port, pvid]
        for vlan_id in vlan_ids:
            s = vlans[vlan_id][i]
            row.append(s)
        rows.append(row)
    for line in tabulate.tabulate(rows, headers=headers).splitlines(keepends=True):
        buf.append('    ')
        buf.append(line)
    return ''.join(buf)
