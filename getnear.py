import shelve
from argparse import ArgumentParser
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import md5
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

CONFIG_PATH = Path.home() / ".local" / "share" / "getnear"
K_COOKIES = "cookies"

PAGE_VLAN_CONFIG = "8021qCf"
PAGE_VLAN_MEMBERS = "8021qMembe"
PAGE_VLAN_PORT_PVIDS = "portPVID"

VLAN = int
PortNumber = int

EXAMPLE_CONFIG = """\
trunk   1 12 14 15  : upstream
trunk   1 12 14 15  : switch02
trunk   1 12 14 15  : switch03
trunk   1 12 14 15  : switch04
access  15          : Huawei cat monitor
access  14          : Rostelecom smart fridge
access  1
access  1
"""


class Port:
    vlans: set[VLAN] = set()


class AccessPort(Port):
    """An access port connects naive peripherals, tagging their traffic on
    ingress, and stripping the vlan tag from traffic for that device on
    egress.

    [T] in the UI.
    """

    def __init__(self, vlan: VLAN):
        self.vlan = vlan
        self.vlans = {
            vlan,
        }


class TrunkPort(Port):
    """A trunk port connects switches and carries tagged traffic.

    [U] in the UI.
    """

    def __init__(self, *vlans: VLAN):
        assert VLAN(1) in vlans, "All trunk ports must carry vlan 1"
        self.vlans = set(vlans)


class UnusedPort(Port):
    pass


VLANs = set[VLAN]
PVIDs = dict[VLAN, set[PortNumber]]
Memberships = dict[VLAN, dict[PortNumber, type[Port]]]


@dataclass
class Layout:
    vlans: VLANs
    pvids: PVIDs
    memberships: Memberships

    def ports(self):
        return sorted(p for ps in self.pvids.values() for p in ps)

    def __str__(self):
        rows = []
        sorted_vlans = sorted(self.vlans)

        port_pvids = dict((p, v) for v, ps in self.pvids.items() for p in ps)

        for port in self.ports():
            row = [port, port_pvids[port]]
            for vlan in sorted_vlans:
                m = self.memberships[vlan][port]
                c = "\N{BULLET OPERATOR}" if m == UnusedPort else m.__name__[0]
                row.append(c)
            rows.append(row)
        headers = ["PORT", "PVID", *(str(v) for v in sorted_vlans)]
        return tabulate(rows, headers=headers)


API_SYMBOLS: dict[type[Port], str] = {
    TrunkPort: "1",
    AccessPort: "2",
    UnusedPort: "3",
}

UI_SYMBOLS: dict[type[Port], str] = {
    TrunkPort: "T",
    AccessPort: "A",
    UnusedPort: "-",
}


def as_screen(text):
    def inner():
        on = "\033[048;2;30;30;110m"
        off = "\033[0m"
        lines = text.splitlines()
        width = max(map(len, lines))
        indent = "  "
        yield ""
        yield indent + on + "┏" + ("━" * width) + "┓" + off
        for line in lines:
            yield indent + on + "┃" + line.ljust(width) + "┃" + off
        yield indent + on + "┗" + ("━" * width) + "┛" + off
        yield ""

    return "\n".join(inner())


def parse_html(html):
    return BeautifulSoup(html, features="lxml")


def is_login_page(response):
    doc = parse_html(response.content)
    return doc.select_one("#password") is not None


def encrypt_password(password, nonce):
    def merge(a: str, b: str):
        buf = ""
        for ca, cb in zip(a, b):
            buf += ca + cb
        off = min(map(len, (a, b)))
        buf += a[off:]
        buf += b[off:]
        return buf

    data = merge(password, nonce).encode()
    return md5(data).hexdigest()


def raise_error_from(response):
    error = parse_html(response.content).select_one("#err_msg")
    if not error:
        return response
    if message := error["value"]:
        raise Exception(message)


def is_logged_in(session, url):
    response = session.get(f"http://{url}/index.htm")
    return b"Switch Information" in response.content


def login(session, host, password):
    print("Logging in")
    login_page = session.get(f"http://{host}/login.htm").content
    rand = parse_html(login_page).select_one("#rand")["value"]
    response = session.post(
        f"http://{host}/login.cgi",
        data=dict(
            password=encrypt_password(password, rand),
        ),
    )
    raise_error_from(response)


@contextmanager
def build_session():
    with shelve.open(CONFIG_PATH, "c") as shelf:
        session = requests.Session()
        if data := shelf.get(K_COOKIES):
            cookies = requests.utils.cookiejar_from_dict(data)
            session.cookies.update(cookies)
        yield session
        data = requests.utils.dict_from_cookiejar(session.cookies)
        shelf[K_COOKIES] = data


def _vlan_cmd(session, host, command, **args):
    response = session.get(f"http://{host}/{command}.htm")
    doc = parse_html(response.content)
    hash = doc.select_one("#hash")["value"]
    data = dict(hash=hash, **args)
    response = session.post(f"http://{host}/{command}.cgi", data=data)
    raise_error_from(response)


def set_802_1Q_status(session, host, is_enabled):
    print(f"set 802.1Q status {is_enabled}")
    _vlan_cmd(
        session,
        host,
        PAGE_VLAN_CONFIG,
        status=("Enable" if is_enabled else "Disable"),
    )


def add_vlan(session, host, vlan):
    print(f"add vlan {vlan}")
    _vlan_cmd(
        session,
        host,
        PAGE_VLAN_CONFIG,
        status="Enable",
        ADD_VLANID=str(vlan),
        vlanNum="0",  # Doesn't seem to matter
        ACTION="Add",
        hiddVlan="",
    )


def set_port_pvid(session, host, pvid, port_numbers):
    print(f"set pvid {pvid} on ports {port_numbers}")
    data = {}
    data["pvid"] = str(pvid)
    for port_number in port_numbers:
        data[f"port{port_number}"] = "checked"
    _vlan_cmd(session, host, PAGE_VLAN_PORT_PVIDS, **data)


def set_vlan_members(session, host, vlan, ports):  # TODO types
    assert len(ports) == 8
    port_types = [ports[k] for k in sorted(ports)]
    ui_symbols = "".join(UI_SYMBOLS[t] for t in port_types)
    print(f"set vlan {vlan} members {ui_symbols}")
    api_symbols = "".join(API_SYMBOLS[t] for t in port_types)
    _vlan_cmd(
        session,
        host,
        PAGE_VLAN_MEMBERS,
        VLAN_ID=str(vlan),
        VLAN_ID_HD=str(vlan),
        hiddenMem=api_symbols,
    )


def convert_to_layout(ports: list[Port]) -> Layout:
    # numbered_ports = [(PortNumber(i + 1), p) for i, p in enumerate(ports)]
    # TODO ^^ use this

    # Gather known VLANs
    vlans = set(v for p in ports for v in p.vlans) | {VLAN(1)}

    # Access ports get their PVID set, otherwise use 1
    pvids: dict[VLAN, set[PortNumber]] = dict((v, set()) for v in vlans)
    for i, port in enumerate(ports):
        port_number = PortNumber(i + 1)
        if isinstance(port, AccessPort):
            pvids[port.vlan].add(port_number)
        else:
            # PVID for a trunk port should be 1
            pvids[1].add(port_number)

    # Port memberships for each vlan.
    memberships: Memberships = {}
    for vlan in vlans:
        mem = {}
        for i, port in enumerate(ports):
            pn = PortNumber(i + 1)
            if vlan in port.vlans:
                mem[pn] = type(port)
            else:
                mem[pn] = UnusedPort
        memberships[vlan] = mem

    return Layout(vlans, pvids, memberships)


def test_layout():
    ports = [
        TrunkPort(1, 12),
        TrunkPort(1, 14),
        TrunkPort(1, 12, 14),
        AccessPort(1),
        AccessPort(12),
        AccessPort(1),
        AccessPort(1),
        AccessPort(14),
    ]
    expected = Layout(
        {
            VLAN(1),
            VLAN(12),
            VLAN(14),
        },
        {
            VLAN(1): {
                PortNumber(1),
                PortNumber(2),
                PortNumber(3),
                PortNumber(4),
                PortNumber(6),
                PortNumber(7),
            },
            VLAN(12): {
                PortNumber(5),
            },
            VLAN(14): {
                PortNumber(8),
            },
        },
        {
            VLAN(1): {
                PortNumber(1): TrunkPort,
                PortNumber(2): TrunkPort,
                PortNumber(3): TrunkPort,
                PortNumber(4): AccessPort,
                PortNumber(5): UnusedPort,
                PortNumber(6): AccessPort,
                PortNumber(7): AccessPort,
                PortNumber(8): UnusedPort,
            },
            VLAN(12): {
                PortNumber(1): TrunkPort,
                PortNumber(2): UnusedPort,
                PortNumber(3): TrunkPort,
                PortNumber(4): UnusedPort,
                PortNumber(5): AccessPort,
                PortNumber(6): UnusedPort,
                PortNumber(7): UnusedPort,
                PortNumber(8): UnusedPort,
            },
            VLAN(14): {
                PortNumber(1): UnusedPort,
                PortNumber(2): TrunkPort,
                PortNumber(3): TrunkPort,
                PortNumber(4): UnusedPort,
                PortNumber(5): UnusedPort,
                PortNumber(6): UnusedPort,
                PortNumber(7): UnusedPort,
                PortNumber(8): AccessPort,
            },
        },
    )
    actual = convert_to_layout(ports)
    assert actual == expected


def sync(host, password, layout):
    with build_session() as session:
        # Log in
        response = session.get(
            f"http://{host}/index.htm",
            allow_redirects=True,
        )
        if b"RedirectToLoginPage" in response.content:
            login(session, host, password)

    with build_session() as session:
        # Reset settings
        set_802_1Q_status(session, host, False)
        set_802_1Q_status(session, host, True)

        for vlan in layout.vlans:
            if vlan == VLAN(1):
                continue  # There by default
            add_vlan(session, host, vlan)
            # In order to juggle port PVIDs, every port has to initially be a
            # member of every VLAN.
            all_on = dict((p, TrunkPort) for p in layout.ports())
            set_vlan_members(session, host, vlan, all_on)

        for vlan, port_numbers in layout.pvids.items():
            set_port_pvid(session, host, vlan, port_numbers)

        for vlan, ports in layout.memberships.items():
            set_vlan_members(session, host, vlan, ports)


def main():
    def trunk_port(vlans_string: str):
        vlans = {int(v) for v in vlans_string.split(",")}
        return TrunkPort(*vlans)

    def access_port(vlan_string: str):
        vlan = int(vlan_string)
        return AccessPort(vlan)

    parser = ArgumentParser()
    parser.add_argument("hostname")
    parser.add_argument("password")
    parser.add_argument(
        "--trunk-port",
        type=trunk_port,
        dest="ports",
        action="append",
    )
    parser.add_argument(
        "--access-port",
        type=access_port,
        dest="ports",
        action="append",
    )
    args = parser.parse_args()
    layout = convert_to_layout(args.ports)
    print(layout)
    sync(args.hostname, args.password, layout)


if __name__ == "__main__":
    main()
