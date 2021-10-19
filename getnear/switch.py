from getnear.eseries import ESeries
from getnear.tseries import TSeries
import lxml.etree
import re
import requests


def connect(hostname, *args, **kwargs):
    url = f'http://{hostname}/login.cgi'
    html = requests.get(url).text
    doc = lxml.etree.HTML(html)

    for info in doc.xpath('//div[@class = "switchInfo"]'):
        if re.match('GS\d+E', info.text):
            return ESeries(hostname, *args, **kwargs)

    url = f'http://{hostname}/'
    html = requests.get(url).text
    doc = lxml.etree.HTML(html)

    for title in doc.xpath('//title'):
        if re.match('NETGEAR GS\d+T', title.text):
            return TSeries(hostname, *args, **kwargs)

    raise Exception(f'unknown switch type for {hostname}:\n{html[:2000]}')
