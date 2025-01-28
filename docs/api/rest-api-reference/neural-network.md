# Neural Network

Each camera is capable of running a [neural network](https://en.wikipedia.org/wiki/Neural_network_\(machine_learning\)) and feeding it data from a selected stream. Our API can currently handle only models in the MyriadX blob format. To read more about this format and how to convert your models to MyriadX blob format, please refer to [Luxonis conversion guide](https://docs.luxonis.com/software/ai-inference/conversion).

{% hint style="warning" %}
Deploying an AI model on the camera takes some time (usually \~20s, but may take up to a minute), during this time, the camera will be inaccessible via the API, since it needs to restart in order to deploy the model. All running streams from the particular camera will be paused and will resume when the camera is up again.
{% endhint %}

## API Reference

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/nn" method="post" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}

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

{% swagger src="../../.gitbook/assets/oas.yml" path="/cameras/{mxid}/streams/{stream_name}/nn" method="delete" %}
[oas.yml](../../.gitbook/assets/oas.yml)
{% endswagger %}
