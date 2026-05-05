from aiortc import RTCPeerConnection, RTCRtpSender, RTCSessionDescription
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
    params = await req.json()
    rtc_offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    pc = RTCPeerConnection()
    webrtc_manager.add_pc(pc)
    sender = pc.addTrack(video_relay.subscribe(video_track, buffered=False))

    # The track yields pre-encoded H.264 av.Packets, so the negotiated codec
    # must be H.264. Without this, aiortc's answer picks VP8 (the default
    # first entry) and the browser tries to decode H.264 bitstream with a
    # VP8 decoder — webrtc-internals shows keyFramesDecoded climbing while
    # framesDecoded stays at 0 (every "frame" fails to decode).
    h264_codecs = [
        c
        for c in RTCRtpSender.getCapabilities("video").codecs
        if c.mimeType.lower() == "video/h264"
    ]
    for transceiver in pc.getTransceivers():
        if transceiver.sender is sender:
            transceiver.setCodecPreferences(h264_codecs)
            break

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
