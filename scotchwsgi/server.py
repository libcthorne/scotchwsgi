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
    def __init__(self, host, port, application, ssl_config=None, backlog=None, num_workers=1):
        self.host = host
        self.port = port
        self.application = application
        self.ssl_config = ssl_config
        self.backlog = backlog
        self.num_workers = num_workers
        self.worker_processes = []

    def start(self, blocking=True):
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        if self.ssl_config:
            logger.info("Using SSL")
            self.sock = ssl.wrap_socket(
                self.sock,
                server_side=True,
                **self.ssl_config,
            )

        if self.backlog:
            self.sock.listen(self.backlog)
        else:
            self.sock.listen()

        logger.info("Listening on %s:%d", self.host, self.port)

        worker = WSGIWorker(
            self.application,
            self.sock,
            self.host,
            os.getpid(),
        )

        for worker_index in range(self.num_workers):
            worker_process = multiprocessing.Process(
                name="worker-%d"%worker_index,
                target=worker.start
            )
            worker_process.start()
            self.worker_processes.append(worker_process)

        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)

        self.alive = True
        if blocking:
            while self.alive:
                time.sleep(1)

    def stop(self):
        for index, worker_process in enumerate(self.worker_processes):
            logger.info("Terminating worker process %d (PID: %d)", index, worker_process.pid)
            worker_process.terminate()
        self.worker_processes = []
        self.alive = False
        self.sock.close()

    def handle_signal(self, signo, _stack_frame):
        logger.debug("Received signal %d", signo)
        self.stop()

def make_server(*args, **kwargs):
    return WSGIServer(*args, **kwargs)
