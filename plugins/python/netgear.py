import httplib
import os
import re
import urllib


class PortTypes(object):
    TAGGED = 'T'
    UNTAGGED = 'U'


class Config(object):
    def __init__(self, dict):
        self.dict = dict
        self.password_old = dict.get('password_old')
        self.password = dict.get('password')

    def ports(self):
        for index, pc in enumerate(self.dict['vlan_ports']):
            pvid = pc['pvid']
            tagged = pc.get('tagged', [])
            if not isinstance(tagged, list):
                tagged = [tagged]
            untagged = pc.get('untagged', [])
            if not isinstance(untagged, list):
                untagged = [untagged]
            yield (index, pvid, tagged, untagged)

    def vlan_ids(self):
        all = [
                [[pvid], tagged, untagged]
                for (_, pvid, tagged, untagged) in self.ports()
                ]
        flat = [i for list1 in all for list2 in list1 for i in list2]
        return sorted(set(flat))

    def memberships(self):
        for vlan_id in self.vlan_ids():
            membership = [
                    (
                        PortTypes.TAGGED    if vlan_id in tagged else
                        PortTypes.UNTAGGED  if vlan_id in untagged else
                        None
                    )
                    for (_, pvid, tagged, untagged) in self.ports()
                    ]
            yield (vlan_id, membership)


class Agent(object):
    def __init__(self, conn):
        self.conn = conn
        self.cookie = None

    def request(self, method, path, params={}):
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


class Browser(object):
    def __init__(self, agent):
        self.agent = agent
        self.page = None

    def request(self, path, params={}):
        method = 'GET'
        if params:
            method = 'POST'
        #print((method, path, params))
        response = self.agent.request(method, path, params)
        self.page = HTML(response.read())
        error = self.page.input_value('err_msg')
        if error and (error != ''):
            raise Exception(error)


class MembershipCodec(object):
    PORT_TYPES = {
            '1': PortTypes.UNTAGGED,
            '2': PortTypes.TAGGED,
            '3': None,
            }

    PORT_CODES = dict((v, k) for k, v in PORT_TYPES.iteritems())

    @classmethod
    def decode(cls, enc):
        return [cls.PORT_TYPES[c] for c in enc]

    @classmethod
    def encode(cls, membership):
        return ''.join(cls.PORT_CODES[t] for t in membership)


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
        self.browser.request(Actions.LOGIN, {'password': password})
        return 'Invalid Password' not in self.browser.page.html

    def logout(self):
        self.browser.request(Actions.LOGOUT)

    def change_password(self, old_password, new_password):
        self.browser.request(Actions.USER)
        params = {
                'oldPassword':      old_password,
                'newPassword':      new_password,
                'reNewPassword':    new_password,
                'hash':             self.browser.page.input_value('hash'),
                }
        try:
            self.browser.request(Actions.USER, params)
        except Exception as ex:
            if ex.message == 'Password changed successfully!':
                return
            else:
                raise ex

    def is_vlans_enabled(self):
        self.browser.request(Actions.VLAN_CONFIG)
        for i in self.browser.page.inputs():
            if i.get('name') == 'status' and 'checked' in i:
                return i['value'] == 'Enable'
        raise Exception("couldn't tell if vlans enabled!")

    def enable_vlans(self):
        self.browser.request(Actions.VLAN_CONFIG)
        self.browser.request(
                Actions.VLAN_CONFIG,
                {
                    'status': 'Enable',
                    'hash': self.browser.page.input_value('hash')
                })

    def get_vlans(self):
        self.browser.request(Actions.VLAN_CONFIG)
        vlans = [
                int(i['value'])
                for i in self.browser.page.inputs()
                if i['name'].startswith('vlanck')
                ]
        return sorted(vlans)

    def add_vlan(self, vlan_id):
        self.browser.request(Actions.VLAN_CONFIG)
        params = {
                'status':       'Enable',
                'ADD_VLANID':   str(vlan_id),
                'vlanNum':      self.browser.page.input_value('vlanNum'),
                'hash':         self.browser.page.input_value('hash'),
                'ACTION':       'Add'
                }
        self.browser.request(Actions.VLAN_CONFIG, params)

    def delete_vlan(self, vlan_id):
        self.browser.request(Actions.VLAN_CONFIG)
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
        self.browser.request(Actions.VLAN_CONFIG, params)

    def get_membership(self, vlan_id):
        """
        To get the members of a vlan we first have to submit members for the
        first VLAN while simultaneously asking for the members of the vlan we
        care about...
        """
        self.browser.request(Actions.VLAN_MEMBERS)
        params = {
                'VLAN_ID':      vlan_id,
                'hash':         self.browser.page.input_value('hash'),
                'hiddenMem':    self.browser.page.input_value('hiddenMem'),
                }
        self.browser.request(Actions.VLAN_MEMBERS, params)
        return MembershipCodec.decode(
                self.browser.page.input_value('hiddenMem'))

    def set_membership(self, vlan_id, membership):
        self.get_membership(vlan_id)
        params = {
                'VLAN_ID':      vlan_id,
                'hash':         self.browser.page.input_value('hash'),
                'hiddenMem':    MembershipCodec.encode(membership),
                }
        self.browser.request(Actions.VLAN_MEMBERS, params)

    def get_pvid(self, port_index):
        self.browser.request(Actions.PORT_PVID)
        html = self.browser.page.html
        pvids_re = '<td class="def" sel="input">(\d+)'
        pvids = [int(s) for s in re.findall(pvids_re, html)]
        return pvids[port_index]

    def set_pvid(self, port_index, pvid):
        self.browser.request(Actions.PORT_PVID)
        #body = self.agent.get(PORT_PVID).read()
        #hash = self.get_input(body, 'hash')
        port_key = 'port{}'.format(port_index)
        params = {
                'pvid':     str(pvid),
                port_key:   'checked',
                'hash':     self.browser.page.input_value('hash'),
                }
        self.browser.request(Actions.PORT_PVID, params)


def sync(fqdn, config):
    conn = httplib.HTTPConnection(fqdn, 80)
    agent = Agent(conn)
    browser = Browser(agent)
    actions = Actions(browser)

    try:
        did_change = False

        if actions.login(config.password_old):
            did_change = True
            print("Changing password")
            actions.change_password(config.password_old, config.password)

        actions.login(config.password)

        if not actions.is_vlans_enabled():
            did_change = True
            print "Enabling VLANs"
            actions.enable_vlans()

        current_vlans = actions.get_vlans()

        # Add all VLANs
        for vlan_id in config.vlan_ids():
            if vlan_id not in current_vlans:
                print "Adding new VLAN {}".format(vlan_id)
                actions.add_vlan(vlan_id)
                did_change = True

        for (index, pvid_vlan, _, _) in config.ports():
            # Ensure port is untagged member of its PVID VLAN
            membership = actions.get_membership(pvid_vlan)
            if membership[index] != PortTypes.UNTAGGED:
                print(
                        "Changing port #{} to be untagged member of VLAN {}".format(
                            index + 1, pvid_vlan))
                membership[index] = PortTypes.UNTAGGED
                actions.set_membership(pvid_vlan, membership)
                did_change = True

            # Set PVID
            if actions.get_pvid(index) != pvid_vlan:
                print(
                        "Setting PVID for port #{} to {}".format(
                            index + 1, pvid_vlan))
                actions.set_pvid(index, pvid_vlan)
                did_change = True

        # Set membership
        for vlan_id, membership in config.memberships():
            if actions.get_membership(vlan_id) != membership:
                print(
                        "Changing VLAN {:4d} membership: {!r}".format(
                            vlan_id,
                            membership))
                actions.set_membership(vlan_id, membership)
                did_change = True

        # Delete unwanted config from switch:
        for vlan_id in current_vlans:
            if vlan_id in config.vlan_ids():
                continue
            did_change = True

            print("Delete membership for VLAN {}".format(vlan_id))
            null_membership = [None for _ in config.ports()]
            actions.set_membership(vlan_id, null_membership)

            print("Delete VLAN {}".format(vlan_id))
            actions.delete_vlan(vlan_id)


    finally:
        actions.logout()



import yaml
config = Config(yaml.load(
        """
        password_old: password
        password: password44
        vlan_ports:
            - pvid: 1
              untagged: [1]
            - pvid: 1
              untagged: [1]
            - pvid: 99
              untagged: [99]
            - pvid: 99
              untagged: [99]
            - pvid: 99
              untagged: [99]
        """))

sync('10.3.1.50', config)
