#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
EDBOWebApiConnector
Author: Eldar Aliiev
Email: e.aliiev@vnmu.edu.ua
"""

import time
import requests
from requests.adapters import HTTPAdapter
from . import config as config
from .helper import EDBOWebApiHelper


class EDBOWebApiConnector(object):
    """EDBOWebApiConnector - class which implements connection
    and method execution with EDBO RESTfull API.

    Attributes:
        url_prefix  Path to RESTful API server.
    """

    # Build url to RESTful server
    url_prefix = '%s/data/EDEBOWebApi' % config.EDBO_SERVER

    def __init__(self, username: str = config.EDBO_USER, password: str = config.EDBO_PASSWORD):
        """Initialize connect and login into RESTful API server.
        :param username: Username (Default=from config file)
        :param password: Method data (Default=from config file)
        :type username: str
        :type password: str
        """
        # Initialize status
        self._status = None

        # Initialize execution_time
        self._execution_time = 0

        # Is user logged in
        self._is_logged_in = False

        # Initialize client session
        self._session = requests.Session()

        # Set default headers to own
        self._session.headers.update(self.default_headers)

        # Mount RESTful API server to our session
        self._session.mount(
            config.EDBO_SERVER,
            HTTPAdapter(max_retries=config.CONNECTION_RETRIES)
        )

        # Login into server
        self.__login(username, password)

    def __del__(self):
        """End of session"""
        # Check if user is logged in and logout if true
        if self._is_logged_in:
            # Logout from server
            self.__logout()

    @property
    def status(self) -> int:
        """Return status of last request
        :return: Status of last method execution
        :rtype: int
        """
        return self._status

    @property
    def execution_time(self) -> float:
        """Return execution time of last request
        :return: Time of last method execution
        :rtype: float
        """
        return self._execution_time

    @property
    def default_headers(self) -> dict:
        """Default request headers
        :return: Default request headers such as user-agent, referer and etc
        :rtype: dict
        """
        return {
            'Origin': config.EDBO_SERVER,
            'Referer': config.EDBO_SERVER,
            'User-Agent': config.USER_AGENT,
        }

    def __login(self, username: str = config.EDBO_USER, password: str = config.EDBO_PASSWORD):
        """Login request to RESTful API"""

        EDBOWebApiHelper.echo(u'Вхід в систему...')
        try:
            # Try to send authorization request
            response = self._session.post(
                self.url_prefix + '/oauth/token',
                data={
                    'grant_type': 'password',
                    'username': username,
                    'password': password,
                    'app_key': config.EDBO_APPLICATION_KEY,
                },
                headers=self.default_headers
            )

            # Check if authorization is successful
            if response.status_code == 200:
                # Catch session start time
                self._session_start_time = time.time()

                # Catch last response status code
                self._status = response.status_code

                # Logged in
                self._is_logged_in = True

                # Add OAuth header to session
                self._session.headers.update({
                    'authorization': 'Bearer ' + response.json().get('access_token', None),
                })

                EDBOWebApiHelper.echo(u'Вхід успішний, вітаю %s!' % config.EDBO_USER, color='green')
            elif response.status_code == 400:
                # Incorrect login data
                EDBOWebApiHelper.echo(
                    response.json().get('error', u'Трапилася невідома помилка!'),
                    color='red',
                    force_exit=True
                )
            else:
                # Fail if login is unsuccessful
                EDBOWebApiHelper.echo(
                    u'Не вдалося авторизуватися в системі!',
                    color='red',
                    force_exit=True
                )

        except requests.exceptions.ConnectionError:
            # Server is unavailable
            EDBOWebApiHelper.echo(
                u'Не вдалося встановити зв\'язок з сервером!',
                color='red',
                force_exit=True
            )

    def __logout(self):
        """Logout from server"""
        EDBOWebApiHelper.echo(u'Вихід з системи...', color='red')
        # Logout from server
        self.execute('auth/logout')

        if self.status == 204:
            # Logged out
            self._is_logged_in = False

    def execute(self, url: str, data: dict = None, headers: dict = None, json_format: bool = True):
        """Send request to RESTful server.
        :param url: Path to RESTful method
        :param data: Method data (Default=empty)
        :param headers: Default headers (Default=empty)
        :param json_format: Return results dictionary or object (Default=True)
        :type url: str
        :type data: dict
        :type headers: dict
        :type json_format: bool
        :returns: Result of method execution
        :rtype: dict, object
        """
        # Check if session is not expired (15min)
        if int(time.time() - self._session_start_time) > config.RELOGIN_AFTER:
            EDBOWebApiHelper.echo(u'Сесія добігає кінця, поновлення...')
            # Logout from server
            self.__logout()

            # Login again
            self.__login()

        # Wait between methods execution
        time.sleep(config.EXECUTION_TIMEOUT)

        # Try to execute method
        while True:
            try:
                EDBOWebApiHelper.echo(u'Виконання методу %s...' % url)

                # Catch start of execution
                execution_start = time.time()

                # Send request to RESTful server
                response = self._session.post(
                    '%s/api/%s' % (self.url_prefix, url),
                    data if data is not None else {'': ''},
                    headers if headers is not None else {}
                )

                # Catch end of execution
                execution_end = time.time()
            except requests.exceptions.ConnectionError:
                EDBOWebApiHelper.echo(
                    u'Виконання методу завершено невдало, повторна спроба...',
                    color='red'
                )

                # Retry if unsuccessful
                continue

            # Execution done
            break

        # Save last execution time
        self._execution_time = execution_end - execution_start

        # Save last status code
        self._status = response.status_code

        EDBOWebApiHelper.echo(
            u'Виконання методу завершено з кодом %d [%.3fs]' % (
                self._status,
                self._execution_time
            ),
            color='green'
        )

        # Check if server return data
        if self.status == 200:
            # Return result of method execution
            return response.json() if json_format else response
