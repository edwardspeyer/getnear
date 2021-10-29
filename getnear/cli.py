import optparse
from functools import reduce
from getnear import checkpoint
from getnear.config import validate, Tagged, Untagged, Ignore
from getnear.format import format_config
from getnear.switch import connect


def main(args=None):
    parser = optparse.OptionParser()

    parser.add_option('--hostname', metavar='HOSTNAME')
    parser.add_option('--password', metavar='PASSWORD', default='password')
    parser.add_option('--commit', action='store_true')
    parser.add_option('--no-commit', action='store_false', dest='commit')
    parser.add_option('--lazy', action='store_true')
    parser.add_option('--no-lazy', action='store_false', dest='lazy')

    options, args = parser.parse_args(args)

    if not options.hostname:
        parser.error('hostname is required')

    if not args:
        parser.error('no port specifications given')

    config = parse(args)

    print(format_config(options.hostname, config))
    time = checkpoint.is_unchanged(options.hostname, config)

    if time:
        print(f'config unchanged since {time}')
        if options.lazy:
            print(f'skipping unchanged config due to --lazy')
            return

    if options.commit:
        connect(
                options.hostname,
                password=options.password).sync(config)
        checkpoint.update(options.hostname, config)
    else:
        print('use --commit to commit changes')


def parse(tokens):
    tokens = tokens[:]

    port = None
    trunk_ports = {}
    access_ports = {}

    while tokens:
        token = tokens.pop(0)
        if token is None:
            break
        elif token == 'port':
            port = int(tokens.pop(0))
        elif token == 'access':
            vlan = int(tokens.pop(0))
            access_ports[port] = vlan
        elif token == 'trunk':
            vlans = set(expand(tokens.pop(0)))
            trunk_ports[port] = vlans
        elif token == ':':
            while tokens:
                if tokens[0] == 'port':
                    break
                tokens.pop(0)
        else:
            raise Exception(f'unrecognized token: {token}')

    # Default for trunk ports is vlan 1, unless explicitly said otherwise.
    for port in trunk_ports:
        if port not in access_ports:
            access_ports[port] = 1

    ports = tuple(sorted(set(access_ports) | set(trunk_ports)))
    pvids = tuple(access_ports[p] for p in ports)

    if not ports:
        raise Exception('ports must be defined as either access or trunk ports')

    vlan_ids = set(access_ports.values())
    if trunk_ports:
        vlan_ids |= reduce(set.union, trunk_ports.values())
    vlans = dict((v, [Ignore for _ in ports]) for v in vlan_ids)
    for port, vlan in access_ports.items():
        i = ports.index(port)
        vlans[vlan][i] = Untagged
    for port, trunked_vlans in trunk_ports.items():
        i = ports.index(port)
        for vlan in trunked_vlans:
            vlans[vlan][i] = Tagged

    config = (ports, pvids, vlans)
    return validate(config)


def expand(vlans_specification):
    for part in vlans_specification.split(','):
        if '-' in part:
            a, b = map(int, part.split('-'))
            for vlan in range(a, b+1):
                yield vlan
        else:
            yield int(part)


if __name__ == '__main__':
    main()
