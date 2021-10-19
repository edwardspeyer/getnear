Tagged = 'T'
Untagged = 'U'
Ignore = '_'

def parse(tokens):
    groups = []
    cur = None

    for token in tokens:
        if token in {'ports', 'pvids', 'vlan'}:
            cur = []
            groups.append(cur)
        cur.append(token)

    vlans = {}
    for group in groups:
        if group[0] == 'ports':
            ports = list(map(int, group[1:]))
        if group[0] == 'pvids':
            pvids = list(map(int, group[1:]))
        if group[0] == 'vlan':
            vlan_id_s, *membership = group[1:]
            vlan_id = int(vlan_id_s)
            for member in membership:
                assert member in {'T', 'U', '_'}
            vlans[vlan_id] = membership

    assert len(ports) == len(pvids)
    for membership in vlans.values():
        assert len(ports) == len(membership)

    config = (ports, pvids, vlans)
    return validate(config)


def validate(config):
    ports, pvids, vlans = config
    # If a port is in a pvid, it must be a member of that vlan too
    for port, pvid in zip(ports, pvids):
        if pvid not in vlans:
            raise
        membership = vlans[pvid]
        state = dict(zip(ports, membership))[port]
        if state == Ignore:
            raise Exception(
                    f'port {port} is in pvid {pvid} '
                    f'but is not a member of the same vlan: {membership}')
    return config


if __name__ == '__main__':
    Example = '''
    ports   01 02 03 04 05 06 07 08
    pvids   01 15 12 35 01 01 01 01
    vlan 01  T  T  _  _  U  _  _  _
    vlan 12  T  _  U  _  U  _  _  _
    vlan 15  T  T  _  _  U  _  _  _
    vlan 35  T  _  _  U  U  U  U  U
    '''

    parse(Example.split())
