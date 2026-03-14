import uuid
from aiortc import RTCPeerConnection
from functools import lru_cache


class WebRTCManager:
    def __init__(self):
        self.pcs: set[RTCPeerConnection] = set()
        self._sessions: dict[str, RTCPeerConnection] = {}

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
