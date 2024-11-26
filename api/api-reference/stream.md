---
description: In default configuration, each sensor provides a video stream via websockets.
---

# Stream

## Video

### Receiving segments

The data obtained via websockets is MP4 fragments encoded using H.264 codec. To start receiving data, simply open a websocket at `ws://host:port/camera/MXID/sensors/SENSOR_NAME/stream`.

### Playing the video

The easiest way to play the video from the stream, is to use our embedded player right here.



{% embed url="https://codepen.io/adamberkes/pen/MYggMWX" fullWidth="false" %}
