import requests
from lxml import etree
import logging
from getnear import config

logging.getLogger('urllib3').setLevel(logging.WARNING)

VLAN_CONFIG = '/8021qCf.cgi'
VLAN_MEMBERS = '/8021qMembe.cgi'
PORT_PVID = '/portPVID.cgi'
    
CODES = {
        '3': config.Ignore,
        '2': config.Tagged,
        '1': config.Untagged,
        }


class ESeries:
    def __init__(self, hostname, password, old_password='password'):
        self.session = requests.session()
        self.hostname = hostname
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
        try:
            v = self.post(VLAN_CONFIG, params)
        except Exception as ex:
            if 'Duplicated VLAN ID not allowed!' in str(ex):
                # Idempotency is not an exception :P
                pass
            else:
                raise

    def delete_vlan(self, vlan_id):
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
        html = self.get(VLAN_MEMBERS)
        doc = etree.HTML(html)
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
        params = {
                f'port{port}': 'checked',
                'pvid': vlan_id,
                'hash': hash,
                }
        html = self.post(PORT_PVID, params)

    def set_membership(self, vlan_id):
        pass

    def set_port_vlan_participation(self, port, vlan_id, is_included):
        pass

    def set_port_vlan_tagging(self, port, vlan_id, is_tagged):
        pass

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
