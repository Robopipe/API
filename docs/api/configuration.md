---
description: Configure the API
---

# Configuration

All configuration is done via a single `.env` file located in the root directory of the project. You can find an example in `.env.example`. To modify these values simply copy the file into `.env` and change the desired keys.

{% hint style="info" %}
Please note that changing the **CORS\_ORIGINS** to a value that does _not_ include the URL of these docs will render the _Try it_ and _stream_ _player_ functionality in these do&#x63;_&#x73;_ unusable.
{% endhint %}

## Configuration values

* **HOST** - domain name or IP address of the host that serves the API
  * _DEFAULT_ - 0.0.0.0
* **PORT** - Por on which the API is running
  * DEFAULT - 8000
* **CORS\_ORIGINS** - comma separated list of allowed origins for the CORS preflight requests
  * DEFAULT - \*

