import logging
import multiprocessing
import os
import signal
import ssl
import sys
import time

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
        self.worker_processes = []

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

        worker_process = multiprocessing.Process(name="worker-0", target=worker.start)
        worker_process.start()
        self.worker_processes.append(worker_process)

        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

        self.alive = True
        while self.alive:
            time.sleep(1)

    def stop(self):
        for index, worker_process in enumerate(self.worker_processes):
            logger.info("Terminating worker process %d (PID: %d)", index, worker_process.pid)
            worker_process.terminate()
        self.alive = False

    def handle_signal(self, signo, _stack_frame):
        logger.debug("Received signal %d", signo)
        self.stop()

def make_server(*args, **kwargs):
    return WSGIServer(*args, **kwargs)
