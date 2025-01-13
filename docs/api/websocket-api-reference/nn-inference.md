# NN Inference

## Running inference

The neural network starts at the point it is uploaded to the camera. The output from the model can be read by subscribing to a websocket endpoint `ws://host:port/cameras/{mxid}/sensors/{sensor_name}/nn`. The outputted data will be a json in the format:

```json
{
    "detections": ...
}
```

where detections will contain whetever you is your model's output.
