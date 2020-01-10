import requests
import time
from bdbag.bdbag_config import *
from bdbag.fetch.auth.keychain import *
from bdbag.fetch.transports import fetch_http

logger = logging.getLogger(__name__)


def get_tenants():
    resp = requests.get('https://api.tacc.utexas.edu/tenants')
    resp_dict = json.loads(resp.text)['result']
    tenant_dict = {}
    for tenant in resp_dict:
        tenant_dict[tenant['baseUrl']] = tenant['code']
    return tenant_dict


def detect_agave(url):
    url = url.lower()
    for tenant in agave_tenants:
        if url.startswith(tenant):
            return True, agave_tenants[tenant]
    return False, None


# Return Agave configuration as dictionary
def get_agave_config(agave_user_config_path):
    try:
        with open(agave_user_config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning('No Agave config found in %s' % agave_user_config_path)
    except Exception as e:
        logger.warning('Undefined exception: %s' % e)


def is_token_expired(access_token, base_url):
    try:
        headers = {"Authorization": "Bearer %s" % access_token}
        resp_json = requests.get('%sprofiles/v2/me' % base_url, headers=headers).json()
        # Check if it is an expired token error
        if hasattr(resp_json.get('fault'), 'get'):
            if "Invalid Credentials" in resp_json.get("fault").get("message"):
                return True
    except Exception as exc:
        logger.warning("Unhandled exception while checking if Agave token is expired: %s" % get_typed_exception(exc))
    return False


def refresh_token(auth):
    refresh_token = auth['refresh_token']
    api_key = auth['apikey']
    api_secret = auth['apisecret']
    endpoint = auth['baseurl'] + 'token'

    # Make refresh request.
    # try requests.auth.HTTPBasicAuth(api_key, api_secret)
    try:
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'scope': 'PRODUCTION',
        }
        resp = requests.post(endpoint, headers=headers, data=data, auth=(api_key, api_secret))
        if not resp.ok:
            logger.warning('Unable to refresh Agave token: ' % resp.json())
            return False
    except requests.exceptions.MissingSchema as err:
        logger.warning('Agave refresh token request missing schema: %s' % err)
        return False

    response = resp.json()

    now = int(time.time())
    expires_at = now + int(response['expires_in'])

    auth['access_token'] = response['access_token']
    auth['refresh_token'] = response['refresh_token']
    auth['expires_in'] = response['expires_in']
    auth['created_at'] = str(now)
    auth['expires_at'] = time.strftime('%a %b %-d %H:%M:%S %Z %Y', time.localtime(expires_at))
    return True


def update_agave_config(config_dict, agave_config_path, auth, auth_name):
    try:
        code = auth['tenantid']
        username = auth['username']
        config_dict['sessions'][code][username][auth_name] = auth
    except KeyError as e:
        logger.warning('KeyError: %s' % e)

    # Update config.json
    config_json_output = json.dumps(config_dict)
    try:
        with open(agave_config_path, 'w') as f:
            f.write(config_json_output)
    except Exception:
        logger.warning('Can\'t write Agave config found in %s' % agave_config_path)

    # Update current
    # Read file, check if auth_name is current
    # if it is: overwrite file
    current_json_output = json.dumps(auth)
    agave_dir_path = os.path.dirname(os.path.abspath(agave_config_path))
    agave_current_path = os.path.join(agave_dir_path, 'current')

    try:
        if get_agave_config(agave_current_path)['client_name'] == auth_name:
            with open(agave_current_path, 'w') as f:
                f.write(current_json_output)
    except KeyError:
        logger.warning('Invalid Agave current in %s' % agave_current_path)
    except Exception as e:
        logger.warning('Can\'t write Agave current found in %s\n%s' % agave_current_path, e)


def get_file(url, output_path, auth_config, **kwargs):
    try:
        config = kwargs.get('config')
        # Check for custom Agave configuration path, otherwise use default
        # Wrap in try catch
        if config['fetch_config']['agave']['config_file_path']:
            agave_config_path = config['fetch_config']['agave']['config_file_path']
        else:
            agave_config_path = os.path.expanduser('~/.agave/config.json')

        # Based on code/tenant id, pull in users/token info from Agave configuration
        code = kwargs.get('code')
        config_dict = get_agave_config(agave_config_path)
        agave_auths = config_dict['sessions'][code]


        # For every auth name in every username in the config.json, attempt download
        # Return when successful
        for username in agave_auths:
            for auth_name in agave_auths[username]:
                auth = agave_auths[username][auth_name]

                # Call small api endpoint to check if token is valid
                # Refresh token if expired
                if is_token_expired(auth['access_token'], auth['baseurl']):
                    logger.info('Agave OAuth token expired! Refreshing...')
                    if not refresh_token(auth):
                        continue
                    update_agave_config(config_dict, agave_config_path, auth, auth['client_name'])

                # Attempt download
                headers = {'Authorization': 'Bearer %s' % auth['access_token']}
                result = fetch_http.get_file(url, output_path, auth_config, headers=headers)

                return result
    except KeyError as e:
        logger.warning('KeyError: %s' % e)
    except Exception as e:
        logger.warning('Exception: %s' % e)
    return None


agave_tenants = get_tenants()

if __name__ == '__main__':
    keychain = read_keychain()
    test_result = get_file(
        'https://agave.designsafe-ci.org/files/v2/media/system/designsafe.storage.published//PRJ-2528/Wright_Reaserchpaper.pdf',
        '/home/elias/bdbag_test/Wright_Reaserchpaper.pdf',
        keychain, # Can't have a None here... even for testing
        code='designsafe',
        config=read_config(DEFAULT_CONFIG_FILE)
    )
    print(test_result)
