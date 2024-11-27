# Neural Network

Each camera is capable of running a [neural network](https://en.wikipedia.org/wiki/Neural_network_\(machine_learning\)) and feeding it data from a selected sensor. Our API can currently handle only models in the MyriadX blob format. To read more about this format and how to convert your models to MyriadX blob format, please refer to [Luxonis conversion guide](https://docs.luxonis.com/software/ai-inference/conversion).

{% hint style="info" %}
We currently support connecting a neural network to **one** sensor, without the ability to mux multiple sensors into one. This means some Luxonis features, such as [stereo depth](https://docs.luxonis.com/software/depthai-components/nodes/stereo_depth) are not available at this time.
{% endhint %}

{% hint style="warning" %}
Deploying an AI model on the camera takes some time (usually \~20s, but may take up to a minute), during this time, the camera will be inaccessible via the API, since it needs to restart in order to deploy the model. All running streams from the particular camera will be paused and will resume when the camera is up again.
{% endhint %}

## API Reference

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/sensors/{sensor_name}/nn" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

## Running inference

The neural network starts at the point it is uploaded to the camera. The output from the model can be read by subscribing to a websocket endpoint `ws://host:port/cameras/{mxid}/sensors/{sensor_name}/nn`. The outputted data will be a json in the format:

```json
{
    "detections": ...
}
```

where detections will contain whetever you is your model's output.
