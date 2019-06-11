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
    LOGIN = '/login.cgi'
    LOGOUT = '/logout.cgi'
    USER = '/user.cgi'
    VLAN_CONFIG = '/8021qCf.cgi'
    VLAN_MEMBERS = '/8021qMembe.cgi'
    PORT_PVID = '/portPVID.cgi'

    def __init__(self, browser):
        self.browser = browser

    def login(self, password='password'):
        self.browser.post(Actions.LOGIN, {'password': password})
        return 'Invalid Password' not in self.browser.page.html

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
        port_key = 'port{}'.format(port_index)
        params = {
                'pvid':     str(pvid),
                port_key:   'checked',
                'hash':     self.browser.page.input_value('hash'),
                }
        self.browser.post(Actions.PORT_PVID, params)


def sync(fqdn, password_old, password_new, vlans, pvids):
    conn = httplib.HTTPConnection(fqdn, 80)
    browser = Browser(conn)
    actions = Actions(browser)

    try:
        did_change = False

        if actions.login(password_old):
            did_change = True
            print("Changing password")
            actions.change_password(password_old, password_new)

        actions.login(password_new)

        if not actions.is_vlans_enabled():
            did_change = True
            print "Enabling VLANs"
            actions.enable_vlans()

        current_vlans = actions.get_vlans()

        # Add all VLANs
        for vlan_id in vlans.keys():
            if vlan_id not in current_vlans:
                print "Adding new VLAN {}".format(vlan_id)
                actions.add_vlan(vlan_id)
                did_change = True

        for port_index, pvid_vlan in enumerate(pvids):
            port_number = port_index + 1

            # Ensure port is some kind of member of its PVID VLAN
            membership = actions.get_membership(pvid_vlan)
            if membership[port_index] == PortTypes.NONE:
                print(
                        "Temporarily changing port #{} to be untagged member of VLAN {}".format(
                            port_number, pvid_vlan))
                membership[port_index] = PortTypes.UNTAGGED
                actions.set_membership(pvid_vlan, membership)
                did_change = True

            # Set PVID
            if actions.get_pvid(port_index) != pvid_vlan:
                print(
                        "Setting PVID for port #{} to {}".format(
                            port_number, pvid_vlan))
                actions.set_pvid(port_index, pvid_vlan)
                did_change = True

        # Set membership
        for vlan_id, membership in vlans.iteritems():
            if actions.get_membership(vlan_id) != membership:
                print(
                        "Changing VLAN {:4d} membership: {!r}".format(
                            vlan_id,
                            membership))
                actions.set_membership(vlan_id, membership)
                did_change = True

        # Delete unwanted config from switch:
        for vlan_id in current_vlans:
            if vlan_id in vlans:
                continue
            did_change = True

            print("Delete membership for VLAN {}".format(vlan_id))
            null_membership = [PortTypes.NONE for _ in pvids]
            actions.set_membership(vlan_id, null_membership)

            print("Delete VLAN {}".format(vlan_id))
            actions.delete_vlan(vlan_id)


    finally:
        actions.logout()



U = PortTypes.UNTAGGED
T = PortTypes.TAGGED
N = PortTypes.NONE

password_old = 'password'
password_new = 'password44'

vlans = {
        1:  [U, N, U, N, N],
        32: [T, U, N, N, N],
        97: [N, N, T, T, U],
        }

pvids = [1, 32, 1, 97, 97]

sync('10.3.1.50', password_old, password_new, vlans, pvids)
