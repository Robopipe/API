from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi import Request

from ..common import VideoRelayDep, VideoTrackDep, WebRTCManagerDep
from . import stream_router


@stream_router.post("/video")
async def stream_video_offer(
    req: Request,
    video_track: VideoTrackDep,
    video_relay: VideoRelayDep,
    webrtc_manager: WebRTCManagerDep,
):
    # Close any prior peer connections before accepting a new one. The
    # OAK + edge host can't sustain two concurrent H.264 encoders feeding
    # from the same source — opening the dashboard alongside the main
    # viewer would put two PCs on the relay, saturate CPU, and leave the
    # stream degraded even after one tab is closed. Enforcing one PC at
    # a time means the latest offer wins; the previous viewer disconnects.
    await webrtc_manager.remove_all_pcs()

    params = await req.json()
    rtc_offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    pc = RTCPeerConnection()
    webrtc_manager.add_pc(pc)
    pc.addTrack(video_relay.subscribe(video_track, buffered=False))
    await pc.setRemoteDescription(rtc_offer)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        if pc.iceConnectionState in ("failed", "disconnected", "closed"):
            await webrtc_manager.remove_pc(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "disconnected", "closed"):
            await webrtc_manager.remove_pc(pc)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
