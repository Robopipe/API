# Neural Network

Each camera is capable of running a [neural network](https://en.wikipedia.org/wiki/Neural_network_\(machine_learning\)) and feeding it data from a selected stream. Our API can currently handle only models in the MyriadX blob format. To read more about this format and how to convert your models to MyriadX blob format, please refer to [Luxonis conversion guide](https://docs.luxonis.com/software/ai-inference/conversion).

{% hint style="warning" %}
Deploying an AI model on the camera takes some time (usually \~20s, but may take up to a minute), during this time, the camera will be inaccessible via the API, since it needs to restart in order to deploy the model. All running streams from the particular camera will be paused and will resume when the camera is up again.
{% endhint %}

## API Reference

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/nn" method="post" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}

### NNConfig Description

The deploy neural network endpoint accepts form-data body. This body shall contain two fields - _model_, which is a binary file containing the neural network in the MyriadX blob format and _nn\_config_, stringified json containing the neural network configuration. The _nn\_config_ format is described below



| NNConfig Field                                | Description                                                                                                                                                                                              |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| <kbd>type</kbd> (_required_)                  | <p>Type of the neural network being deployed.<br><br>Possible values are:</p><ul><li><code>Generic</code></li><li><code>YOLO</code></li><li><code>MobileNet</code></li></ul><p>Type: <kbd>enum</kbd></p> |
| <kbd>num\_inference\_threads</kbd> (optional) | <p>Number of CPU to run inference on.</p><p></p><p>Type: <kbd>number</kbd><br>Default: <kbd>2</kbd></p>                                                                                                  |
| <kbd>nn\_config</kbd> (_optional_)            | <p>Type-specific configuration for the deployed model.<br><br>Type: <kbd>NNYoloConfig | NNMobileNetConfig</kbd></p>                                                                                      |

#### NNYoloConfig

| NNYoloConfig Field                       | Description |
| ---------------------------------------- | ----------- |
| <kbd>anchor\_masks</kbd> (_optional_)    |             |
| <kbd>anchors</kbd> (_optional_)          |             |
| <kbd>coordinate\_size</kbd> (_optional_) |             |
| <kbd>iou\_threshold</kbd> (_optional_)   |             |
| <kbd>num\_classes</kbd> (_optional_)     |             |

#### NNMobileNetConfig

| NNMobileNetConfig Field                       | Description |
| --------------------------------------------- | ----------- |
| <kbd>confidence\_threshold</kbd> (_optional_) |             |

{% openapi-operation spec="robopipe-api" path="/cameras/{mxid}/streams/{stream_name}/nn" method="delete" %}
[OpenAPI robopipe-api](https://gitbook-x-prod-openapi.4401d86825a13bf607936cc3a9f3897a.r2.cloudflarestorage.com/raw/61c09c137433794c1f1727040fd632d7a56c4ad805d94fa4404486ea4c326b25.yaml?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Content-Sha256=UNSIGNED-PAYLOAD&X-Amz-Credential=dce48141f43c0191a2ad043a6888781c%2F20250718%2Fauto%2Fs3%2Faws4_request&X-Amz-Date=20250718T112051Z&X-Amz-Expires=172800&X-Amz-Signature=4d21029758779c17d573643c236e9f9069a5ee15193b1272c66a3df1100916b6&X-Amz-SignedHeaders=host&x-amz-checksum-mode=ENABLED&x-id=GetObject)
{% endopenapi-operation %}
