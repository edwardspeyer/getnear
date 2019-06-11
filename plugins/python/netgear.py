import httplib
import os
import re
import urllib

class Agent(object):
    def __init__(self, conn):
        self.conn = conn
        self.cookie = None

    def get(self, path, params={}):
        return self._request('GET', path, params)

    def post(self, path, params={}):
        return self._request('POST', path, params)

    def _request(self, method, path, params={}):
        body = urllib.urlencode(params)
        headers = {}
        if self.cookie is not None:
            headers['Cookie'] = self.cookie
        self.conn.request(method, path, body, headers)
        response = self.conn.getresponse()
        set_cookie = response.getheader('Set-Cookie')
        if set_cookie is not None:
            self.cookie = set_cookie.split(';')[0]
        return response


LOGIN = '/login.cgi'
LOGOUT = '/logout.cgi'
VLAN_CONFIG = '/8021qCf.cgi'
VLAN_MEMBERS = '/8021qMembe.cgi'
PORT_PVID = '/portPVID.cgi'

class Actions(object):
    def __init__(self, agent):
        self.agent = agent

    def login(self, password):
        self.agent.post(LOGIN, {'password': password})
    
    def logout(self):
        self.agent.get(LOGOUT)

    def is_advanced_VLAN_enabled(self):
        body = self.get_advanced_VLAN_status()
        for input in inputs(body):
            if (input['name'] == 'status') and ('checked' in input):
                return input['value'] == 'Enable'
        raise Exception("Could not find a checked radio button")

    def enable_advanced_VLAN(self):
        body = self.get_advanced_VLAN_status()
        hash = self.get_input(body, 'hash')
        self.agent.post(VLAN_CONFIG, {'status': 'Enable', 'hash': hash})

    def get_advanced_VLAN_status(self):
        return self.agent.get(VLAN_CONFIG).read()

    def get_vlans(self):
        body = self.get_advanced_VLAN_status()
        vlans = [
                int(input['value'])
                for input in inputs(body)
                if input['name'].startswith('vlanck')
                ]
        return sorted(vlans)

    def add_vlan(self, vlan_id):
        current_vlans = self.get_vlans()
        if vlan_id in current_vlans:
            return False
        index = len(current_vlans)
        body = self.get_advanced_VLAN_status()
        hash = self.get_input(body, 'hash')
        params = {
                'status': 'Enable',
                'ADD_VLANID': str(vlan_id),
                'vlanNum': len(current_vlans),
                'hash': hash,
                'ACTION': 'Add'
                }
        self.agent.post(VLAN_CONFIG, params)
        return True

    def delete_vlan(self, vlan_id):
        body = self.agent.get(VLAN_CONFIG).read()
        hash = self.get_input(body, 'hash')
        vlanck = next(
                i.get('name')
                for i in inputs(body)
                if i.get('name', '').startswith('vlanck')
                and i.get('value') == str(vlan_id)
                )
        vlan_num = next(
                i.get('value')
                for i in inputs(body)
                if i.get('name') == 'vlanNum'
                )
        params = {
                'status':       'Enable',
                'ADD_VLANID':   '',
                vlanck:         str(vlan_id),
                'vlanNum':      vlan_num,
                'hash':         hash,
                'ACTION':       'Delete',
                }
        self.agent.post(VLAN_CONFIG, params)

    def get_members(self, vlan_id):
        return self.get_or_set_members(vlan_id, None)

    def set_members(self, vlan_id, port_types):
        return self.get_or_set_members(vlan_id, port_types)

    def get_or_set_members(self, vlan_id, port_types):
        # Going to VLAN_MEMBERS returns a form for changing the VLAN with the
        # lowest number.
        #
        # Submit that form without changing anything to get the form we want.
        body = self.agent.get(VLAN_MEMBERS).read()
        hash = self.get_input(body, 'hash')
        encoded_membership = self.get_input(body, 'hiddenMem')
        option_re = '<option value="(\d+)"( selected)?>'
        current_vlan_id = next(
            int(id)
            for id, sel in re.findall(option_re, body)
            if sel is not ''
            )
        params = {
                'VLAN_ID': vlan_id,
                'hash': hash,
                'hiddenMem': encoded_membership,
                }

        body = self.agent.post(VLAN_MEMBERS, params).read()
        encoded_membership = self.get_input(body, 'hiddenMem')
        current_port_types = decode_membership(encoded_membership)

        if port_types is None:
            return current_port_types

        if current_port_types == port_types:
            return False

        hash = self.get_input(body, 'hash')
        encoded_membership = encode_membership(port_types)
        params = {
                'VLAN_ID': vlan_id,
                'hash': hash,
                'hiddenMem': encoded_membership,
                }
        self.agent.post(VLAN_MEMBERS, params)
        return True

    def get_input(self, body, name):
        return next(
                i['value']
                for i in inputs(body)
                if ('name' in i) and (i['name'] == name)
                )

    def get_pvids(self):
        body = self.agent.get(PORT_PVID).read()
        pvids_re = '<td class="def" sel="input">(\d+)'
        return [int(s) for s in re.findall(pvids_re, body)]

    def set_pvid(self, port_number, pvid):
        body = self.agent.get(PORT_PVID).read()
        hash = self.get_input(body, 'hash')
        port_key = 'port{}'.format(port_number)
        params = {
                'pvid': str(pvid),
                port_key: 'checked',
                'hash': hash,
                }
        body = self.agent.post(PORT_PVID, params).read()
        self.raise_errors(body)

    def raise_errors(self, body):
        error_re = "id='err_msg' value='(.+?)'"
        match = re.search(error_re, body)
        if match:
            raise Exception(match.groups()[0])

def inputs(html):
    result = {}
    matches = re.findall("<input(\s+.+?)>", html)
    return [
            dict(re.findall("\s+(\w+)(?:=['\"]?(\w+)['\"]?)?", match))
            for match in matches
            ]

# 31312 = _U_UT
PORT_UNTAGGED = 'U'
PORT_TAGGED = 'T'
PORT_NOT_A_MEMBER = '_'

PORT_TYPES = {
        '1': PORT_UNTAGGED,
        '2': PORT_TAGGED,
        '3': PORT_NOT_A_MEMBER,
        }

PORT_CODES = dict((v, k) for k, v in PORT_TYPES.iteritems())

def decode_membership(encoded_membership):
    return [PORT_TYPES[c] for c in encoded_membership]

def encode_membership(port_types):
    return ''.join(
            PORT_CODES[t] for t in port_types
            )

fqdn = '10.3.1.50'
password = 'password'
conn = httplib.HTTPConnection(fqdn, 80)
agent = Agent(conn)
actions = Actions(agent)

import yaml
ports_config = yaml.load(
        """
        - pvid: 1
          tagged: [1, 12, 13, 14, 15]
        - pvid: 12
          untagged: 12
        - pvid: 74
          untagged: 74
          tagged: [12, 15]
        - pvid: 99
          untagged: 99
        - pvid: 1
          tagged: [1, 12, 13, 14, 15]
        """)

class Config(object):
    def __init__(self, ports_config):
        self.ports_config = ports_config
    
    def ports(self):
        for pc in self.ports_config:
            pvid = pc['pvid']
            tagged = pc.get('tagged', [])
            if not isinstance(tagged, list):
                tagged = [tagged]
            untagged = pc.get('untagged', [])
            if not isinstance(untagged, list):
                untagged = [untagged]
            yield (pvid, tagged, untagged)

    def vlan_ids(self):
        all = [
                [[pvid], tagged, untagged]
                for (pvid, tagged, untagged) in self.ports()
                ]
        flat = [i for list1 in all for list2 in list1 for i in list2]
        return sorted(set(flat))

    def memberships(self):
        for vlan_id in self.vlan_ids():
            membership = [
                    (
                        PORT_TAGGED     if vlan_id in tagged else
                        PORT_UNTAGGED   if vlan_id in untagged else
                        PORT_NOT_A_MEMBER
                    )
                    for (pvid, tagged, untagged) in self.ports()
                    ]
            yield (vlan_id, membership)


config = Config(ports_config)

try:
    actions.login(password)
    if not actions.is_advanced_VLAN_enabled():
        print "ENABLE_VLAN"
        actions.enable_advanced_VLAN()

    did_change = False

    # Sync config to switch:
    for (vlan_id, membership) in config.memberships():
        print("ADD VLAN {}".format(vlan_id))
        if actions.add_vlan(vlan_id):
            did_change = True

        print("VLAN MEMBERSHIP {!r}".format(membership))
        if actions.set_members(vlan_id, membership):
            did_change = True

    for (port_index, (pvid, _, _)) in enumerate(config.ports()):
        print("PORT {} PVID {}".format(port_index, pvid))
        if actions.set_pvid(port_index, pvid):
            did_change = True

    # Delete unwanted config from switch:
    for vlan_id in actions.get_vlans():
        if vlan_id in config.vlan_ids():
            continue
        
        print("DELETE MEMBERSHIP {}".format(vlan_id))
        null_membership = [PORT_NOT_A_MEMBER for _ in config.ports()]
        if actions.set_members(vlan_id, null_membership):
            did_change = True

        print("DELETE VLAN {}".format(vlan_id))
        if actions.delete_vlan(vlan_id):
            did_change = True

finally:
    print "Logging out..."
    actions.logout()
