import telnetlib
import time
from getnear.logging import info

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
                yield port, (is_included, is_tagged)

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
        self.t.write(b'enable\n') # Double newline
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
        pass
