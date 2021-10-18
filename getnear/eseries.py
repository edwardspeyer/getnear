from urllib.request import HTTPCookieProcessor, build_opener
from http.cookiejar import CookieJar


class ESeries:
    def __init__(self, hostname, password, old_password='password'):
        jar = CookieJar()
        processor = HTTPCookieProcessor(jar)
        self.opener = build_opener(processor)
        self.hostname = hostname
        self.login(password, old_password)

    def login(self, password, old_password):
        pass

    def add_vlan(self, vlan_id):
        pass

    def set_port_pvid(self, port, vlan_id):
        pass

    def set_port_vlan_participation(self, port, vlan_id, is_included):
        pass

    def set_port_vlan_tagging(self, port, vlan_id, is_tagged):
        pass


'''


import httplib
import os
import re
import urllib


class PortTypes(object):
    UNTAGGED = '1'
    TAGGED = '2'
    NONE = '3'


class Browser(object):
    def __init__(self, conn):
        self.conn = conn
        self.cookie = None
        self.page = None

    def get(self, path):
        return self._request('GET', path, {})

    def post(self, path, params):
        return self._request('POST', path, params)

    def _request(self, method, path, params):
        body = urllib.urlencode(params)
        headers = {}
        if self.cookie is not None:
            headers['Cookie'] = self.cookie

        #print((method, path, body, headers))
        self.conn.request(method, path, body, headers)
        response = self.conn.getresponse()
        self._set_cookie(response)

        self.page = HTML(response.read())
        error = self.page.input_value('err_msg')
        if error and (error != ''):
            raise Exception(error)

        return response

    def _set_cookie(self, response):
        set_cookie = response.getheader('Set-Cookie')
        if set_cookie is not None:
            self.cookie = set_cookie.split(';')[0]


class HTML(object):
    RE_TAGS = re.compile(
            """
            < (\w+) (?: \s+ (.+?) )? /?>
            """,
            re.VERBOSE | re.DOTALL)

    RE_ATTRIBUTES = re.compile(
            """
            (\w+)
            (?: = (?: (?: "(.*?)" ) | (?: '(.*?)' ) | (?: (.*?) ) ) )?
            (?: \s | $)
            """,
            re.VERBOSE | re.DOTALL)


    def __init__(self, html):
        self.html = html

    def __str__(self):
        return self.html

    def input_value(self, name):
        for i in self.inputs():
            if i.get('name') == name:
                return i['value']

    def inputs(self):
        return self._tags_with_name('input')

    def _tags_with_name(self, tag_name):
        return [a for (t, a) in self._tags() if t == tag_name]

    def _tags(self):
        return [
                (
                    name,
                    dict(
                        (key, dq or sq or uq)
                        for (key, dq, sq, uq)
                        in re.findall(HTML.RE_ATTRIBUTES, attrs)
                    )
                )
                for (name, attrs) in re.findall(HTML.RE_TAGS, self.html)
                ]


class Actions(object):
    HOME = '/login.htm'
    LOGIN = '/login.cgi'
    LOGOUT = '/logout.cgi'
    USER = '/user.cgi'
    VLAN_CONFIG = '/8021qCf.cgi'
    VLAN_MEMBERS = '/8021qMembe.cgi'
    PORT_PVID = '/portPVID.cgi'

    def __init__(self, browser):
        self.browser = browser

    def number_of_ports(self):
        try:
            self.browser.get(Actions.LOGIN)
        except Exception:
            pass

        match = re.search('(\d+)-Port', str(self.browser.page))
        if match:
            return int(match.groups()[0])
        else:
            raise Exception("unable to guess number of ports")

    def login(self, password='password'):
        self.browser.post(Actions.LOGIN, {'password': password})
        if 'Invalid Password' in self.browser.page.html:
            raise Exception("Invalid Password!")

    def logout(self):
        self.browser.get(Actions.LOGOUT)

    def change_password(self, old_password, new_password):
        self.browser.get(Actions.USER)
        params = {
                'oldPassword':      old_password,
                'newPassword':      new_password,
                'reNewPassword':    new_password,
                'hash':             self.browser.page.input_value('hash'),
                }
        try:
            self.browser.post(Actions.USER, params)
        except Exception as ex:
            if ex.message == 'Password changed successfully!':
                return
            else:
                raise ex

    def is_vlans_enabled(self):
        self.browser.get(Actions.VLAN_CONFIG)
        for i in self.browser.page.inputs():
            if i.get('name') == 'status' and 'checked' in i:
                return i['value'] == 'Enable'
        raise Exception("couldn't tell if vlans enabled!")

    def enable_vlans(self):
        self.browser.get(Actions.VLAN_CONFIG)
        self.browser.post(
                Actions.VLAN_CONFIG,
                {
                    'status': 'Enable',
                    'hash': self.browser.page.input_value('hash')
                })

    def get_vlans(self):
        self.browser.get(Actions.VLAN_CONFIG)
        vlans = [
                int(i['value'])
                for i in self.browser.page.inputs()
                if i['name'].startswith('vlanck')
                ]
        return sorted(vlans)

    def add_vlan(self, vlan_id):
        self.browser.get(Actions.VLAN_CONFIG)
        params = {
                'status':       'Enable',
                'ADD_VLANID':   str(vlan_id),
                'vlanNum':      self.browser.page.input_value('vlanNum'),
                'hash':         self.browser.page.input_value('hash'),
                'ACTION':       'Add'
                }
        self.browser.post(Actions.VLAN_CONFIG, params)

    def delete_vlan(self, vlan_id):
        self.browser.get(Actions.VLAN_CONFIG)
        vlanck = next(
                i.get('name')
                for i in self.browser.page.inputs()
                if i.get('name', '').startswith('vlanck')
                and i.get('value') == str(vlan_id)
                )
        params = {
                'status':       'Enable',
                'ADD_VLANID':   '',
                vlanck:         vlan_id,
                'vlanNum':      self.browser.page.input_value('vlanNum'),
                'hash':         self.browser.page.input_value('hash'),
                'ACTION':       'Delete',
                }
        # Another v2 (GS108) quirk
        if self.browser.page.input_value('hiddVlan') is not None:
            params['hiddVlan'] = ''
        self.browser.post(Actions.VLAN_CONFIG, params)

    def get_membership(self, vlan_id):
        """
        To get the members of a vlan we first have to submit members for the
        first VLAN while simultaneously asking for the members of the vlan we
        care about...
        """
        self.browser.get(Actions.VLAN_MEMBERS)
        params = {
                'VLAN_ID':      vlan_id,
                'hash':         self.browser.page.input_value('hash'),
                'hiddenMem':    self.browser.page.input_value('hiddenMem'),
                }
        current_vlan_id = self.browser.page.input_value('VLAN_ID_HD')
        # A quirk of firmware v2 (on GS108v3)
        if current_vlan_id:
            params['VLAN_ID_HD'] = current_vlan_id
        self.browser.post(Actions.VLAN_MEMBERS, params)
        membership_string = self.browser.page.input_value('hiddenMem')
        return [c for c in membership_string]

    def set_membership(self, vlan_id, membership):
        self.get_membership(vlan_id)
        params = {
                'VLAN_ID':      vlan_id,
                'hash':         self.browser.page.input_value('hash'),
                'hiddenMem':    ''.join(membership),
                }
        self.browser.post(Actions.VLAN_MEMBERS, params)

    def get_pvid(self, port_index):
        self.browser.get(Actions.PORT_PVID)
        html = self.browser.page.html
        pvids_re = '<td class="def" sel="input">(\d+)'
        pvids = [int(s) for s in re.findall(pvids_re, html)]
        return pvids[port_index]

    def set_pvid(self, port_index, pvid):
        self.browser.get(Actions.PORT_PVID)
        #body = self.agent.get(PORT_PVID).read()
        #hash = self.get_input(body, 'hash')

        # Quirk fix:
        # On GS105 these are numbered (port0, port1, ...)
        # On GS108 these are numbered (port1, port2, ...)
        port_key_index = port_index
        if 'port0' not in [i.get('name') for i in self.browser.page.inputs()]:
            port_key_index = port_key_index + 1

        port_key = 'port{}'.format(port_key_index)
        params = {
                'pvid':     str(pvid),
                port_key:   'checked',
                'hash':     self.browser.page.input_value('hash'),
                }
        self.browser.post(Actions.PORT_PVID, params)


def check(message):
    print(" CHECK  {}".format(message))


def change(message):
    print(" CHANGE {}".format(message))


#
# CLI
#
# Either literally state the port PVIDs and VLAN memberships, in a way that
# mirrors the web UI:
#
#   netgear-switch-vlans                    \
#           --hostname 10.3.1.50            \
#           --password password44           \
#           --password-old password         \
#           --pvids      1  11  13  15  97  \
#           --vlan   1   T   _   _   _   T  \
#           --vlan  11   T   U   _   _   T  \
#           --vlan  13   T   _   U   _   T  \
#           --vlan  15   T   _   _   U   T
#
# Or list trunk ports and static-host ports, and have everything derived
# automatically:
#
#   netgear-switch-vlans                \
#           --hostname 10.3.1.50        \
#           --password password44       \
#           --password-old password     \
#           --trunk-port 1              \
#           --host-port  2 11           \
#           --host-port  3 13           \
#           --host-port  4 15           \
#           --trunk-port 5
#

import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--hostname', type=str)
parser.add_argument('--password', type=str)
parser.add_argument('--old-password', type=str, default='password')

parser.add_argument(
        '--trunk-port',
        type=int,
        nargs='+',
        action='append',
        default=[])

parser.add_argument(
        '--host-port',
        type=int,
        nargs='+',
        action='append',
        default=[])

args = parser.parse_args()

hostname = args.hostname
password_new = args.password
password_old = args.old_password

# Create a connection
check('connection')
conn = httplib.HTTPConnection(hostname, 80)
browser = Browser(conn)
actions = Actions(browser)

# Get number of ports
num_ports = actions.number_of_ports()

# Parse args
trunk_ports = dict((l[0], l[1:]) for l in args.trunk_port)
host_ports = dict(args.host_port)

# All mentioned VLAN IDs
vlan_ids = host_ports.values()
vlan_ids.extend((n for ns in trunk_ports.values() for n in ns))
vlan_ids = sorted(set(vlan_ids))
print(vlan_ids)

###
# Baseline Config
pvids = [1 for _ in range(0, num_ports)]
all_ports_none = [PortTypes.NONE for _ in range(0, num_ports)]
memberships = dict((id, all_ports_none[:]) for id in vlan_ids)
# Default port state is UNTAGGED on VLAN 1
memberships[1] = [PortTypes.UNTAGGED for _ in range(0, num_ports)]

for port, ids in trunk_ports.iteritems():
    index = port - 1
    pvids[index] = 1
    for id in ids:
        memberships[id][index] = (
                PortTypes.UNTAGGED if id ==1 else PortTypes.TAGGED)

for port, id in host_ports.iteritems():
    index = port - 1
    pvids[index] = id
    memberships[id][index] = PortTypes.UNTAGGED

# Print settings
print(" TODO   pvids {!r}".format(pvids))
for id in sorted(memberships.keys()):
    membership = memberships[id]
    print(" TODO   vlan {:4d} = {!r}".format(id, membership))

# Sync all settings
try:
    check("old password")
    old_password_valid = False
    try:
        actions.login(password_old)
        old_password_valid = True
    except Exception:
        pass

    if old_password_valid:
        actions.change_password(password_old, password_new)
        change('password')

    check('new password')
    actions.login(password_new)

    check("802.1Q Advanced VLANS enabled")
    if not actions.is_vlans_enabled():
        change('enable')
        actions.enable_vlans()

    current_vlans = actions.get_vlans()

    # Add all VLANs
    for vlan_id in memberships.keys():
        check("presence of VLAN {}".format(vlan_id))
        if vlan_id not in current_vlans:
            change("VLAN {}".format(vlan_id))
            actions.add_vlan(vlan_id)

    for port_index, pvid_vlan in enumerate(pvids):
        port_number = port_index + 1

        # Ensure port is some kind of member of its PVID VLAN
        check("port #{} is member of VLAN {}".format(
            port_number, pvid_vlan))
        membership = actions.get_membership(pvid_vlan)
        if membership[port_index] == PortTypes.NONE:
            membership[port_index] = PortTypes.UNTAGGED
            change("port #{} to be untagged member of VLAN {}".format(
                port_number, pvid_vlan))
            actions.set_membership(pvid_vlan, membership)

        # Set PVID
        check("PVID for port #{} is {}".format(port_number, pvid_vlan))
        if actions.get_pvid(port_index) != pvid_vlan:
            change("PVID for port #{} to {}".format(port_number, pvid_vlan))
            actions.set_pvid(port_index, pvid_vlan)

    # Set membership
    for vlan_id, membership in memberships.iteritems():
        check("membership of VLAN {}".format(vlan_id))
        current_membership = actions.get_membership(vlan_id)
        if current_membership != membership:
            change("membership of VLAN {} from {!r} to {!r}".format(
                vlan_id, current_membership, membership))
            actions.set_membership(vlan_id, membership)

    # Delete unwanted config from switch:
    for vlan_id in current_vlans:
        if vlan_id in memberships:
            continue

        change("delete membership for VLAN {}".format(vlan_id))
        null_membership = [PortTypes.NONE for _ in pvids]
        actions.set_membership(vlan_id, null_membership)

        change("delete VLAN {}".format(vlan_id))
        actions.delete_vlan(vlan_id)


finally:
    actions.logout()

'''
