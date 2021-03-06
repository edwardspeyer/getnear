from getnear.config import Tagged, Untagged, Ignore
from getnear.logging import info
from lxml import etree
import re
import requests
import telnetlib


def connect(hostname, *args, **kwargs):
    url = f'http://{hostname}/'
    html = requests.get(url).text
    doc = etree.HTML(html)
    for title in doc.xpath('//title'):
        if re.match('NETGEAR GS\d+T', title.text):
            return TSeries(hostname, *args, **kwargs)


class TSeries:
    def __init__(self, hostname, password='password', old_password='password', debug=False):
        info('connecting')
        self.t = telnetlib.Telnet(hostname, 60000)
        if debug:
            self.t.set_debuglevel(2)

        info('entering admin mode')
        self.admin_mode()
        info('logging in')
        if self.login(password):
            return
        else:
            info('trying old password')
            self.admin_mode()
            if self.login(old_password):
                info('changing password')
                self.change_password(old_password, password)
            else:
                raise Exception('login failed')

    def admin_mode(self):
        self.t.read_until(b'please wait ...')
        self.t.write(b'admin\n')

    def login(self, password):
        self.t.read_until(b'Password:')
        self.t.write(password.encode('ascii'))
        self.t.write(b'\n')

        _, _, match = self.t.expect([b'>', b'Applying'])
        if b'Applying' in match:
            return False

        self.t.write(b'enable\n\n')
        self.t.read_until(b'#')
        return True

    def exit(self):
        # Leave "enable" mode
        self.t.write(b'exit\n')
        self.t.read_until(b'>')
        self.t.write(b'logout\n')

    def get_current_config(self):
        # (ports, pvids, {vlan_id -> {U, T, _, _...})
        ports_pvids = dict(self.get_port_pvids())
        ports = tuple(sorted(ports_pvids))
        pvids = tuple(ports_pvids[p] for p in ports)
        vlans = {}
        vlan_ids = set(pvids) | set(self.get_vlan_ids())
        for vlan_id in vlan_ids:
            port_map = dict(self.get_vlan(vlan_id))
            membership = tuple(port_map[p] for p in ports)
            vlans[vlan_id] = membership
        return (ports, pvids, vlans)

    def get_vlan_ids(self):
        self.t.write(b'show vlan brief\n')
        output = self.page().decode(errors='ignore')
        for line in output.splitlines():
            fields = line.split()
            if fields and fields[0].isnumeric():
                yield int(fields[0])

    def get_vlan(self, vlan_id):
        self.t.write(f'show vlan {vlan_id}\n'.encode())
        for line in self.paged_table_body():
            fields = line.split(maxsplit=3)
            interface_port, current = fields[0:2]
            interface, port = map(int, interface_port.split('/'))
            if interface == 0:
                port = int(interface_port.split('/')[1])
                is_included = current == 'Include'
                is_tagged = 'Tagged' in line
                if is_tagged:
                    state = Tagged
                elif is_included:
                    state = Untagged
                else:
                    state = Ignore
                yield port, state

    def get_port_pvids(self):
        self.t.write(b'show vlan port all\n')
        for line in self.paged_table_body():
            fields = line.split()
            interface_port, pvid_s = fields[0:2]
            interface, port = map(int, interface_port.split('/'))
            if interface == 0:
                pvid = int(pvid_s)
                yield port, pvid

    def set_port_pvid(self, port, vlan_id):
        self.do_configure_interface(port, f'vlan pvid {vlan_id}')

    def set_port_vlan_tagging(self, port, vlan_id, is_tagged):
        if is_tagged:
            command = f'vlan tagging {vlan_id}'
        else:
            command = f'no vlan tagging {vlan_id}'
        self.do_configure_interface(port, command)

    def set_port_vlan_participation(self, port, vlan_id, is_included):
        if is_included:
            command = f'vlan participation include {vlan_id}'
        else:
            command = f'vlan participation exclude {vlan_id}'
        self.do_configure_interface(port, command)

    def add_vlan(self, vlan_id):
        self.do_vlan_database(f'vlan {vlan_id}')

    def delete_vlan(self, vlan_id):
        self.do_vlan_database(f'no vlan {vlan_id}')

    def do_configure_interface(self, port, command):
        self.t.write(b'configure\n')
        self.t.read_until(b'#')
        self.t.write(f'interface 0/{port}\n'.encode())
        self.t.read_until(b'#')
        self.t.write((command + '\n').encode())
        self.t.read_until(b'#')
        self.t.write(b'exit\n')
        self.t.read_until(b'#')
        self.t.write(b'exit\n')
        self.t.read_until(b'#')

    def do_vlan_database(self, command):
        self.t.write(b'vlan database\n')
        self.t.read_until(b'#')
        self.t.write((command + '\n').encode())
        self.t.read_until(b'#')
        self.t.write(b'exit\n')
        self.t.read_until(b'#')

    def change_password(self, password_old, password_new):
        # TODO For this to work, we have to leave "enable" mode.  It would be
        # better if all other commands entererd enable mode instead.  More
        # verbose, but less confusing.  Maybe have a cursor to remember which
        # mode we are in?
        self.t.write(b'exit\n')
        self.t.read_until(b'>')
        self.t.write(b'passwd\n')
        self.t.read_until(b'Enter old password:')
        self.t.write((password_old + '\n').encode())
        self.t.read_until(b'Enter new password:')
        self.t.write((password_new + '\n').encode())
        self.t.read_until(b'Confirm new password:')
        self.t.write((password_new + '\n').encode())
        self.t.read_until(b'Password Changed!')
        self.t.write(b'enable\n')  # Double newline
        self.t.read_until(b'#')

    def paged_table_body(self):
        output = self.page().decode(errors='ignore')
        in_body = False
        for line in output.splitlines():
            if line.strip() == '':
                in_body = False
            if in_body:
                yield line
            if line and line[0:4] == '----':
                in_body = True

    def page(self):
        result = b''
        while True:
            index, _, output = self.t.expect([
                b'--More-- or \(q\)uit',
                b'#'
            ])
            result += output
            if index == 0:
                self.t.write(b'\n')
            else:
                break
        return result

    def sync(self, config):
        ports, pvids, vlans = config

        vlan_ids = set(pvids) | set(vlans)
        for vlan_id in sorted(vlan_ids):
            info(f'adding vlan {vlan_id}')
            self.add_vlan(vlan_id)

        for port, pvid in zip(ports, pvids):
            info(f'setting port {port} to PVID {pvid}')
            self.set_port_pvid(port, pvid)

        for vlan_id, membership in vlans.items():
            info(f'vlan {vlan_id}')
            for port, status in zip(ports, membership):
                if status == Ignore:
                    info(f'  port {port} off')
                    self.set_port_vlan_participation(port, vlan_id, False)
                else:
                    is_tagged = status == Tagged
                    symbol = 'T' if is_tagged else 'U'
                    info(f'  port {port} {symbol}')
                    self.set_port_vlan_participation(port, vlan_id, True)
                    self.set_port_vlan_tagging(port, vlan_id, is_tagged)
