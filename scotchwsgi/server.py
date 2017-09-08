import logging
import multiprocessing
import os
import ssl

from gevent import socket

from scotchwsgi.worker import WSGIWorker

logger = logging.getLogger(__name__)

class WSGIServer(object):
    def __init__(self, host, port, application, ssl_config=None, backlog=None):
        self.host = host
        self.port = port
        self.application = application
        self.ssl_config = ssl_config
        self.backlog = backlog

    def start(self):
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        if self.ssl_config:
            logger.info("Using SSL")
            sock = ssl.wrap_socket(
                sock,
                server_side=True,
                **self.ssl_config,
            )

        if self.backlog:
            sock.listen(self.backlog)
        else:
            sock.listen()

        logger.info("Listening on %s:%d", self.host, self.port)

        worker = WSGIWorker(
            self.application,
            sock,
            self.host,
            self.port,
            os.getpid(),
        )

        worker_process = multiprocessing.Process(target=worker.start)
        worker_process.start()
        worker_process.join()

def make_server(*args, **kwargs):
    return WSGIServer(*args, **kwargs)
