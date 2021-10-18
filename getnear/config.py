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

    return (ports, pvids, vlans)


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
