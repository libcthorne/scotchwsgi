import multiprocessing
import os
import signal
import time
import unittest
from unittest.mock import Mock, patch

import psutil

from scotchwsgi.worker import WSGIWorker

TEST_HOST = 'localhost'
TEST_PORT = 0

def start_worker_process(app, worker_pid):
    mock_sock = Mock(getsockname=lambda: (TEST_HOST, TEST_PORT))
    worker = WSGIWorker(app, mock_sock, TEST_HOST, os.getpid())

    def start_worker():
        mock_gevent = patch('scotchwsgi.worker.gevent')
        mock_gevent.start()
        worker.start()
        mock_gevent.stop()

    worker_process = multiprocessing.Process(target=start_worker)
    worker_process.start()

    worker_pid.value = worker_process.pid

    worker_process.join()

class TestWorkerParentBinding(unittest.TestCase):
    """A worker should die when its parent process is killed"""

    def setUp(self):
        self.worker_pid = multiprocessing.Value('i')

        mock_app = Mock()

        self.parent_process = multiprocessing.Process(
            target=start_worker_process,
            args=(mock_app, self.worker_pid)
        )
        self.parent_process.start()

        while not self.parent_process.is_alive():
            # wait for parent process to be started
            time.sleep(0.1)

        while self.worker_pid.value == 0 and self.parent_process.is_alive():
            # wait for worker process to be started
            time.sleep(0.1)

    def tearDown(self):
        if self.parent_process.is_alive():
            os.kill(self.parent_process.pid, signal.SIGKILL)

    def test_worker_dies_when_parent_killed(self):
        self.assertTrue(psutil.pid_exists(self.worker_pid.value))
        os.kill(self.parent_process.pid, signal.SIGKILL)
        time.sleep(2)
        self.assertFalse(psutil.pid_exists(self.worker_pid.value))
