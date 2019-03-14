import os

import requests

from intezer_sdk import consts
from intezer_sdk import errors

try:
    from http import HTTPStatus
except ImportError:
    import httplib as HTTPStatus

_global_api = None


class IntezerApi(object):
    def __init__(self,
                 api_version=None,
                 api_key=None,
                 base_url=None):  # type: (str, str,str) -> None
        self.full_url = base_url + api_version
        self.api_key = api_key
        self._access_token = None
        self._session = None

    def _request(self,
                 method,
                 path,
                 params=None,
                 headers=None,
                 files=None):  # type: (str, str, dict, dict, dict) -> Response
        if not self._session:
            self._set_session()

        if files:
            response = self._session.request(
                method,
                self.full_url + path,
                data=params or {},
                headers=headers or {},
                files=files
            )
        else:
            response = self._session.request(
                method,
                self.full_url + path,
                json=params or {},
                headers=headers
            )

        return response

    def analyze_by_hash(self,
                        file_hash,
                        dynamic_unpacking=None,
                        static_unpacking=None):  # type: (str,bool,bool) -> str
        params = self._param_initialize(dynamic_unpacking, static_unpacking)

        params['hash'] = file_hash
        response = self._request(path='/analyze-by-hash', params=params, method='POST')
        self._handle_analysis_reponse_status_code(response)

        return self._get_analysis_id_from_response(response)

    def analyze_by_file(self,
                        file_path,
                        dynamic_unpacking=None,
                        static_unpacking=None):  # type: (str,bool,bool) -> str
        params = self._param_initialize(dynamic_unpacking, static_unpacking)

        with open(file_path, 'rb') as file_to_upload:
            file = {'file': (os.path.basename(file_path), file_to_upload)}

            response = self._request(path='/analyze', files=file, params=params, method='POST')

        self._handle_analysis_reponse_status_code(response)

        return self._get_analysis_id_from_response(response)

    def get_analysis_response(self, analyses_id):  # type: (str) -> Response
        response = self._request(path='/analyses/{}'.format(analyses_id), method='GET')
        response.raise_for_status()

        return response

    def index_by_sha256(self, sha256, index_as, family_name=None):  # type: (str, IndexType, str) -> Response
        params = {'index_as': index_as.value}
        if family_name:
            params['family_name'] = family_name

        response = self._request(path='/files/{}/index'.format(sha256), params=params, method='POST')
        self._handle_Index_reponse_status_code(response)

        return self._get_index_id_from_response(response)

    def index_by_file(self, file_path, index_as, family_name=None):  # type: (str, IndexType, str) -> Response
        params = {'index_as': index_as.value}
        if family_name:
            params['family_name'] = family_name

        with open(file_path, 'rb') as file_to_upload:
            file = {'file': (os.path.basename(file_path), file_to_upload)}

            response = self._request(path='/files/index', params=params, files=file, method='POST')

        self._handle_Index_reponse_status_code(response)

        return self._get_index_id_from_response(response)

    def get_index_response(self, index_id):  # type: (str) -> Response
        response = self._request(path='/files/index/{}'.format(index_id), method='GET')
        response.raise_for_status()

        return response

    def _set_access_token(self, api_key):  # type: (str) -> str
        if self._access_token is None:
            response = requests.post(self.full_url + '/get-access-token', json={'api_key': api_key})

            if response.status_code != HTTPStatus.OK:
                raise errors.InvalidApiKey()

            self._access_token = response.json()['result']

    def _set_session(self):
        self._session = requests.session()
        self._set_access_token(self.api_key)
        self._session.headers['Authorization'] = 'Bearer {}'.format(self._access_token)
        self._session.headers['User-Agent'] = consts.USER_AGENT

    def _param_initialize(self, dynamic_unpacking=None, static_unpacking=None):
        params = {}

        if dynamic_unpacking is not None:
            params['dynamic_unpacking'] = dynamic_unpacking
        if static_unpacking is not None:
            params['static_unpacking'] = static_unpacking

        return params

    def _handle_analysis_reponse_status_code(self, response):
        if response.status_code == HTTPStatus.NOT_FOUND:
            raise errors.HashDoesNotExistError()
        elif response.status_code == HTTPStatus.CONFLICT:
            raise errors.AnalysisIsAlreadyRunning()
        elif response.status_code == HTTPStatus.FORBIDDEN:
            raise errors.InsufficientQuota()
        elif response.status_code != HTTPStatus.CREATED:
            raise errors.IntezerError('Error in response status code:{}'.format(response.status_code))

    def _handle_Index_reponse_status_code(self, response):
        if response.status_code == HTTPStatus.NOT_FOUND:
            raise errors.HashDoesNotExistError()
        elif response.status_code != HTTPStatus.CREATED:
            raise errors.IntezerError('Error in response status code:{}'.format(response.status_code))

    def _get_analysis_id_from_response(self, response):
        return response.json()['result_url'].split('/')[2]

    def _get_index_id_from_response(self, response):
        return response.json()['result_url'].split('/')[3]


def get_global_api():  # type: () -> IntezerApi
    global _global_api

    if not _global_api:
        raise errors.GlobalApiIsNotInitialized()

    return _global_api


def set_global_api(api_key=None):
    global _global_api
    api_key = os.environ.get('INTEZER_ANALYZE_API_KEY') or api_key
    _global_api = IntezerApi(consts.API_VERSION, api_key, consts.BASE_URL)
