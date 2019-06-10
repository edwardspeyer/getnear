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
        print("SETTING {} to {!r} / {}".format(
            vlan_id,
            port_types,
            encoded_membership
            ))
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
        print(params)
        body = self.agent.post(PORT_PVID, params).read()

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
PORT_UNTAGGED = 'UNTAGGED'
PORT_TAGGED = 'TAGGED'
PORT_NOT_A_MEMBER = 'NOT_A_MEMBER'

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

try:
    actions.login(password)
    if not actions.is_advanced_VLAN_enabled():
        print "ENABLE_VLAN"
        actions.enable_advanced_VLAN()

    print actions.add_vlan(7)

    print actions.get_members(148)

    print actions.set_members(
            148,
            [
                PORT_UNTAGGED,
                PORT_TAGGED,
                PORT_TAGGED,
                PORT_UNTAGGED,
                PORT_NOT_A_MEMBER,
            ]
        )

    print actions.get_pvids()

    print actions.set_pvid(3, 14)
finally:
    print "Logging out..."
    actions.logout()
