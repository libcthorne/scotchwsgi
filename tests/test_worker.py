import multiprocessing
import os
import socket
import time
import unittest

import psutil

from scotchwsgi.worker import WSGIWorker

TEST_HOST = 'localhost'
TEST_PORT = 9000

def open_test_socket():
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((TEST_HOST, TEST_PORT))
    sock.listen()
    return sock

def dummy_app(environ, start_response):
    start_response('200 OK', [])
    return []

def start_worker(sock, worker_pid):
    worker = WSGIWorker(
        dummy_app,
        sock,
        TEST_HOST,
        os.getpid(),
    )

    worker_process = multiprocessing.Process(target=worker.start)
    worker_process.start()
    worker_pid.value = worker_process.pid
    worker_process.join()

class TestParentWorkerBinding(unittest.TestCase):
    def setUp(self):
        self.sock = open_test_socket()

        self.worker_pid = multiprocessing.Value('i')

        self.parent_process = multiprocessing.Process(
            target=start_worker,
            args=(self.sock, self.worker_pid)
        )
        self.parent_process.start()

        while self.worker_pid.value == 0 and self.parent_process.is_alive():
            # wait for worker process to be started
            time.sleep(0.1)

    def tearDown(self):
        if self.parent_process.is_alive():
            self.parent_process.terminate()
        self.sock.close()

    def test_worker_dies_when_parent_dies(self):
        self.assertTrue(psutil.pid_exists(self.worker_pid.value))
        self.parent_process.terminate()
        time.sleep(1)
        self.assertFalse(psutil.pid_exists(self.worker_pid.value))
