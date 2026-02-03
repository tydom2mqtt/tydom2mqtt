import asyncio
import json
import logging
from typing import Optional

from .HealthState import HealthState

logger = logging.getLogger(__name__)


class HealthServer:
    """Minimal async HTTP server for health checks."""

    def __init__(self, port: int = 8080):
        self.port = port
        self.health_state = HealthState()
        self._server: Optional[asyncio.AbstractServer] = None

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle an incoming HTTP request."""
        try:
            # Read the request line
            request_line = await asyncio.wait_for(
                reader.readline(), timeout=5.0
            )
            if not request_line:
                return

            request_str = request_line.decode("utf-8", errors="ignore").strip()
            logger.debug("Health server received: %s", request_str)

            # Parse request
            parts = request_str.split()
            if len(parts) >= 2:
                method, path = parts[0], parts[1]
            else:
                method, path = "GET", "/"

            # Drain remaining headers
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                if line == b"\r\n" or line == b"\n" or not line:
                    break

            # Handle routes
            if method == "GET" and path == "/health":
                await self._send_health_response(writer)
            else:
                await self._send_not_found(writer)

        except asyncio.TimeoutError:
            logger.debug("Health server request timeout")
        except Exception as e:
            logger.debug("Health server error: %s", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _send_health_response(self, writer: asyncio.StreamWriter) -> None:
        """Send the health check response."""
        status_dict = self.health_state.get_status_dict()
        body = json.dumps(status_dict, indent=2)

        if status_dict["healthy"]:
            status_line = "HTTP/1.1 200 OK"
        else:
            status_line = "HTTP/1.1 503 Service Unavailable"

        response = (
            f"{status_line}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{body}"
        )

        writer.write(response.encode("utf-8"))
        await writer.drain()

    async def _send_not_found(self, writer: asyncio.StreamWriter) -> None:
        """Send a 404 response."""
        body = '{"error": "Not Found"}'
        response = (
            f"HTTP/1.1 404 Not Found\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
            f"{body}"
        )
        writer.write(response.encode("utf-8"))
        await writer.drain()

    async def start(self) -> None:
        """Start the health server."""
        try:
            self._server = await asyncio.start_server(
                self.handle_client, "0.0.0.0", self.port
            )
            logger.info("Health server started on port %d", self.port)
        except Exception as e:
            logger.error("Failed to start health server: %s", e)
            raise

    async def stop(self) -> None:
        """Stop the health server."""
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            logger.info("Health server stopped")
