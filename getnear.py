import os
import shelve
from contextlib import contextmanager
from enum import Enum, auto
from hashlib import md5
from pathlib import Path
from typing import Iterator, Optional

import requests
from bs4 import BeautifulSoup
from pytest import fixture, skip
from tabulate import tabulate

CONFIG_PATH = str(Path.home() / ".local" / "share" / "getnear")
K_COOKIES = "cookies"

PAGE_VLAN_CONFIG = "8021qCf"
PAGE_VLAN_MEMBERS = "8021qMembe"
PAGE_VLAN_PORT_PVIDS = "portPVID"

DEFAULT_PASSWORD = "password"

VLAN = int


class PortType(Enum):
    # An access port connects naive peripherals, tagging their traffic on
    # ingress, and stripping the vlan tag from traffic for that device on
    # egress.
    #
    # [U] in the UI.
    ACCESS = auto()

    # A trunk port connects switches and carries tagged traffic.
    #
    # [T] in the UI.
    TRUNK = auto()


# Helpful symbols
A = ACCESS = PortType.ACCESS
T = TRUNK = PortType.TRUNK

PortSpec = dict[VLAN, PortType]

API_SYMBOLS: dict[PortType | None, str] = {
    PortType.ACCESS: "1",
    PortType.TRUNK: "2",
    None: "3",
}

UI_SYMBOLS: dict[PortType | None, str] = {
    PortType.TRUNK: "T",
    PortType.ACCESS: "A",
    None: "\N{BULLET OPERATOR}",
}


def format_ports(ports: list[PortSpec]) -> str:
    vlans = calculate_vlans(ports)
    pvids = calculate_pvids(ports)
    memberships = calculate_memberships(ports)

    def build_headers():
        yield "PORT"
        yield "PVID"
        for vlan in sorted(vlans):
            yield vlan

    def format_port(index):
        yield index + 1
        yield pvids[index]
        for vlan in sorted(vlans):
            yield UI_SYMBOLS[memberships[vlan][index]]

    return tabulate(
        (format_port(i) for i, _ in enumerate(ports)),
        headers=build_headers(),
    )


def parse_html(html: bytes):
    return BeautifulSoup(html, features="lxml")


def encrypt_password(password: str, nonce: str):
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


def get_error_from(content: bytes) -> Optional[str]:
    error = parse_html(content).select_one("#err_msg")
    if error:
        return error.get("value")
    else:
        return None


def raise_error_from(content: bytes):
    if error := get_error_from(content):
        raise Exception(f"UI error: {error}")


def login(
    session: requests.Session,
    host: str,
    password: str,
):
    r = session.get(f"http://{host}/login.htm")
    nonce = parse_html(r.content).select_one("#rand")["value"]
    r = session.post(
        f"http://{host}/login.cgi",
        {
            "password": encrypt_password(password, nonce),
        },
    )

    if error := get_error_from(r.content):
        if "The password is invalid" in error:
            return False
        else:
            raise Exception(error)
    elif b"RedirectToIndexPage()" in r.content:
        session.get(f"http://{host}/index.htm")
        return True
    else:
        raise Exception("Unexpected response: {r.content}")


def change_password(
    session: requests.Session,
    host: str,
    old_password: str,
    new_password: str,
):
    print("Looking for change-password hash")
    r = session.get(
        f"http://{host}/pwd_ck.htm",
        headers={"Referer": f"http://{host}/index.htm"},
    )
    hash = parse_html(r.content).select_one("#hashEle")["value"]
    print(f"Changing password with {hash=}")
    session.post(
        f"http://{host}/changeDefPwd.cgi",
        {
            "hash": hash,
            "oldPassword": old_password,
            "newPassword": new_password,
        },
    )
    print("Password should now be changed")


def provision(
    session: requests.Session,
    host: str,
    password: str,
):
    r = session.get(
        f"http://{host}/index.htm",
        allow_redirects=True,
    )

    if b"Thank you for selecting NETGEAR products" in r.content:
        print("Already logged in with a valid cookie")
        return

    if b"RedirectToLoginPage()" not in r.content:
        raise Exception(f"unknown state for page: {r.content!r}")

    print("Need to login again and get a new cookie...")
    session.cookies.clear()

    print("Trying the default password...")
    if login(session, host, DEFAULT_PASSWORD):
        print("Need to change password...")
        change_password(session, host, DEFAULT_PASSWORD, password)
    else:
        print("Trying the custom password")
        if not login(session, host, password):
            raise Exception("Couldn't log in")

    print("We should now be logged in")


@contextmanager
def build_session() -> Iterator[requests.Session]:
    with shelve.open(CONFIG_PATH, "c") as shelf:
        session = requests.Session()
        if data := shelf.get(K_COOKIES):
            cookies = requests.utils.cookiejar_from_dict(data)
            session.cookies.update(cookies)
        yield session
        data = requests.utils.dict_from_cookiejar(session.cookies)
        shelf[K_COOKIES] = data


def vlan_cmd(
    session: requests.Session,
    host: str,
    command: str,
    **args,
):
    response1 = session.get(f"http://{host}/{command}.htm")
    hash_el = parse_html(response1.content).select_one("#hash")
    assert hash_el, f"no hash in {response1.content!r}"
    hash = hash_el["value"]
    data = dict(hash=hash, **args)
    response2 = session.post(f"http://{host}/{command}.cgi", data=data)
    raise_error_from(response2.content)


def set_802_1Q_status(
    session: requests.Session,
    host: str,
    is_enabled: bool,
):
    print(f"set 802.1Q status {is_enabled}")
    vlan_cmd(
        session,
        host,
        PAGE_VLAN_CONFIG,
        status=("Enable" if is_enabled else "Disable"),
    )


def add_vlan(
    session: requests.Session,
    host: str,
    vlan: VLAN,
):
    print(f"add vlan {vlan:4d}")
    vlan_cmd(
        session,
        host,
        PAGE_VLAN_CONFIG,
        status="Enable",
        ADD_VLANID=str(vlan),
        vlanNum="0",  # Doesn't seem to matter
        ACTION="Add",
        hiddVlan="",
    )


def set_port_pvid(
    session: requests.Session,
    host: str,
    pvid: VLAN,
    port_number: int,
):
    print(f"set pvid {pvid:4d} on port {port_number}")
    data = {
        "pvid": str(pvid),
        f"port{port_number}": "checked",
    }
    vlan_cmd(session, host, PAGE_VLAN_PORT_PVIDS, **data)


def set_vlan_members(
    session: requests.Session,
    host: str,
    vlan: VLAN,
    port_types: list[PortType | None],
):
    assert len(port_types) == 8
    ui_symbols = "".join(UI_SYMBOLS[t] for t in port_types)
    print(f"set vlan {vlan:4d} members {ui_symbols}")
    api_symbols = "".join(API_SYMBOLS[t] for t in port_types)
    vlan_cmd(
        session,
        host,
        PAGE_VLAN_MEMBERS,
        VLAN_ID=str(vlan),
        VLAN_ID_HD=str(vlan),
        hiddenMem=api_symbols,
    )


def calculate_vlans(ports: list[PortSpec]) -> set[VLAN]:
    return set(vlan for port in ports for vlan in port)


def calculate_pvids(ports: list[PortSpec]) -> list[VLAN]:
    def get_pvid(port: dict[VLAN, PortType]):
        access_vlans = [v for v, pt in port.items() if pt == PortType.ACCESS]
        if len(access_vlans) > 1:
            raise Exception(f"unknown PVID; port has >1 access VLANs: {port}")
        elif len(access_vlans) == 1:
            return access_vlans[0]
        else:
            return 1

    return [get_pvid(port) for port in ports]


def calculate_memberships(
    ports: list[PortSpec],
) -> dict[VLAN, list[PortType | None]]:
    return dict(
        (
            v,
            [p.get(v) for p in ports],
        )
        for v in calculate_vlans(ports)
    )


@fixture
def example():
    return [
        {1: A},
        {1: A, 12: T, 14: T},
        {1: A},
        {1: A},
        {12: A},
        {13: A},
        {14: A},
        {1: T, 12: T, 13: T, 14: T},
    ]


def test_calculations(example):
    _ = None
    assert calculate_vlans(example) == {1, 12, 13, 14}
    assert calculate_pvids(example) == [1, 1, 1, 1, 12, 13, 14, 1]
    assert calculate_memberships(example) == {
        VLAN(1): [A, A, A, A, _, _, _, T],
        VLAN(12): [_, T, _, _, A, _, _, T],
        VLAN(13): [_, _, _, _, _, A, _, T],
        VLAN(14): [_, T, _, _, _, _, A, T],
    }


def test_format(example):
    print("\n" + format_ports(example))


def test_real(example):
    var = "GETNEAR_TEST_HOST"
    if host := os.environ.get(var):
        sync_ports(host, "parsewort", example)
    else:
        skip("!!")


def sync_ports(host: str, password: str, ports: list[PortSpec]):
    with build_session() as session:
        provision(session, host, password)

    with build_session() as session:
        # Reset settings
        set_802_1Q_status(session, host, False)
        set_802_1Q_status(session, host, True)

        for vlan in calculate_vlans(ports):
            if vlan == VLAN(1):
                continue  # There by default
            add_vlan(session, host, vlan)

        # In order to juggle port PVIDs, every port has to initially be a
        # member of every VLAN.
        for vlan in calculate_vlans(ports):
            all_on: list[PortType | None] = [PortType.TRUNK for _ in ports]
            set_vlan_members(session, host, vlan, all_on)

        for index, pvid in enumerate(calculate_pvids(ports)):
            port_number = index + 1
            set_port_pvid(session, host, pvid, port_number)

        for vlan, port_types in calculate_memberships(ports).items():
            set_vlan_members(session, host, vlan, port_types)
