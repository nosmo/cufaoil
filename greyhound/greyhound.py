#!/usr/bin/env python

import json

import requests
from bs4 import BeautifulSoup


class LoginFailedException(Exception):
    pass


class UninitialisedSessionException(Exception):
    pass


class GreyhoundResponseException(Exception):
    pass


class Greyhound:
    def __init__(self, account_number, pin):
        self._account_number = account_number
        self._pin = pin
        self._session = requests.Session()

    def login(self):
        """Get a sessionid from the Greyhound web interface"""

        # get the CSRF token
        csrf_result = self._session.get("https://app.greyhound.ie/")

        post_result = self._session.post(
            "https://app.greyhound.ie/",
            data={
                "customerNo": self._account_number,
                "pinCode": self._pin,
                "csrfmiddlewaretoken": self._session.cookies["csrftoken"],
            },
            # without this header this request will silently fail
            headers={"referer": "https://app.greyhound.ie/"},
        )

        # If we don't have a sessionid by now, we've failed
        if not "sessionid" in self._session.cookies:
            raise LoginFailedException(result.text)

        return True

    def parse_raw_data(self, raw_bin_data):
        """Reorganise web information into something slightly simpler

        In future this should capture more information from the
        supplied dict.
        """

        bin_data = {"green": {}, "brown": {}, "black": {}}

        for raw_entry in raw_bin_data:
            bin_data[raw_entry["waste_type"].lower()][raw_entry["date_time"]] = float(
                raw_entry["weight"]
            )

        return bin_data

    def get_data(self):
        """Fetch data from the Greyhound web UI"""

        if not "sessionid" in self._session.cookies:
            raise UninitialisedSessionException(
                "Tried to get bin data on an uninitialised session"
            )

        raw_bin_data = {}

        result = self._session.get(
            "https://app.greyhound.ie/collection/collection_history/green/"
        )
        soup = BeautifulSoup(result.text, features="html.parser")

        for script in soup.find_all("script"):
            if script.contents and "blackBinsData" in script.contents[0]:
                jsdata_lines = [
                    i
                    for i in script.contents[0].split("\n")
                    if i.startswith("            res")
                ]
                if jsdata_lines:
                    raw_bin_data = json.loads(jsdata_lines[0].strip().split("=")[1])

        if not raw_bin_data:
            raise GreyhoundResponseException("Couldn't find raw bin data when scraping")

        bin_data = self.parse_raw_data(raw_bin_data)

        return bin_data
