Tagged = 'T'
Untagged = 'U'
Ignore = '_'

Trunk = 'Trunk'
Unused = 'Unused'


def simple(*tokens):
    ports = tuple(range(1, len(tokens) + 1))
    pvids = tuple(1 if t in {Trunk, Unused} else t for t in tokens)

    empty = list(Ignore for _ in ports)
    vlans = dict((vlan, empty[:]) for vlan in pvids)
    vlans[1] = empty[:]

    for index, token in enumerate(tokens):
        if token is Trunk:
            for vlan in vlans:
                vlans[vlan][index] = Tagged
        elif token is Unused:
            vlans[1][index] = Untagged
        else:
            vlans[token][index] = Untagged

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
                f'but is not a member of the same vlan: '
                f'{membership}')
    return config
