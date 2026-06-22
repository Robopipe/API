import uuid
from aiortc import RTCPeerConnection, RTCDataChannel
from functools import lru_cache


class WebRTCManager:
    def __init__(self):
        self.pcs: set[RTCPeerConnection] = set()
        self._sessions: dict[str, RTCPeerConnection] = {}
        self._event_channels: dict[tuple[str, str], set[RTCDataChannel]] = {}
        self._ended_streams: set[tuple[str, str]] = set()

    def add_pc(self, pc: RTCPeerConnection) -> str:
        session_id = str(uuid.uuid4())
        self.pcs.add(pc)
        self._sessions[session_id] = pc
        return session_id

    def get_pc(self, session_id: str) -> RTCPeerConnection | None:
        return self._sessions.get(session_id)

    async def remove_pc(self, pc: RTCPeerConnection):
        try:
            await pc.close()
        except Exception:
            pass
        self.pcs.discard(pc)
        stale = [sid for sid, p in self._sessions.items() if p is pc]
        for sid in stale:
            del self._sessions[sid]

    def register_event_channel(self, mxid: str, sensor_name: str, channel: RTCDataChannel) -> None:
        key = (mxid, sensor_name)
        if key not in self._event_channels:
            self._event_channels[key] = set()
        self._event_channels[key].add(channel)

    def unregister_event_channel(self, mxid: str, sensor_name: str, channel: RTCDataChannel) -> None:
        key = (mxid, sensor_name)
        channels = self._event_channels.get(key)
        if channels:
            channels.discard(channel)
            if not channels:
                del self._event_channels[key]

    def get_event_channels(self, mxid: str, sensor_name: str) -> set[RTCDataChannel]:
        return set(self._event_channels.get((mxid, sensor_name), set()))

    def mark_stream_ended(self, mxid: str, sensor_name: str) -> None:
        self._ended_streams.add((mxid, sensor_name))

    def clear_stream_ended(self, mxid: str, sensor_name: str) -> None:
        self._ended_streams.discard((mxid, sensor_name))

    def is_stream_ended(self, mxid: str, sensor_name: str) -> bool:
        return (mxid, sensor_name) in self._ended_streams

    async def remove_all_pcs(self):
        pcs = self.pcs.copy()
        self.pcs.clear()
        self._sessions.clear()
        for pc in pcs:
            try:
                await pc.close()
            except Exception:
                pass


@lru_cache(maxsize=1)
def webrtc_manager_factory() -> WebRTCManager:
    return WebRTCManager()
