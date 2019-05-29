# Copyright (c) 2019. All rights reserved.

import atexit
from io import StringIO
import json
import unittest
import yaml

from tornado.ioloop import IOLoop
import tornado.testing

from addrservice.addressbook_db import create_addressbook_db
from addrservice.service import AddressBookService
from addrservice.app import (
    make_addrservice_app,
    ADDRESSBOOK_ENTRY_URI_FORMAT_STR
)

from tests.unit.address_data_test import address_data_suite


IN_MEMORY_CFG_TXT = '''
service:
  name: Address Book Test

addr-db:
  memory: null
'''

with StringIO(IN_MEMORY_CFG_TXT) as f:
    TEST_CONFIG = yaml.load(f.read(), Loader=yaml.SafeLoader)


class TestAddressServiceApp(tornado.testing.AsyncHTTPTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.headers = {'Content-Type': 'application/json; charset=UTF-8'}
        address_data = address_data_suite()
        keys = list(address_data.keys())
        self.assertGreaterEqual(len(keys), 2)
        self.addr0 = address_data[keys[0]]
        self.addr1 = address_data[keys[1]]

    def get_app(self) -> tornado.web.Application:
        # get_app is the hook that Tornado Test uses to get app under test
        addr_db = create_addressbook_db(TEST_CONFIG['addr-db'])
        addr_service = AddressBookService(addr_db)

        addr_service.start()
        atexit.register(lambda: addr_service.stop())

        return make_addrservice_app(
            service=addr_service,
            config=TEST_CONFIG,
            debug=True
        )

    def get_new_ioloop(self):
        IOLoop.configure('tornado.platform.asyncio.AsyncIOLoop')
        instance = IOLoop.instance()
        return instance

    def test_liveness(self):
        r = self.fetch(
            '/healthz',
            method='GET',
            headers=None,
        )
        info = json.loads(r.body.decode('utf-8'))

        self.assertEqual(r.code, 200, info)
        self.assertGreater(info['uptime'], 0)

    def test_readiness(self):
        r = self.fetch(
            '/readiness',
            method='GET',
            headers=None,
        )
        info = json.loads(r.body.decode('utf-8'))

        self.assertEqual(r.code, 200, info)
        self.assertTrue(info['ready'])
        self.assertGreater(info['uptime'], 0)

    def test_default_handler(self):
        r = self.fetch(
            '/does-not-exist',
            method='GET',
            headers=None,
        )
        info = json.loads(r.body.decode('utf-8'))

        self.assertEqual(r.code, 404, info)
        self.assertEqual(info['code'], 404)
        self.assertEqual(info['message'], 'Unknown Endpoint')

    def test_address_book_endpoints(self):
        # Get all addresses in the address book, must be ZERO
        r = self.fetch(
            ADDRESSBOOK_ENTRY_URI_FORMAT_STR.format(id=''),
            method='GET',
            headers=None,
        )
        all_addrs = json.loads(r.body.decode('utf-8'))
        self.assertEqual(r.code, 200, all_addrs)
        self.assertEqual(len(all_addrs), 0, all_addrs)

        # Add an address
        r = self.fetch(
            ADDRESSBOOK_ENTRY_URI_FORMAT_STR.format(id=''),
            method='POST',
            headers=self.headers,
            body=json.dumps(self.addr0),
        )
        self.assertEqual(r.code, 201)
        addr_uri = r.headers['Location']

        # POST: error cases
        r = self.fetch(
            ADDRESSBOOK_ENTRY_URI_FORMAT_STR.format(id=''),
            method='POST',
            headers=self.headers,
            body='it is not json',
        )
        self.assertEqual(r.code, 400)
        self.assertEqual(r.reason, 'Invalid JSON body')
        r = self.fetch(
            ADDRESSBOOK_ENTRY_URI_FORMAT_STR.format(id=''),
            method='POST',
            headers=self.headers,
            body=json.dumps({}),
        )
        self.assertEqual(r.code, 400)
        self.assertEqual(r.reason, 'JSON Schema validation failed')

        # Get the added address
        r = self.fetch(
            addr_uri,
            method='GET',
            headers=None,
        )
        self.assertEqual(r.code, 200)
        self.assertEqual(self.addr0, json.loads(r.body.decode('utf-8')))

        # GET: error cases
        r = self.fetch(
            ADDRESSBOOK_ENTRY_URI_FORMAT_STR.format(id='no-such-id'),
            method='GET',
            headers=None,
        )
        self.assertEqual(r.code, 404)

        # Update that address
        r = self.fetch(
            addr_uri,
            method='PUT',
            headers=self.headers,
            body=json.dumps(self.addr1),
        )
        self.assertEqual(r.code, 204)
        r = self.fetch(
            addr_uri,
            method='GET',
            headers=None,
        )
        self.assertEqual(r.code, 200)
        self.assertEqual(self.addr1, json.loads(r.body.decode('utf-8')))

        # PUT: error cases
        r = self.fetch(
            addr_uri,
            method='PUT',
            headers=self.headers,
            body='it is not json',
        )
        self.assertEqual(r.code, 400)
        self.assertEqual(r.reason, 'Invalid JSON body')
        r = self.fetch(
            ADDRESSBOOK_ENTRY_URI_FORMAT_STR.format(id='1234'),
            method='PUT',
            headers=self.headers,
            body=json.dumps(self.addr1),
        )
        self.assertEqual(r.code, 404)
        r = self.fetch(
            addr_uri,
            method='PUT',
            headers=self.headers,
            body=json.dumps({}),
        )
        self.assertEqual(r.code, 400)
        self.assertEqual(r.reason, 'JSON Schema validation failed')

        # Delete that address
        r = self.fetch(
            addr_uri,
            method='DELETE',
            headers=None,
        )
        self.assertEqual(r.code, 204)
        r = self.fetch(
            addr_uri,
            method='GET',
            headers=None,
        )
        self.assertEqual(r.code, 404)

        # DELETE: error cases
        r = self.fetch(
            addr_uri,
            method='DELETE',
            headers=None,
        )
        self.assertEqual(r.code, 404)

        # Get all addresses in the address book, must be ZERO
        r = self.fetch(
            ADDRESSBOOK_ENTRY_URI_FORMAT_STR.format(id=''),
            method='GET',
            headers=None,
        )
        all_addrs = json.loads(r.body.decode('utf-8'))
        self.assertEqual(r.code, 200, all_addrs)
        self.assertEqual(len(all_addrs), 0, all_addrs)


if __name__ == '__main__':
    unittest.main()
