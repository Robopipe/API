import asyncio
import json
import os
import socket
from functools import lru_cache

import anyio.to_thread
from zeroconf import ServiceInfo, Zeroconf

from .log import logger
from . import __version__

MDNS_SERVICE_TYPE = "_robopipe._tcp.local."
DISCOVERY_MAGIC = b"ROBOPIPE_DISCOVER"
DEFAULT_API_PORT = 8080
DEFAULT_UDP_PORT = 5685


def get_local_ips() -> list[str]:
    """Resolve non-loopback IPv4 addresses of this machine."""
    try:
        import ifaddr

        ips = []
        for adapter in ifaddr.get_adapters():
            for ip in adapter.ips:
                if isinstance(ip.ip, str) and ip.ip != "127.0.0.1":
                    ips.append(ip.ip)
        if ips:
            return ips
    except ImportError:
        pass

    # Fallback: connect a UDP socket to determine the primary outbound IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and ip != "127.0.0.1":
            return [ip]
    except OSError:
        pass

    return []


def get_api_info(port: int) -> dict:
    """Build the discovery response payload."""
    ips = get_local_ips()
    return {
        "name": "Robopipe API",
        "version": __version__,
        "host": ips[0] if ips else socket.gethostname(),
        "port": port,
        "hostname": os.getenv("HOSTNAME", ""),
    }


class MDNSService:
    def __init__(self, port: int, hostname: str | None = None):
        self._port = port
        self._hostname = hostname
        self._zeroconf: Zeroconf | None = None
        self._service_info: ServiceInfo | None = None

    async def start(self) -> None:
        ips = get_local_ips()
        if not ips:
            logger.warning("mDNS: no network interfaces found, skipping registration")
            return

        name_suffix = f" ({self._hostname})" if self._hostname else ""
        service_name = f"Robopipe API{name_suffix}.{MDNS_SERVICE_TYPE}"

        self._service_info = ServiceInfo(
            type_=MDNS_SERVICE_TYPE,
            name=service_name,
            addresses=[socket.inet_aton(ip) for ip in ips],
            port=self._port,
            properties={
                "version": __version__,
                "path": "/",
                "hostname": self._hostname or "",
            },
            server=f"{self._hostname}.local." if self._hostname else None,
        )

        self._zeroconf = Zeroconf()
        await anyio.to_thread.run_sync(
            lambda: self._zeroconf.register_service(self._service_info)
        )
        logger.info(f"mDNS: registered {service_name} on port {self._port}")

    async def stop(self) -> None:
        if self._zeroconf and self._service_info:
            await anyio.to_thread.run_sync(
                lambda: self._zeroconf.unregister_service(self._service_info)
            )
            await anyio.to_thread.run_sync(self._zeroconf.close)
            logger.info("mDNS: unregistered service")


class _DiscoveryProtocol(asyncio.DatagramProtocol):
    def __init__(self, api_port: int):
        self._api_port = api_port
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self._transport = transport

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        if data.strip() == DISCOVERY_MAGIC:
            response = json.dumps(get_api_info(self._api_port)).encode("utf-8")
            self._transport.sendto(response, addr)


class UDPDiscoveryService:
    def __init__(self, api_port: int, udp_port: int = DEFAULT_UDP_PORT):
        self._api_port = api_port
        self._udp_port = udp_port

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: _DiscoveryProtocol(self._api_port),
            local_addr=("0.0.0.0", self._udp_port),
            family=socket.AF_INET,
        )

        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        logger.info(f"UDP discovery: listening on port {self._udp_port}")
        try:
            while True:
                await anyio.sleep(1)
        finally:
            transport.close()
            logger.info("UDP discovery: stopped")


class DiscoveryManager:
    def __init__(
        self,
        api_port: int,
        mdns_enabled: bool = True,
        udp_enabled: bool = True,
        udp_port: int = DEFAULT_UDP_PORT,
        hostname: str | None = None,
    ):
        self._mdns: MDNSService | None = None
        self._udp: UDPDiscoveryService | None = None

        if mdns_enabled:
            self._mdns = MDNSService(port=api_port, hostname=hostname)
        if udp_enabled:
            self._udp = UDPDiscoveryService(api_port=api_port, udp_port=udp_port)

    async def start(self) -> None:
        if self._mdns:
            try:
                await self._mdns.start()
            except Exception as e:
                logger.warning(f"mDNS registration failed: {e}")

    async def run_udp(self) -> None:
        if self._udp:
            try:
                await self._udp.run()
            except Exception as e:
                logger.warning(f"UDP discovery failed: {e}")

    async def stop(self) -> None:
        if self._mdns:
            try:
                await self._mdns.stop()
            except Exception as e:
                logger.warning(f"mDNS unregistration failed: {e}")


@lru_cache(maxsize=1)
def _env_bool(key: str, default: str = "true") -> bool:
    return os.getenv(key, default).lower() in ("true", "1", "yes")


def discovery_manager_factory() -> DiscoveryManager:
    api_port = int(os.getenv("PORT") or str(DEFAULT_API_PORT))
    hostname = os.getenv("HOSTNAME")

    mdns_enabled = _env_bool("DISCOVERY_MDNS_ENABLED")
    udp_enabled = _env_bool("DISCOVERY_UDP_ENABLED")
    udp_port = int(os.getenv("DISCOVERY_UDP_PORT") or str(DEFAULT_UDP_PORT))

    return DiscoveryManager(
        api_port=api_port,
        mdns_enabled=mdns_enabled,
        udp_enabled=udp_enabled,
        udp_port=udp_port,
        hostname=hostname,
    )
