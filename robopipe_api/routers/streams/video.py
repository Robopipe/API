import json

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

    # The track yields pre-encoded VP8 av.Packets, so the negotiated codec
    # must be VP8. aiortc's answer would otherwise pick whatever the
    # browser offered first (often H.264), and the browser would try to
    # decode VP8 bitstream with the wrong decoder — webrtc-internals
    # would show keyFramesDecoded climbing while framesDecoded stayed at 0.
    vp8_codecs = [
        c
        for c in RTCRtpSender.getCapabilities("video").codecs
        if c.mimeType.lower() == "video/vp8"
    ]
    for transceiver in pc.getTransceivers():
        if transceiver.sender is sender:
            transceiver.setCodecPreferences(vp8_codecs)
            break

    mxid = video_track.camera.mxid
    sensor_name = video_track.sensor_name
    event_channels: list = []

    @pc.on("datachannel")
    def on_datachannel(ch):
        if ch.label != "events":
            return
        event_channels.append(ch)
        webrtc_manager.register_event_channel(mxid, sensor_name, ch)

        @ch.on("close")
        def on_ch_close():
            webrtc_manager.unregister_event_channel(mxid, sensor_name, ch)

        if webrtc_manager.is_stream_ended(mxid, sensor_name) and ch.readyState == "open":
            ch.send(json.dumps({"event": "eof"}))

    async def _deregister_channels():
        for ch in list(event_channels):
            webrtc_manager.unregister_event_channel(mxid, sensor_name, ch)
        event_channels.clear()

    await pc.setRemoteDescription(rtc_offer)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        if pc.iceConnectionState in ("failed", "disconnected", "closed"):
            await _deregister_channels()
            await webrtc_manager.remove_pc(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        if pc.connectionState in ("failed", "disconnected", "closed"):
            await _deregister_channels()
            await webrtc_manager.remove_pc(pc)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
