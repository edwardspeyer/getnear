def diff(config_from, config_to):
    a = config_from
    b = config_to

    a_ports, a_pvids, a_vlans = a
    b_ports, b_pvids, b_vlans = b

    ports = b_ports
    pvids = [None for _ in b_ports]
    vlans = {}

    for i, port in enumerate(ports):
        pvids[i] = b_pvids[i] if a_pvids[i] != b_pvids[i] else None

    for vlan_id in b_vlans:
        a_membership = a_vlans[vlan_id]
        b_membership = b_vlans[vlan_id]
        vlans[vlan_id] = tuple(
            b_state if b_state != a_state else None
            for a_state, b_state in zip(a_membership, b_membership))

    config = (ports, pvids, vlans)
    return config
