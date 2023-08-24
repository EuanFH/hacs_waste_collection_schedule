from dateutil import parser

import requests
import re
import json
import base64
from urllib.parse import urlparse
from urllib.parse import parse_qs
from bs4 import BeautifulSoup
from waste_collection_schedule import Collection # type: ignore[attr-defined]

TITLE = 'East Renfrewshire Council'
DESCRIPTION = 'Source for eastrenfrewshire.gov.uk services for East Renfrewshire'
URL = 'https://www.eastrenfrewshire.gov.uk/bin-days'

TEST_CASES = {
    "Test_001": {"postcode": "XXXX", "uprn": "XXXXXX"},
}

ICON_MAP = {
    "Grey": "mdi:trash-can",
    "Brown": "mdi:leaf",
    "Green": "mdi:glass-fragile",
    "Blue": "mdi:note",
}


class Source:
    def __init__(self, postcode, uprn):
        self._postcode = postcode
        self._uprn = str(uprn).zfill(12)


    def fetch(self):
        session = requests.Session()
        address_page = self.get_address_page(session, self._postcode)
        bin_collection_info_page = self.get_bin_collection_info_page(session, address_page, self._uprn)
        bin_collection_info = self.get_bin_collection_info(bin_collection_info_page)
        return self.generate_collection_entries(bin_collection_info) 
    
    def generate_collection_entries(self, bin_collection_info):
        collection_results = bin_collection_info['residualWasteResponse']['value']['collectionResults']
        entries = []
        for collection in collection_results['binsOrderingArray']:
            for collection_date in collection['collectionDates']:
                entries.append(
                    Collection(
                        date = parser.parse(collection_date).date(), 
                        t = collection['color'],
                        icon = ICON_MAP.get(collection['color']),
                    )
                )
        return entries

    def get_bin_collection_info(self, bin_collection_info_page):
        serializedCollectionInfoPattern = re.compile(r'var RESIDUALWASTEV2SerializedVariables = "(.*?)";$', re.MULTILINE | re.DOTALL)
        soup = BeautifulSoup(bin_collection_info_page, 'html.parser')
        script = soup.find('script', text=serializedCollectionInfoPattern)
        if not script:
            return {}
        match = serializedCollectionInfoPattern.search(script.text)
        if not match:
            return {}
        serializedCollectionInfo = match.group(1)
        collectionInfo = json.loads(base64.b64decode(serializedCollectionInfo))
        return collectionInfo

    def get_bin_collection_info_page(self, session, address_page, uprn):
        soup = BeautifulSoup(address_page, 'html.parser')
        form = soup.find(id='RESIDUALWASTEV2_FORM')
        goss_ids = self.get_goss_form_ids(form['action'])
        r = session.post(form['action'], data={
            'RESIDUALWASTEV2_PAGESESSIONID': goss_ids['page_session_id'],
            'RESIDUALWASTEV2_SESSIONID': goss_ids['session_id'],
            'RESIDUALWASTEV2_NONCE': goss_ids['nonce'],
            'RESIDUALWASTEV2_VARIABLES': 'e30=',
            'RESIDUALWASTEV2_PAGENAME': 'PAGE2',
            'RESIDUALWASTEV2_PAGEINSTANCE': '1',
            'RESIDUALWASTEV2_PAGE2_FIELD201': 'true',
            'RESIDUALWASTEV2_PAGE2_UPRN': '',
            'RESIDUALWASTEV2_PAGE2_UPRN': uprn,
            'RESIDUALWASTEV2_FORMACTION_NEXT': 'RESIDUALWASTEV2_PAGE2_FIELD206',
            'RESIDUALWASTEV2_PAGE2_FIELD202': 'false',
            'RESIDUALWASTEV2_PAGE2_FIELD203': 'false',
        })
        r.raise_for_status()
        return r.text

    def get_address_page(self, s, postcode):
        r = s.get('https://www.eastrenfrewshire.gov.uk/bin-days')
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        form = soup.find(id='RESIDUALWASTEV2_FORM')
        goss_ids = self.get_goss_form_ids(form['action'])
        r = s.post(form['action'], data={
            'RESIDUALWASTEV2_PAGESESSIONID': goss_ids['page_session_id'],
            'RESIDUALWASTEV2_SESSIONID': goss_ids['session_id'],
            'RESIDUALWASTEV2_NONCE': goss_ids['nonce'],
            'RESIDUALWASTEV2_VARIABLES': 'e30=',
            'RESIDUALWASTEV2_PAGENAME': 'PAGE1',
            'RESIDUALWASTEV2_PAGEINSTANCE': '0',
            'RESIDUALWASTEV2_PAGE1_POSTCODE': postcode,
            'RESIDUALWASTEV2_FORMACTION_NEXT': 'RESIDUALWASTEV2_PAGE1_FIELD199',
        })
        r.raise_for_status()
        return r.text

    def get_goss_form_ids(self, url):
        parsed_form_url = urlparse(url)
        form_url_values = parse_qs(parsed_form_url.query)
        return {
            'page_session_id': form_url_values['pageSessionId'][0],
            'session_id': form_url_values['fsid'][0],
            'nonce': form_url_values['fsn'][0]
        }