import asyncio
import base64
import http.client
import json
import logging
import os
import re
import ssl
import sys
import time

import websockets
import requests
from requests.auth import HTTPDigestAuth
from urllib3 import encode_multipart_formdata
from .const import (
    DELTADORE_API_SITES,
    DELTADORE_AUTH_CLIENTID,
    DELTADORE_AUTH_SCOPE,
    DELTADORE_AUTH_URL,
    DELTADORE_AUTH_GRANT_TYPE,
    MEDIATION_URL,
)
from health.HealthState import HealthState

logger = logging.getLogger(__name__)

# How long to wait for someone to press the hub's button, and how often to
# retry while waiting.
DEFAULT_PAIRING_TIMEOUT = 180
PAIRING_RETRY_DELAY = 3


class TydomClient:
    def __init__(
        self,
        mac,
        password,
        polling_interval,
        thermostat_cool_mode_temp_default,
        thermostat_heat_mode_temp_default,
        host=MEDIATION_URL,
        alarm_pin=None,
        thermostat_custom_presets=None,
        password_store=None,
        pairing_timeout=DEFAULT_PAIRING_TIMEOUT,
    ):
        logger.debug("Initializing TydomClient Class")

        self.password = password
        self.mac = mac
        self.host = host
        self.alarm_pin = alarm_pin
        self.password_store = password_store
        self.pairing_timeout = int(pairing_timeout)
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
        self.in_memory = {}
        self.polling_interval = int(polling_interval)

        if thermostat_custom_presets is None:
            self.thermostat_custom_presets = None
        else:
            self.thermostat_custom_presets = json.loads(thermostat_custom_presets)
            self.current_preset = {}

        self.thermostat_cool_mode_temp_default = int(thermostat_cool_mode_temp_default)
        self.thermostat_heat_mode_temp_default = int(thermostat_heat_mode_temp_default)

        self.health_state = HealthState()

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
    def getTydomCredentials(login: str, password: str, macaddress: str):
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

            response = requests.get(
                DELTADORE_API_SITES + macaddress,
                headers={"Authorization": f"Bearer {access_token}"},
            )

            json_response = response.json()
            response.close()

            password = None
            if (
                "sites" in json_response
                and len(json_response["sites"]) > 0
                and "gateway" in json_response["sites"][0]
            ):
                password = json_response["sites"][0]["gateway"]["password"]
            logger.debug(
                "Your Tydom password : %s",
                json_response["sites"][0]["gateway"]["password"],
            )
            return password

        except Exception as e:
            logger.info(e)
            return None

    @staticmethod
    async def read_local_password(host, mac, ssl_context):
        """Read the gateway's local password, if its pairing window is open.

        A Tydom hub accepts an unauthenticated connection only during the
        short window that follows a press on its physical button, and serves
        its own local password on /configs/gateway/password. Outside that
        window it answers 401 and this returns None.

        Note that this password is a different secret from the one the Delta
        Dore cloud API returns for the same gateway: the cloud one does not
        authenticate a local connection.
        """
        try:
            connection = await websockets.connect(
                f"wss://{host}:443/mediation/client?mac={mac}&appli=1",
                additional_headers={"Sec-WebSocket-Version": "13"},
                ssl=ssl_context,
                ping_timeout=None,
            )
        except Exception:
            # Still locked, or unreachable; the caller decides whether to
            # keep waiting.
            return None

        try:
            request = (
                "GET /configs/gateway/password HTTP/1.1\r\n"
                "Content-Length: 0\r\n"
                "Content-Type: application/json; charset=UTF-8\r\n"
                "Transac-Id: 0\r\n\r\n"
            )
            await connection.send(request.encode("ascii"))
            # The hub also pushes unsolicited events, so skip anything that is
            # not the answer to this request.
            for _ in range(5):
                reply = await asyncio.wait_for(connection.recv(), timeout=5)
                text = (
                    reply if isinstance(reply, str) else reply.decode(errors="replace")
                )
                if "/configs/gateway/password" in text:
                    return TydomClient.extract_password(text)
            return None
        except Exception as e:
            logger.warning("Could not read the local password (%s)", e)
            return None
        finally:
            await connection.close()

    @staticmethod
    def extract_password(response):
        """Pull the password out of a /configs/gateway/password response."""
        separator = response.find("\r\n\r\n")
        body = response[separator + 4 :] if separator != -1 else response

        payload = ""
        lines = body.split("\r\n")
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            index += 1
            if not line:
                continue
            # Chunked transfer encoding: a hex length, then that chunk.
            if not re.fullmatch(r"[0-9a-fA-F]+", line):
                payload += line
                continue
            if int(line, 16) == 0:
                break
            if index < len(lines):
                payload += lines[index]
                index += 1

        try:
            return json.loads(payload)["current"]
        except (ValueError, KeyError):
            return None

    async def pair_locally(self):
        """Wait for the hub's button to be pressed, then keep its password.

        Returns True once a password has been obtained.
        """
        logger.warning(
            "No usable local password for the Tydom hub at %s. "
            "PRESS THE BUTTON ON THE HUB NOW: it will be read automatically "
            "and stored, and will not be asked for again. Waiting up to %ss.",
            self.host,
            self.pairing_timeout,
        )

        deadline = time.monotonic() + self.pairing_timeout
        while time.monotonic() < deadline:
            password = await self.read_local_password(
                self.host, self.mac, self.ssl_context
            )
            if password is not None:
                logger.info("Paired with the Tydom hub, local password read")
                self.password = password
                if self.password_store is not None:
                    self.password_store.write(password)
                return True
            remaining = int(deadline - time.monotonic())
            logger.info(
                "Hub still locked, press its button (%ss left)", max(remaining, 0)
            )
            await asyncio.sleep(PAIRING_RETRY_DELAY)

        return False

    async def connect(self, allow_pairing=True):
        logger.info("Connecting to tydom")

        # A local hub can hand out its own password once its button is
        # pressed, so an empty password is not a fatal configuration error
        # there: pair first, then connect with what we were given.
        if not self.remote_mode and not self.password and allow_pairing:
            if not await self.pair_locally():
                logger.error(
                    "Nobody pressed the button on the Tydom hub, so no local "
                    "password could be obtained. Restart and press it to "
                    "pair, or set TYDOM_PASSWORD explicitly."
                )
                sys.exit(1)

        http_headers = {
            "Connection": "Upgrade",
            "Upgrade": "websocket",
            "Host": self.host + ":443",
            "Accept": "*/*",
            "Sec-WebSocket-Key": self.generate_random_key(),
            "Sec-WebSocket-Version": "13",
        }
        conn = http.client.HTTPSConnection(self.host, 443, context=self.ssl_context)

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
        www_authenticate = res.headers["WWW-Authenticate"]
        if www_authenticate is not None:
            # A gateway in its pairing window answers without challenging, so
            # only authenticate when we were actually challenged.
            challenge = self.parse_digest_challenge(www_authenticate)
            websocket_headers = {"Authorization": self.build_digest_headers(challenge)}

        logger.debug("Upgrading http connection to websocket....")

        if self.ssl_context is not None:
            websocket_ssl_context = self.ssl_context
        else:
            websocket_ssl_context = True  # Verify certificate

        # outer loop restarted every time the connection fails
        logger.debug("Attempting websocket connection with Tydom hub")
        """
            Connecting to webSocket server
            websockets.client.connect returns a WebSocketClientProtocol, which is used to send and receive messages
        """
        try:
            self.connection = await websockets.connect(
                f"wss://{self.host}:443/mediation/client?mac={self.mac}&appli=1",
                additional_headers=websocket_headers,
                ssl=websocket_ssl_context,
                ping_timeout=None,
            )
            logger.info("Connected to tydom")
            self.health_state.update_tydom_status(True)
            return self.connection
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code != 401:
                logger.error(
                    "Tydom rejected the websocket handshake (HTTP %s)", e.status_code
                )
                sys.exit(1)

            # The credentials were refused. On a local hub they may simply
            # have gone stale (hub reset, password changed), so forget them
            # and pair again rather than requiring manual intervention.
            if not self.remote_mode and allow_pairing:
                logger.warning(
                    "The Tydom hub refused the local password (HTTP 401). "
                    "Discarding it and pairing again."
                )
                if self.password_store is not None:
                    self.password_store.clear()
                self.password = None
                if await self.pair_locally():
                    # allow_pairing=False so a second refusal is reported
                    # instead of looping on the button forever.
                    return await self.connect(allow_pairing=False)
                logger.error(
                    "Nobody pressed the button on the Tydom hub, so the "
                    "local password could not be renewed."
                )
                sys.exit(1)

            logger.error(
                "Tydom rejected the credentials (HTTP 401). The gateway's "
                "local password is NOT the one returned by the Delta Dore "
                "cloud API: they are two different secrets."
            )
            sys.exit(1)
        except Exception as e:
            logger.error("Exception when trying to connect with websocket (%s)", e)
            sys.exit(1)

    async def disconnect(self):
        if self.connection is not None:
            logger.info("Disconnecting")
            await self.connection.close()
            self.health_state.update_tydom_status(False)
            logger.info("Disconnected")

    # Generate 16 bytes random key for Sec-WebSocket-Keyand convert it to
    # base64
    @staticmethod
    def generate_random_key():
        return base64.b64encode(os.urandom(16))

    @staticmethod
    def parse_digest_challenge(header_value):
        """Parse a "WWW-Authenticate: Digest ..." header into its directives.

        The realm must be echoed back exactly as the gateway sent it: it feeds
        the digest response hash (HA1 = MD5(username:realm:password)), so a
        hardcoded realm silently produces a response that never matches, even
        with the correct password. Recent Tydom firmwares answer with
        realm="Protected Area", which no longer matches the value that used to
        be hardcoded here.
        """
        return {
            key: quoted or unquoted
            for key, quoted, unquoted in re.findall(
                r'(\w+)=(?:"([^"]*)"|([^,\s]+))', header_value
            )
        }

    # Build the headers of Digest Authentication
    def build_digest_headers(self, challenge):
        digest_auth = HTTPDigestAuth(self.mac, self.password)
        chal = dict()
        chal["nonce"] = challenge["nonce"]
        chal["realm"] = challenge["realm"]
        chal["qop"] = challenge.get("qop", "auth")
        if "opaque" in challenge:
            chal["opaque"] = challenge["opaque"]
        digest_auth._thread_local.chal = chal
        digest_auth._thread_local.last_nonce = ""
        digest_auth._thread_local.nonce_count = 0
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
            self.cmd_prefix
            + method
            + " "
            + msg
            + " HTTP/1.1\r\nContent-Length: 0\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n"
        )
        a_bytes = bytes(str, "ascii")
        logger.debug(
            "Sending message to tydom (%s %s)",
            method,
            msg if "pwd" not in msg else "***",
        )

        if self.connection is not None:
            await self.connection.send(a_bytes)
        else:
            logger.warning(
                "Cannot send message to Tydom because no connection has been established yet"
            )

    # Give order (name + value) to endpoint
    async def put_devices_data(self, device_id, endpoint_id, name, value):
        # For shutter, value is the percentage of closing
        body = '[{"name":"' + name + '","value":"' + value + '"}]'
        # endpoint_id is the endpoint = the device (shutter in this case) to
        # open.
        str_request = (
            self.cmd_prefix
            + f"PUT /devices/{device_id}/endpoints/{endpoint_id}/data HTTP/1.1\r\nContent-Length: "
            + str(len(body))
            + "\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n"
            + body
            + "\r\n\r\n"
        )
        a_bytes = bytes(str_request, "ascii")
        logger.debug("Sending message to tydom (%s %s)", "PUT devices data", body)
        await self.connection.send(a_bytes)
        return 0

    async def put_areas_data(self, area_id, data):
        formatted_data = []
        for key, value in data.items():
            formatted_data.append({"name": key, "value": value})
        body = json.dumps(formatted_data)
        str_request = (
            self.cmd_prefix
            + f"PUT /areas/{area_id}/data HTTP/1.1\r\nContent-Length: "
            + str(len(body))
            + "\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n"
            + body
            + "\r\n\r\n"
        )
        a_bytes = bytes(str_request, "ascii")
        logger.debug("Sending message to tydom (%s %s)", "PUT areas data", body)
        await self.connection.send(a_bytes)
        return 0

    async def put_home_hvac_mode(self, mode):
        """Set the zone-level HVAC mode (STOP / HEATING / COOLING).

        Tells the heat pump which way to run (or stop). Tydom acknowledges
        with a 200 OK then broadcasts the resulting state to all clients via
        PUT /devices/data (per-thermostat authorization update) and
        POST /events/home/hvac.
        """
        body = '{"mode":"' + mode + '"}'
        str_request = (
            self.cmd_prefix
            + "PUT /home/hvac/data HTTP/1.1\r\nContent-Length: "
            + str(len(body))
            + "\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n"
            + body
            + "\r\n\r\n"
        )
        a_bytes = bytes(str_request, "ascii")
        logger.debug("Sending message to tydom (%s %s)", "PUT home hvac data", body)
        await self.connection.send(a_bytes)
        return 0

    async def put_alarm_cdata(self, device_id, alarm_id=None, value=None, zone_id=None):
        # Credits to @mgcrea on github !
        # AWAY # "PUT /devices/{}/endpoints/{}/cdata?name=alarmCmd HTTP/1.1\r\ncontent-length: 29\r\ncontent-type: application/json; charset=utf-8\r\ntransac-id: request_124\r\n\r\n\r\n{"value":"ON","pwd":{}}\r\n\r\n"
        # HOME "PUT /devices/{}/endpoints/{}/cdata?name=zoneCmd HTTP/1.1\r\ncontent-length: 41\r\ncontent-type: application/json; charset=utf-8\r\ntransac-id: request_46\r\n\r\n\r\n{"value":"ON","pwd":"{}","zones":[1]}\r\n\r\n"
        # DISARM "PUT /devices/{}/endpoints/{}/cdata?name=alarmCmd HTTP/1.1\r\ncontent-length: 30\r\ncontent-type: application/json; charset=utf-8\r\ntransac-id: request_7\r\n\r\n\r\n{"value":"OFF","pwd":"{}"}\r\n\r\n"
        # PANIC (Active la sirène) "PUT
        # /devices/{}/endpoints/{}/cdata?name=alarmCmd
        # HTTP/1.1\r\ncontent-length: 30\r\ncontent-type: application/json;
        # charset=utf-8\r\ntransac-id:
        # request_7\r\n\r\n\r\n{"value":"PANIC","pwd":"{}"}\r\n\r\n"

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
            if value == "ACK":
                cmd = "ackEventCmd"
                body = '{"pwd":"' + str(self.alarm_pin) + '"}'
            elif zone_id is None:
                cmd = "alarmCmd"
                body = (
                    '{"value":"' + str(value) + '","pwd":"' + str(self.alarm_pin) + '"}'
                )
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
                self.cmd_prefix
                + "PUT /devices/{device}/endpoints/{alarm}/cdata?name={cmd} HTTP/1.1\r\nContent-Length: ".format(
                    device=str(device_id), alarm=str(alarm_id), cmd=str(cmd)
                )
                + str(len(body))
                + "\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n"
                + body
                + "\r\n\r\n"
            )

            a_bytes = bytes(str_request, "ascii")
            logger.debug("Sending message to tydom (%s %s) PUT cdata", body)

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
        logger.debug("running post_refresh")
        msg_type = "/refresh/all"
        req = "POST"
        await self.send_message(method=req, msg=msg_type)
        # Get poll device data
        nb_poll_devices = len(self.poll_device_urls)
        logger.debug("nb_poll_devices : %d", nb_poll_devices)
        for polling_device in self.poll_device_urls:
            await self.get_poll_device_data(polling_device)

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
            self.cmd_prefix
            + f"GET /devices/{device_id}/endpoints/{device_id}/data HTTP/1.1\r\nContent-Length: 0\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n"
        )
        a_bytes = bytes(str_request, "ascii")
        await self.connection.send(a_bytes)

    async def get_area_data(self, id):
        device_id = str(id)
        str_request = (
            self.cmd_prefix
            + f"GET /areas/{device_id}/data HTTP/1.1\r\nContent-Length: 0\r\nContent-Type: application/json; charset=UTF-8\r\nTransac-Id: 0\r\n\r\n"
        )
        a_bytes = bytes(str_request, "ascii")
        await self.connection.send(a_bytes)

    async def get_poll_device_data(self, url):
        logger.debug("get_poll_device_data : %s", url)
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
        if str(boiler_id) not in self.current_preset:
            await self.set_thermostat_custom_current_preset(str(boiler_id), "none")
        return self.current_preset[str(boiler_id)]

    async def set_thermostat_custom_current_preset(self, boiler_id, preset):
        logger.debug("set preset %s for %s", preset, boiler_id)
        self.current_preset[str(boiler_id)] = str(preset)

    async def set_in_memory(self, id, name, value):
        logger.debug("set %s, %s : %s in memory", id, name, value)
        if id not in self.in_memory:
            self.in_memory |= {id: {name: value}}
        else:
            self.in_memory[id] |= {name: value}
        logger.debug("Memory state : %s", self.in_memory)

    async def get_in_memory(self, id, name=None):
        logger.debug("get %s, %s in memory", id, name)
        if name is None:
            return self.in_memory[id]
        else:
            if id in self.in_memory:
                if name in self.in_memory[id]:
                    return self.in_memory[id][name]
            return None
