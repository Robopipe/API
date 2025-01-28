# NN Inference

## Running inference

The neural network starts at the point it is uploaded to the camera. The output from the model can be read by subscribing to a websocket endpoint `ws://host:port/cameras/{mxid}/streams/{sensor_name}/nn`. The outputted data will be a json in the format:

```json
{
    "detections": ...
}
```

where detections will contain whetever you is your model's output.

## Output format

The data format received from the websocket endpoint depends on the type of neural network you have running on the camera.

### Generic neural network

In case you used a generic neural network, the output data will be a one dimensional array containing raw data from the last layer of the neural network.

```json
{
    "detections": [
        0.3,
        0.02,
        0.05,
        ...
    ]
}
```

### YOLO & MobilenetSSD

In case you have chosen either a YOLO or MobilenetSSD model, the output format will be an array containing detection objects. Each detection object contains:

* label - number indicating the label it detected
* confidence - float in the range \[0, 1] indicating the confidence level of the detection
* coords - four element tuple, containing the coordinates of the detection in the image \[x\_min, y\_min, x\_max, y\_max]

```json
{
    "detections": [
        {"label": 0, "confidence": 0.765, "coords": [0.5, 0.1, 0.6, 0.23]},
        ...
    ]
}
```

#### Depth

In case a depth stream is active and running at the same time a neural network is deployed, each detection object will also contain information regarding its depth position.
