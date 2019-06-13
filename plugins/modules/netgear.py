################################################################################
#
# Netgear API Code
#
import httplib
import os
import re
import urllib


DEFAULT_PASSWORD = 'password'

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
                i['value']
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
        pvids = [s for s in re.findall(pvids_re, html)]
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


def sync(address, password_old, password_new, vlans, pvids):
    conn = httplib.HTTPConnection(address, 80)
    browser = Browser(conn)
    actions = Actions(browser)

    log = []

    try:
        if actions.login(password_old):
            actions.change_password(password_old, password_new)
            log.append("Changed password")

        actions.login(password_new)

        if not actions.is_vlans_enabled():
            actions.enable_vlans()
            log.append("Enabled Advanced 802.1Q VLAN mode")

        current_vlans = actions.get_vlans()

        # Add all VLANs
        for vlan_id in vlans.keys():
            if vlan_id not in current_vlans:
                actions.add_vlan(vlan_id)
                log.append("Added new VLAN {}".format(vlan_id))

        for port_index, pvid_vlan in enumerate(pvids):
            port_number = port_index + 1

            # Ensure port is some kind of member of its PVID VLAN
            membership = actions.get_membership(pvid_vlan)
            if membership[port_index] == PortTypes.NONE:
                membership[port_index] = PortTypes.UNTAGGED
                actions.set_membership(pvid_vlan, membership)

            # Set PVID
            if actions.get_pvid(port_index) != pvid_vlan:
                actions.set_pvid(port_index, pvid_vlan)
                log.append("Set PVID for port {} to {}".format(
                    port_number, pvid_vlan))

        # Set membership
        for vlan_id, membership in vlans.iteritems():
            current_membership = actions.get_membership(vlan_id)
            log.append('{}: {!r} ==? {!r}'.format(
                vlan_id, current_membership, membership))
            if current_membership != membership:
                actions.set_membership(vlan_id, membership)
                log.append("Changed VLAN {} membership to {!r}".format(
                    vlan_id, membership))

        # Delete unwanted config from switch:
        for vlan_id in current_vlans:
            if vlan_id in vlans:
                continue
            null_membership = [PortTypes.NONE for _ in pvids]
            actions.set_membership(vlan_id, null_membership)
            actions.delete_vlan(vlan_id)
            log.append("Deleted VLAN {}".format(vlan_id))


    finally:
        actions.logout()
        return log


################################################################################
#
# Ansible Module
#
ANSIBILE_METADATA = {
    'metadata_version': '1.1',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
'''

EXAMPLES = '''
'''

from ansible.module_utils.basic import AnsibleModule

def run_module():
    # define available arguments/parameters a user can pass to the module
    module_args = dict(
        address=dict(type='str', required=True),
        password=dict(type='str', required=True, no_log=True),
        password_old=dict(type='str', required=False, no_log=True),
        pvids=dict(type='list', required=True),
        vlans=dict(type='dict', required=True),
    )

    # seed the result dict in the object
    # we primarily care about changed and state
    # change is if this module effectively modified the target
    # state will include any data that you want your module to pass back
    # for consumption, for example, in a subsequent task
    result = dict(
        changed=False,
    )

    # the AnsibleModule object will be our abstraction working with Ansible
    # this includes instantiation, a couple of common attr would be the
    # args/params passed to the execution, as well as if the module
    # supports check mode
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=False
    )

    address = module.params['address']
    password_new = module.params['password']
    password_old = module.params.get('password_old', DEFAULT_PASSWORD)
    pvids = module.params['pvids']

    vlans = {}
    for vlan_id, membership in module.params['vlans'].iteritems():
        vlans[vlan_id] = [
                (PortTypes.TAGGED if m == 'T' else
                    PortTypes.UNTAGGED if m == 'U' else
                    PortTypes.NONE)
                for m in membership
                ]

    log = sync(address, password_old, password_new, vlans, pvids)

    if log:
        result['changed'] = True
        result['log'] = log

    # during the execution of the module, if there is an exception or a
    # conditional state that effectively causes a failure, run
    # AnsibleModule.fail_json() to pass in the message and the result
    #if module.params['name'] == 'fail me':
    #    module.fail_json(msg='You requested this to fail', **result)

    # in the event of a successful module execution, you will want to
    # simple AnsibleModule.exit_json(), passing the key/value results
    module.exit_json(**result)

def main():
    run_module()

if __name__ == '__main__':
    main()
