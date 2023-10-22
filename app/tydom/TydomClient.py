import base64
import http.client
import json
import logging
import os
import ssl
import sys

import websockets
import requests
from requests.auth import HTTPDigestAuth
from urllib3 import encode_multipart_formdata
from .const import *

logger = logging.getLogger(__name__)


class TydomClient:
    def __init__(
            self,
            mac,
            password,
            alarm_pin=None,
            host=MEDIATION_URL,
            thermostat_custom_presets=None):
        logger.debug("Initializing TydomClient Class")

        self.password = password
        self.mac = mac
        self.host = host
        self.alarm_pin = alarm_pin
        self.connection = None
        self.remote_mode = True
        self.ssl_context = None
        self.cmd_prefix = "\x02"
        self.reply_timeout = 4
        self.ping_timeout = None
        self.refresh_timeout = 42
        self.sleep_time = 2
        self.incoming = None
        # Some devices (like Tywatt) need polling
        self.poll_device_urls = []
        self.current_poll_index = 0

        if thermostat_custom_presets is None:
            self.thermostat_custom_presets = None
        else:
            self.thermostat_custom_presets = json.loads(thermostat_custom_presets)
            self.current_preset = {}

        # Set Host, ssl context and prefix for remote or local connection
        if self.host == MEDIATION_URL:
            logger.info("Configure remote mode (%s)", self.host)
            self.remote_mode = True
            self.ssl_context = ssl._create_unverified_context()
            self.cmd_prefix = "\x02"
            self.ping_timeout = 40

        else:
            logger.info("Configure local mode (%s)", self.host)
            self.remote_mode = False
            self.ssl_context = ssl._create_unverified_context()
            self.ssl_context.options |= 0x4
            self.cmd_prefix = ""
            self.ping_timeout = None

    @staticmethod
    def getTydomCredentials(login: str, password: str, macaddress: str, site_name: str):
        """get tydom credentials from Delta Dore"""
        try:
            response = requests.get(DELTADORE_AUTH_URL)

            json_response = response.json()
            response.close()
            signin_url = json_response["token_endpoint"]

            body, ct_header = encode_multipart_formdata(
                {
                    "username": f"{login}",
                    "password": f"{password}",
                    "grant_type": DELTADORE_AUTH_GRANT_TYPE,
                    "client_id": DELTADORE_AUTH_CLIENTID,
                    "scope": DELTADORE_AUTH_SCOPE,
                }
            )

            response = requests.post(
                url=signin_url,
                headers={"Content-Type": ct_header},
                data=body,
            )

            json_response = response.json()
            response.close()
            access_token = json_response["access_token"]

            if site_name is not None and site_name!= "":
                params = {'offset': 0, 'limit': 60}
                # TODO: handle pagination
                response =requests.get(DELTADORE_SITE_LIST, headers={"Authorization": f"Bearer {access_token}"}, params=params)
                known_sites = {}
                for site in response.json()["site_access_list"]:
                    site_label = site.get("label", None)
                    site_mac = site.get("site", {}).get("gateway", {}).get("mac", "Unknown")
                    known_sites[site_label] = site_mac
                    if site_label == site_name:
                        password = site.get("site", {}).get("gateway", {}).get("password", None)
                        if password is not None:
                            logger.debug("Your Tydom password for site %s (mac: %s) : %s", site_name, site.get("site", {}).get("gateway", {}).get("mac", "Unknown"), password) 
                            return password
                logger.error(
                    "unable to find site with name %s. Will try with mac adress",
                    site_name)
                logger.error("available sites:")
                for k, v in known_sites.items():
                    logger.error("%s: %s" % (k, v))

            response = requests.get(DELTADORE_API_SITES + macaddress,
                                    headers={"Authorization": f"Bearer {access_token}"})

            json_response = response.json()
            response.close()

            password = None
            if (
                "sites" in json_response
                and len(json_response["sites"]) > 0
                and "gateway" in json_response["sites"][0]
            ):
                password = json_response["sites"][0]["gateway"]["password"]
            logger.debug("Your Tydom password : %s", json_response["sites"][0]["gateway"]["password"]) 
            return password

        except Exception as exception:
            return None

    async def connect(self):
        logger.info('Connecting to tydom')
        http_headers = {
            "Connection": "Upgrade",
            "Upgrade": "websocket",
            "Host": self.host + ":443",
            "Accept": "*/*",
            "Sec-WebSocket-Key": self.generate_random_key(),
            "Sec-WebSocket-Version": "13",
        }
        conn = http.client.HTTPSConnection(
            self.host, 443, context=self.ssl_context)

        # Get first handshake
        conn.request(
            "GET",
            "/mediation/client?mac={}&appli=1".format(self.mac),
            None,
            http_headers,
        )
        res = conn.getresponse()
        conn.close()

        logger.debug("Response headers")
        logger.debug(res.headers)

        logger.debug("Response code")
        logger.debug(res.getcode())

        # Read response
        logger.debug("response")
        logger.debug(res.read())
        res.read()

        # Get authentication
        websocket_headers = {}
        try:
            # Local installations are unauthenticated but we don't *know* that for certain
            # so we'll EAFP, try to use the header and fallback if we're unable.
            nonce = res.headers["WWW-Authenticate"].split(",", 3)
            # Build websocket headers
            websocket_headers = {
                "Authorization": self.build_digest_headers(nonce)}
        except AttributeError:
            pass

        logger.debug("Upgrading http connection to websocket....")

        if self.ssl_context is not None:
            websocket_ssl_context = self.ssl_context
        else:
            websocket_ssl_context = True  # Verify certificate

        # outer loop restarted every time the connection fails
        logger.debug(
            "Attempting websocket connection with Tydom hub"
        )
        """
            Connecting to webSocket server
            websockets.client.connect returns a WebSocketClientProtocol, which is used to send and receive messages
        """
        try:
            self.connection = await websockets.connect(
                f"wss://{self.host}:443/mediation/client?mac={self.mac}&appli=1",
                extra_headers=websocket_headers,
                ssl=websocket_ssl_context,
                ping_timeout=None,
            )
            logger.info('Connected to tydom')
            return self.connection
        except Exception as e:
            logger.error(
                "Exception when trying to connect with websocket (%s)", e)
            sys.exit(1)

    async def disconnect(self):
        if self.connection is not None:
            logger.info('Disconnecting')
            await self.connection.close()
            logger.info('Disconnected')

    # Generate 16 bytes random key for Sec-WebSocket-Keyand convert it to
    # base64
    @staticmethod
    def generate_random_key():
        return base64.b64encode(os.urandom(16))

    # Build the headers of Digest Authentication
    def build_digest_headers(self, nonce):
        digest_auth = HTTPDigestAuth(self.mac, self.password)
        chal = dict()
        chal["nonce"] = nonce[2].split('=', 1)[1].split('"')[1]
        chal["realm"] = "ServiceMedia" if self.remote_mode is True else "protected area"
        chal["qop"] = "auth"
        digest_auth._thread_local.chal = chal
        digest_auth._thread_local.last_nonce = nonce
        digest_auth._thread_local.nonce_count = 1
        return digest_auth.build_digest_header(
            "GET",
            "https://{host}:443/mediation/client?mac={mac}&appli=1".format(
                host=self.host, mac=self.mac
            ),
        )

    async def notify_alive(self, msg="OK"):
        pass

    def add_poll_device_url(self, url):
        self.poll_device_urls.append(url)

    # Send Generic  message
    async def send_message(self, method, msg):
        str = (
            self.cmd_prefix +
            method +
            " " +
            msg +
            " HTTP/1.1\r\nContent-Length: 0\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n")
        a_bytes = bytes(str, "ascii")
        logger.debug(
            "Sending message to tydom (%s %s)",
            method,
            msg if "pwd" not in msg else "***")

        if self.connection is not None:
            await self.connection.send(a_bytes)
        else:
            logger.warning(
                'Cannot send message to Tydom because no connection has been established yet')

    # Give order (name + value) to endpoint
    async def put_devices_data(self, device_id, endpoint_id, name, value):
        # For shutter, value is the percentage of closing
        body = '[{"name":"' + name + '","value":"' + value + '"}]'
        # endpoint_id is the endpoint = the device (shutter in this case) to
        # open.
        str_request = (
            self.cmd_prefix +
            f"PUT /devices/{device_id}/endpoints/{endpoint_id}/data HTTP/1.1\r\nContent-Length: " +
            str(
                len(body)) +
            "\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n" +
            body +
            "\r\n\r\n")
        a_bytes = bytes(str_request, "ascii")
        logger.debug("Sending message to tydom (%s %s)",
                     "PUT devices data", body)
        await self.connection.send(a_bytes)
        return 0

    async def put_areas_data(self, area_id, data):
        formatted_data = []
        for key, value in data.items():
            formatted_data.append({"name": key, "value": value})
        body = json.dumps(formatted_data)
        str_request = (
            self.cmd_prefix +
            f"PUT /areas/{area_id}/data HTTP/1.1\r\nContent-Length: " +
            str(len(body)) +
            "\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n" +
            body +
            "\r\n\r\n")
        a_bytes = bytes(str_request, "ascii")
        logger.debug("Sending message to tydom (%s %s)",
                     "PUT areas data", body)
        await self.connection.send(a_bytes)
        return 0

    async def put_alarm_cdata(self, device_id, alarm_id=None, value=None, zone_id=None):

        # Credits to @mgcrea on github !
        # AWAY # "PUT /devices/{}/endpoints/{}/cdata?name=alarmCmd HTTP/1.1\r\ncontent-length: 29\r\ncontent-type: application/json; charset=utf-8\r\ntransac-id: request_124\r\n\r\n\r\n{"value":"ON","pwd":{}}\r\n\r\n"
        # HOME "PUT /devices/{}/endpoints/{}/cdata?name=zoneCmd HTTP/1.1\r\ncontent-length: 41\r\ncontent-type: application/json; charset=utf-8\r\ntransac-id: request_46\r\n\r\n\r\n{"value":"ON","pwd":"{}","zones":[1]}\r\n\r\n"
        # DISARM "PUT /devices/{}/endpoints/{}/cdata?name=alarmCmd
        # HTTP/1.1\r\ncontent-length: 30\r\ncontent-type: application/json;
        # charset=utf-8\r\ntransac-id:
        # request_7\r\n\r\n\r\n{"value":"OFF","pwd":"{}"}\r\n\r\n"

        # variables:
        # id
        # Cmd
        # value
        # pwd
        # zones

        if self.alarm_pin is None:
            logger.warning("Tydom alarm pin is not set!")
            pass
        try:

            if zone_id is None:
                cmd = "alarmCmd"
                body = ('{"value":"' + str(value) +
                        '","pwd":"' + str(self.alarm_pin) + '"}')
            else:
                cmd = "zoneCmd"
                body = (
                    '{"value":"'
                    + str(value)
                    + '","pwd":"'
                    + str(self.alarm_pin)
                    + '","zones":"['
                    + str(zone_id)
                    + ']"}'
                )

            str_request = (
                self.cmd_prefix +
                "PUT /devices/{device}/endpoints/{alarm}/cdata?name={cmd} HTTP/1.1\r\nContent-Length: ".format(
                    device=str(device_id),
                    alarm=str(alarm_id),
                    cmd=str(cmd)) +
                str(
                    len(body)) +
                "\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n" +
                body +
                "\r\n\r\n")

            a_bytes = bytes(str_request, "ascii")
            logger.debug(
                "Sending message to tydom (%s %s)"
                "PUT cdata",
                body)

            try:
                await self.connection.send(a_bytes)
                return 0
            except BaseException:
                logger.error("put_alarm_cdata ERROR !", exc_info=True)
                logger.error(a_bytes)
        except BaseException:
            logger.error("put_alarm_cdata ERROR !", exc_info=True)

    # Get some information on Tydom
    async def get_info(self):
        msg_type = "/info"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)

    # Refresh (all)
    async def post_refresh(self):
        msg_type = "/refresh/all"
        req = "POST"
        await self.send_message(method=req, msg=msg_type)
        # Get poll device data
        nb_poll_devices = len(self.poll_device_urls)
        if self.current_poll_index < nb_poll_devices - 1:
            self.current_poll_index = self.current_poll_index + 1
        else:
            self.current_poll_index = 0
        if nb_poll_devices > 0:
            await self.get_poll_device_data(self.poll_device_urls[self.current_poll_index])

    # Get the moments (programs)
    async def get_moments(self):
        msg_type = "/moments/file"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)

    # Get the scenarios
    async def get_scenarii(self):
        msg_type = "/scenarios/file"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)

    # Send a ping (pong should be returned)
    async def ping(self):
        msg_type = "/ping"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)
        logger.debug("Ping")

    # Get all devices metadata
    async def get_devices_meta(self):
        msg_type = "/devices/meta"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)

    # Get all devices data
    async def get_devices_data(self):
        msg_type = "/devices/data"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)
        # Get poll devices data
        for url in self.poll_device_urls:
            await self.get_poll_device_data(url)

    # List the device to get the endpoint id
    async def get_configs_file(self):
        msg_type = "/configs/file"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)

    # Get metadata configuration to list poll devices (like Tywatt)
    async def get_devices_cmeta(self):
        msg_type = "/devices/cmeta"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)

    # Get all areas data
    async def get_areas_data(self):
        msg_type = "/areas/data"
        req = "GET"
        await self.send_message(method=req, msg=msg_type)

    async def get_data(self):
        await self.get_configs_file()
        await self.get_devices_cmeta()
        await self.get_devices_data()
        await self.get_areas_data()

    # Give order to endpoint
    async def get_device_data(self, id):
        # 10 here is the endpoint = the device (shutter in this case) to open.
        device_id = str(id)
        str_request = (
            self.cmd_prefix +
            f"GET /devices/{device_id}/endpoints/{device_id}/data HTTP/1.1\r\nContent-Length: 0\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n")
        a_bytes = bytes(str_request, "ascii")
        await self.connection.send(a_bytes)

    async def get_area_data(self, id):
        device_id = str(id)
        str_request = (
            self.cmd_prefix +
            f"GET /areas/{device_id}/data HTTP/1.1\r\nContent-Length: 0\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n")
        a_bytes = bytes(str_request, "ascii")
        await self.connection.send(a_bytes)

    async def get_poll_device_data(self, url):
        msg_type = url
        req = "GET"
        await self.send_message(method=req, msg=msg_type)

    async def setup(self):
        logger.info("Setup tydom client")
        await self.get_info()
        await self.post_refresh()
        await self.get_data()

    async def get_thermostat_custom_presets(self):
        logger.debug("get presets")
        return self.thermostat_custom_presets
    
    async def get_thermostat_custom_current_preset(self, boiler_id):
        logger.debug("get preset for %s", boiler_id)
        print(self.current_preset)
        if str(boiler_id) not in self.current_preset:
            await self.set_thermostat_custom_current_preset(str(boiler_id), "none" )
        return self.current_preset[str(boiler_id)]
    
    async def set_thermostat_custom_current_preset(self, boiler_id, preset):
        logger.debug("set preset %s for %s", preset, boiler_id)
        self.current_preset[str(boiler_id)] = str(preset)