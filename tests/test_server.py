import unittest
from unittest.mock import Mock, patch

from scotchwsgi.server import make_server

TEST_HOST = "localhost"
TEST_PORT = 0
NUM_WORKERS = 10

class BaseServerTestCase(unittest.TestCase):
    def setUp(self):
        def get_mock_process(*args, **kwargs):
            return Mock(pid=0)

        self.mock_process = patch(
            'scotchwsgi.server.multiprocessing.Process',
            side_effect=get_mock_process
        )

        self.mock_socket_instance = Mock(getsockname=lambda: (TEST_HOST, TEST_PORT))
        self.mock_socket = patch(
            'scotchwsgi.server.socket.socket',
            return_value=self.mock_socket_instance,
        )

        self.mock_process.start()
        self.mock_socket.start()

        self.mock_app = Mock()

    def tearDown(self):
        self.mock_process.stop()
        self.mock_socket.stop()

class TestServerWorkers(BaseServerTestCase):
    def test_workers_started(self):
        server = make_server(TEST_HOST, TEST_PORT, self.mock_app, num_workers=NUM_WORKERS)
        server.start(blocking=False)

        self.assertEqual(len(server.worker_processes), NUM_WORKERS)
        for worker_process in server.worker_processes:
            worker_process.start.assert_called_once()

    def test_workers_stopped_on_server_stop(self):
        server = make_server(TEST_HOST, TEST_PORT, self.mock_app, num_workers=NUM_WORKERS)
        server.start(blocking=False)
        worker_processes = server.worker_processes.copy()
        server.stop()

        for worker_process in worker_processes:
            worker_process.terminate.assert_called_once()

class TestServerSignalHandling(BaseServerTestCase):
    def test_handle_signal_stops_server(self):
        server = make_server(TEST_HOST, TEST_PORT, self.mock_app, num_workers=NUM_WORKERS)
        server.start(blocking=False)
        self.assertEqual(server.alive, True)
        server.handle_signal(0, 0)
        self.assertEqual(server.alive, False)

class TestServerSocketCreation(BaseServerTestCase):
    def test_no_backlog(self):
        server = make_server(TEST_HOST, TEST_PORT, self.mock_app, num_workers=NUM_WORKERS)
        server.start(blocking=False)

        self.mock_socket_instance.listen.assert_called_with()

        server.stop()

    def test_backlog(self):
        server = make_server(TEST_HOST, TEST_PORT, self.mock_app, backlog=100, num_workers=NUM_WORKERS)
        server.start(blocking=False)

        self.mock_socket_instance.listen.assert_called_with(100)

        server.stop()
