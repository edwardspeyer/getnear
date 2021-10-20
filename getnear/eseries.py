from getnear import config
from getnear.logging import info
from lxml import etree
import logging
import re
import requests

logging.getLogger('urllib3').setLevel(logging.WARNING)

VLAN_CONFIG = '/8021qCf.cgi'
VLAN_MEMBERS = '/8021qMembe.cgi'
PORT_PVID = '/portPVID.cgi'
    
CODES = {
        '3': config.Ignore,
        '2': config.Tagged,
        '1': config.Untagged,
        }

def connect(hostname, *args, **kwargs):
    url = f'http://{hostname}/login.cgi'
    html = requests.get(url).text
    doc = etree.HTML(html)
    for info in doc.xpath('//div[@class = "switchInfo"]'):
        md = re.match('GS\d+Ev(\d)', info.text)
        if not md:
            return
        version = int(md.groups()[0])
        kwargs['version'] = version
        return ESeries(hostname, *args, **kwargs)


class ESeries:
    def __init__(self, hostname, password, old_password='password', debug=False, version=3):
        self.session = requests.session()
        self.hostname = hostname
        self.version = version
        self.login(password, old_password)

    def __del__(self):
        self.logout()

    def login(self, password, old_password):
        html = self.post('/login.cgi', {'password': password})
        if 'Maximum sessions reached' in html:
            raise Exception('max sessions')
        return 'RedirectToIndexPage' in html

    def post(self, path, data):
        url = f'http://{self.hostname}{path}'
        response = self.session.post(url, data=data)
        self.rethrow_error_message(response.text)
        return response.text

    def get(self, path):
        url = f'http://{self.hostname}{path}'
        response = self.session.get(url)
        self.rethrow_error_message(response.text)
        return response.text

    def rethrow_error_message(self, html):
        doc = etree.HTML(html)
        errors = list(filter(len, doc.xpath('//input[@id = "err_msg"]/@value')))
        if errors:
            raise Exception('; '.join(errors))

    def logout(self):
        self.get('/logout.cgi')

    def add_vlan(self, vlan_id):
        html = self.get(VLAN_CONFIG)
        doc = etree.HTML(html)
        hash = doc.xpath('//input[@name="hash"]/@value')[0]
        vlan_num = doc.xpath('//input[@name="vlanNum"]/@value')[0]
        params = {
            'status':       'Enable',
            'hiddVlan':     '',
            'ADD_VLANID':   str(vlan_id),
            'vlanNum':      vlan_num,
            'hash':         hash,
            'ACTION':       'Add',
            }
        self.post(VLAN_CONFIG, params)

    def delete_vlan(self, vlan_id):
        # The old version of this method said that claimed that an empty
        # `hiddVlan` parameter was needed due to "another v2 (GS108) quirk".
        # That seems to work fine for GS108Ev3 as well.
        html = self.get(VLAN_CONFIG)
        doc = etree.HTML(html)
        hash = doc.xpath('//input[@name="hash"]/@value')[0]
        vlan_num = doc.xpath('//input[@name="vlanNum"]/@value')[0]
        vlanck = doc.xpath(
                f'//input[@value = {vlan_id} and '
                'starts-with(@name, "vlanck")]/@name')[0]
        params = {
                'status':       'Enable',
                'hiddVlan':     '',
                'ADD_VLANID':   '',
                vlanck:         str(vlan_id),
                'vlanNum':      vlan_num,
                'hash':         hash,
                'ACTION':       'Delete',
                }
        self.post(VLAN_CONFIG, params)

    def get_port_vlan_membership(self, vlan_id):
        # The older version of this method said that, as "a quirk of firmware
        # v2 (on GS108v3)", fetching another vlan membership would only work if
        # you submit the current vlan data using `hiddenMem` and `VLAN_ID_HD`.
        #
        # It doesn't look like that's the case any more.
        html = self.get(VLAN_MEMBERS)
        doc = etree.HTML(html)

        currently_shown_vlan_id = int(doc.xpath(
                '//select[@id = "vlanIdOption"]'
                '/option[@selected]'
                '/@value')[0])

        # By default, the VLAN_MEMBERS page loads with the members for one of
        # the vlans, usually 1.  If it doesn't we have to reload the page:
        if vlan_id != currently_shown_vlan_id:
            hash = doc.xpath('//input[@name="hash"]/@value')[0]
            params = {
                    'VLAN_ID': str(vlan_id),
                    'hash': hash,
                    }
            html = self.post(VLAN_MEMBERS, params)
            doc = etree.HTML(html)

        code = doc.xpath('//input[@name = "hiddenMem"]/@value')[0]
        return tuple(CODES[c] for c in code)

    def set_port_vlan_membership(self, vlan_id, membership):
        html = self.get(VLAN_MEMBERS)
        doc = etree.HTML(html)
        hash = doc.xpath('//input[@name="hash"]/@value')[0]
        chars = dict((v, k) for k, v in CODES.items())
        code = ''.join(chars[m] for m in membership)
        params = {
                'VLAN_ID': str(vlan_id),
                'VLAN_ID_HD': str(vlan_id),
                'hash': hash,
                'hiddenMem': code,
                }
        html = self.post(VLAN_MEMBERS, params)
    
    def get_port_pvid(self, port_index):
        self.browser.get(Actions.PORT_PVID)
        html = self.browser.page.html
        pvids_re = '<td class="def" sel="input">(\d+)'
        pvids = [int(s) for s in re.findall(pvids_re, html)]
        return pvids[port_index]

    def set_port_pvid(self, port, vlan_id):
        html = self.get(PORT_PVID)
        doc = etree.HTML(html)
        hash = doc.xpath('//input[@name="hash"]/@value')[0]

        if self.version <= 2:
            # Quirk fix: the GS105Ev2 the port parameter is named (port0,
            # port1, ...), but on the GS108Ev3 they are (port1, port2, ...).
            # The previous guess was that this is a v2 specific thing.
            port_index = port - 1
        else:
            port_index = port
        params = {
                f'port{port_index}': 'checked',
                'pvid': vlan_id,
                'hash': hash,
                }
        html = self.post(PORT_PVID, params)

    def get_vlan_ids(self):
        html = self.get(VLAN_CONFIG)
        for input in etree.HTML(html).xpath('//input'):
            if input.get('name').startswith('vlanck'):
                vlan_id_s = input.get('value')
                yield int(vlan_id_s)

    def is_vlans_enabled(self):
        html = self.get(VLAN_CONFIG)
        elements = etree.HTML(html).xpath('//input[@name="status" and @checked]')
        return bool(elements)

    def enable_vlans(self):
        html = self.get(VLAN_CONFIG)
        hash = etree.HTML(html).xpath('//input[@name="hash"]/@value')[0]
        self.post(VLAN_CONFIG, {'status': 'Enable', 'hash': hash})

    def sync(self, config):
        ports, pvids, vlans = config

        self.enable_vlans()
        todo = set(pvids) | set(vlans)
        done = set(self.get_vlan_ids())
        info(f'all vlan ids {sorted(todo)}')
        for vlan_id in todo - done:
            info(f'adding new vlan {vlan_id}')
            self.add_vlan(vlan_id)

        for port, pvid in zip(ports, pvids):
            info(f'setting port pvid for {port} to {pvid}')
            # To change a port's PVID it must be a member first
            i = ports.index(port)
            membership = vlans[pvid]
            state = membership[i]
            current_membership = list(self.get_port_vlan_membership(pvid))
            updated_membership = current_membership[:]
            updated_membership[i] = membership[i]
            info(f'vlan {pvid} current membership: {current_membership}')
            info(f'vlan {pvid} updated membership: {updated_membership}')
            if updated_membership != current_membership:
                info(
                        f'updating membership for vlan {pvid} '
                        f'prior to changing port {port} pvid to {pvid}')
                self.set_port_vlan_membership(pvid, updated_membership)

            # Now we can change the port PVIDs
            info(f'setting port {port} to pvid {pvid}')
            self.set_port_pvid(port, pvid)

        # Now fix up all the memberships
        for vlan_id, membership in vlans.items():
            info(f'setting port membership for vlan {vlan_id}')
            self.set_port_vlan_membership(vlan_id, membership)
