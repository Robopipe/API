from aiortc import RTCPeerConnection

from functools import lru_cache


class WebRTCManager:
    def __init__(self):
        self.pcs = set()

    def add_pc(self, pc: RTCPeerConnection):
        self.pcs.add(pc)

    async def remove_pc(self, pc: RTCPeerConnection):
        try:
            await pc.close()
        except Exception:
            pass
        self.pcs.discard(pc)

    async def remove_all_pcs(self):
        pcs = self.pcs.copy()
        self.pcs.clear()
        for pc in pcs:
            try:
                await pc.close()
            except Exception:
                pass


@lru_cache(maxsize=1)
def webrtc_manager_factory() -> WebRTCManager:
    return WebRTCManager()
