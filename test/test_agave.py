import tempfile
import vcr
import unittest
from os import path
from bdbag.fetch.transports.fetch_agave import *


class TestAgave(unittest.TestCase):
    @vcr.use_cassette('test_agave/get_tenants.yaml')
    def test_get_tenants(self):
        tenants = get_tenants()
        expected_tenants = {'https://api.3dem.org/': '3dem',
                            'https://public.agaveapi.co/': 'agave.prod',
                            'https://api.araport.org/': 'araport.org',
                            'https://api.bridge.tacc.cloud/': 'bridge',
                            'https://agave.designsafe-ci.org/': 'designsafe',
                            'https://agave.iplantc.org/': 'iplantc.org',
                            'https://irec.tenants.prod.tacc.cloud/': 'irec',
                            'https://portals-api.tacc.utexas.edu/': 'portals',
                            'https://api.sd2e.org/': 'sd2e',
                            'https://sgci.tacc.cloud/': 'sgci',
                            'https://api.tacc.utexas.edu/': 'tacc.prod',
                            'https://vdj-agave-api.tacc.utexas.edu/': 'vdjserver.org'}
        self.assertEqual(tenants, expected_tenants)

    def test_detect_agave(self):
        boolean, tenant = detect_agave('https://agave.designsafe-ci.org/path/to/endpoint')
        self.assertEqual(boolean, True)
        self.assertEqual(tenant, 'designsafe')

        boolean, tenant = detect_agave('https://example.com/path/to/endpoint')
        self.assertEqual(boolean, False)
        self.assertEqual(tenant, None)

    def test_get_agave_config(self):
        config_dict = {
            'sessions': {
                'designsafe': {
                    'USERNAME': {
                        'test_client': {
                            'refresh_token': 'VALID_REFRESH_TOKEN',
                            'expires_in': 3600,
                            'expires_at': 'Mon Nov  4 15:24:54 2019',
                            'created_at': 1572877494,
                            'username': 'USERNAME',
                            'token_username': None,
                            'client_name': 'test_client',
                            'use_nonce': False,
                            'verify': True,
                            'proxies': {},
                            'tenantid': 'designsafe',
                            'apisecret': 'VALID_API_SECRET',
                            'apikey': 'VALID_API_KEY',
                            'baseurl': 'https://agave.designsafe-ci.org/',
                            'access_token': 'VALID_ACCESS_TOKEN'
                        }
                    }
                }
            }
        }
        temp_dir = tempfile.mkdtemp()
        config_path = path.join(temp_dir, 'config.json')

        with open(config_path, 'w') as f:
            f.write(json.dumps(config_dict))

        result = get_agave_config(config_path)

        self.assertEqual(result, config_dict)

    @vcr.use_cassette('test_agave/is_token_expired_true.yaml')
    def test_is_token_expired_true(self):
        result = is_token_expired('EXPIRED_ACCESS_TOKEN', 'https://agave.designsafe-ci.org/')
        self.assertEqual(result, True)

    @vcr.use_cassette('test_agave/is_token_expired_false.yaml')
    def test_is_token_expired_false(self):
        result = is_token_expired('VALID_ACCESS_TOKEN', 'https://agave.designsafe-ci.org/')
        self.assertEqual(result, False)

    @vcr.use_cassette('test_agave/refresh_token_bad.yaml')
    def test_refresh_token_bad(self):
        auth = {
            'refresh_token': 'BAD_REFRESH_TOKEN',
            'apikey': 'API_KEY',
            'apisecret': 'API_SECRET',
            'baseurl': 'https://agave.designsafe-ci.org/'
        }
        self.assertEqual(refresh_token(auth), False)

    @vcr.use_cassette('test_agave/refresh_token_good.yaml')
    def test_refresh_token_good(self):
        auth = {
            'refresh_token': 'GOOD_REFRESH_TOKEN',
            'apikey': 'API_KEY',
            'apisecret': 'API_SECRET',
            'baseurl': 'https://agave.designsafe-ci.org/'
        }
        expected_auth = {
            'refresh_token': 'NEW_REFRESH_TOKEN',
            'apikey': 'API_KEY',
            'apisecret': 'API_SECRET',
            'baseurl': 'https://agave.designsafe-ci.org/',
            'access_token': 'NEW_ACCESS_TOKEN',
            'expires_in': 14400
        }
        self.assertEqual(refresh_token(auth), True)
        self.assertEqual(auth['apikey'], expected_auth['apikey'])
        self.assertEqual(auth['apisecret'], expected_auth['apisecret'])
        self.assertEqual(auth['baseurl'], expected_auth['baseurl'])
        self.assertEqual(auth['refresh_token'], expected_auth['refresh_token'])
        self.assertEqual(auth['access_token'], expected_auth['access_token'])
        self.assertEqual(auth['expires_in'], expected_auth['expires_in'])

    def test_update_agave_config(self):
        config_dict = {
            'sessions': {
                'designsafe': {
                    'USERNAME': {
                        'test_client': {
                            'refresh_token': 'VALID_REFRESH_TOKEN',
                            'expires_in': 3600,
                            'expires_at': 'Mon Nov  4 15:24:54 2019',
                            'created_at': 1572877494,
                            'username': 'USERNAME',
                            'token_username': None,
                            'client_name': 'test_client',
                            'use_nonce': False,
                            'verify': True,
                            'proxies': {},
                            'tenantid': 'designsafe',
                            'apisecret': 'VALID_API_SECRET',
                            'apikey': 'VALID_API_KEY',
                            'baseurl': 'https://agave.designsafe-ci.org/',
                            'access_token': 'VALID_ACCESS_TOKEN'
                        }
                    }
                }
            }
        }
        temp_dir = tempfile.mkdtemp()
        config_path = path.join(temp_dir, 'config.json')
        current_path = path.join(temp_dir, 'current')
        with open(current_path, "w") as f:
            f.write("""{"client_name": "test_client"}""")

        update_agave_config(config_dict, config_path,
                            config_dict['sessions']['designsafe']['USERNAME']['test_client'], 'test_client')

        with open(config_path, "r") as f:
            self.assertEqual(json.load(f), config_dict)

        with open(current_path, "r") as f:
            self.assertEqual(json.load(f), config_dict['sessions']['designsafe']['USERNAME']['test_client'])

    @vcr.use_cassette('test_agave/get_file.yaml')
    def test_get_file(self):
        temp_dir = tempfile.mkdtemp()
        config = read_config(DEFAULT_CONFIG_FILE)
        temp_config_file_path = path.join(temp_dir, 'config.json')

        with open(temp_config_file_path, 'w') as f:
            f.write("""{"sessions": {"designsafe": {"username": {"bdbag_test": {"refresh_token": 
            "VALID_REFRESH_TOKEN", "expires_in": 3600, "expires_at": "Mon Nov 18 16:12:12 2019", "created_at": 
            1574089932, "username": "username", "token_username": null, "client_name": "bdbag_test", "use_nonce": 
            false, "verify": true, "proxies": {}, "tenantid": "designsafe", "apisecret": "API_SECRET", 
            "apikey": "API_KEY", "baseurl": "https://agave.designsafe-ci.org/", "access_token": 
            "VALID_ACCESS_TOKEN"}}}}}""" )

        config['fetch_config']['agave']['config_file_path'] = temp_config_file_path
        keychain = read_keychain()
        test_result = get_file(
            'https://agave.designsafe-ci.org/files/v2/media/system/designsafe.storage.published//PRJ-0000/test_file.pdf',
            temp_dir + '/test_file.pdf',
            keychain,  # Can't have a None here... even for testing
            code='designsafe',
            config=config
        )
        self.assertEqual(test_result, temp_dir + '/test_file.pdf')

if __name__ == '__main__':
    unittest.main()
