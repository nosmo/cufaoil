import requests

class LoginFailedException(Exception):
    pass


class UninitialisedSessionException(Exception):
    pass


class BinCompanyResponseException(Exception):
    pass

class BinCompany:
    """ Generic type for a company that does bin collections """

    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._session = requests.Session()

    def login(self):
        raise NotImplemented

    def get_data(self, raw_bin_data):
        raise NotImplemented
