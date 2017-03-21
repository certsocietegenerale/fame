***
API
***

The API is using the same endpoints as the web application.

Authentication
==============

In order to authenticate, you should add your API key to the ``X-API-KEY`` header. This is needed for all requests made through the API.

Error Codes
===========

The API can return the following HTTP codes:

* ``302``: this means that you are not properly authenticated.
* ``403``: this means that your permissions are not sufficient.
* ``404``: this means that you tried to access an object that could not be found.

Reference
=========

.. qrefflask:: webserver:app
   :undoc-static:

.. autoflask:: webserver:app
    :undoc-static:
