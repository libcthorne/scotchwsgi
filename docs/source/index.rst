ScotchWSGI - Yet Another Web Server
===================================

ScotchWSGI is a `WSGI-compliant <https://www.python.org/dev/peps/pep-3333/>`_ web server written in Python.
Driven by the `gevent <http://www.gevent.org/>`_ library, it is able to handle tens of thousands of open connections at once.
It currently implements the majority of `HTTP/1.1 <https://tools.ietf.org/html/rfc2616>`_ features, and work is underway to support `HTTP/2.0 <https://tools.ietf.org/html/rfc7540>`_.

*Note: This is primarily an educational side project undertaken to explore the specifications of the web and how modern web servers work. While ScotchWSGI aims to be stable, it should currently be viewed as experimental and should not be used in production.*

Installation
------------

The latest stable version of ScotchWSGI can be installed using pip:

.. code-block:: none

   pip install scotchwsgi

Alternatively, you can install from `source <https://github.com/libcthorne/scotchwsgi>`_ using `setup.py`:

.. code-block:: none

   python setup.py install

Usage
-----

A ScotchWSGI server can be started by simply passing in the name of a module that exposes an `app` object to the `scotchwsgi` command:

.. code-block:: none

   scotchwsgi app

Links
-----

* :ref:`modindex`
