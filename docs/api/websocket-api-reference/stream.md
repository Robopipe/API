# Video Stream

Each sensor provides its own video stream. If there are no subscribers, no data is streamed to prevent additional resource usage. The streams starts when the first subscriber connects to the websocket endpoint and ends when the last subscriber disconnects. Each stream is capable of handling multiple subscribers with some [caveats](stream.md#multiple-subscribers).

## Video

### Receiving segments

The data obtained via websockets is MP4 fragments encoded using H.264 codec. To start receiving data, simply open a websocket at `ws://host:port/camera/MXID/streams/SENSOR_NAME/video`.

### Playing the video

The easiest way to play the video from the stream, is to use our embedded player right here. You are free to edit the source code to modify it to your needs.

{% embed url="https://codepen.io/robopipe/pen/YPKLyRG" %}

## Multiple subscribers

Streaming starts when the first subscriber connects to the websocket endpoint. The video encoding process also starts at this stage. This means that the first subscriber will always receive frames with   PTS[^1] starting at 0, however, this is different for each next subscriber.

When a subsequent subscriber connects to an already running stream, they will first receive an initialization segment, that is needed in order to correctly play the video. This segment is same for **all** subscribers connected to the same stream. The PTS contained in the received frames however, will not start at 0, but rather at some point X. In order to correctly play the video, the player must correctly decode the PTS from the first received frame and then offset the playback time accordingly.

[^1]: PTS stands for [presentation timestamp](https://en.wikipedia.org/wiki/Presentation_timestamp)
