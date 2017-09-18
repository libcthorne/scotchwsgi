import unittest
from unittest.mock import Mock, patch

from scotchwsgi.server import make_server

TEST_HOST = "localhost"
TEST_PORT = 0

class TestServerWorkers(unittest.TestCase):
    WORKER_COUNT = 10

    @patch('scotchwsgi.server.multiprocessing.Process')
    def test_workers_started(self, mock_process):
        mock_process.side_effect = Mock

        mock_app = Mock()
        server = make_server(TEST_HOST, TEST_PORT, mock_app, num_workers=self.WORKER_COUNT)
        server.start(blocking=False)

        self.assertEqual(len(server.worker_processes), self.WORKER_COUNT)
        for worker_process in server.worker_processes:
            worker_process.start.assert_called_once()

    @patch('scotchwsgi.server.multiprocessing.Process')
    def test_workers_stopped_on_server_stop(self, mock_process):
        def get_mock_process(*args, **kwargs):
            return Mock(pid=0)

        mock_process.side_effect = get_mock_process

        mock_app = Mock()
        server = make_server(TEST_HOST, TEST_PORT, mock_app, num_workers=self.WORKER_COUNT)
        server.start(blocking=False)
        worker_processes = server.worker_processes
        server.stop()

        self.assertEqual(len(worker_processes), self.WORKER_COUNT)
        for worker_process in worker_processes:
            worker_process.terminate.assert_called_once()

class TestServerSignalHandling(unittest.TestCase):
    def test_handle_signal_stops_server(self):
        mock_app = Mock()
        server = make_server(TEST_HOST, TEST_PORT, mock_app, num_workers=2)
        server.start(blocking=False)
        self.assertEqual(server.alive, True)
        server.handle_signal(0, 0)
        self.assertEqual(server.alive, False)

class TestServerSocketCreation(unittest.TestCase):
    @patch('scotchwsgi.server.multiprocessing.Process')
    @patch('scotchwsgi.server.socket.socket')
    def test_no_backlog(self, mock_socket, mock_process):
        mock_socket_instance = Mock(getsockname=lambda: (TEST_HOST, TEST_PORT))
        mock_socket.return_value = mock_socket_instance

        mock_app = Mock()
        server = make_server(TEST_HOST, TEST_PORT, mock_app, num_workers=2)
        server.start(blocking=False)

        mock_socket_instance.listen.assert_called_with()

        server.stop()

    @patch('scotchwsgi.server.multiprocessing.Process')
    @patch('scotchwsgi.server.socket.socket')
    def test_backlog(self, mock_socket, mock_process):
        mock_socket_instance = Mock(getsockname=lambda: (TEST_HOST, TEST_PORT))
        mock_socket.return_value = mock_socket_instance

        mock_app = Mock()
        server = make_server(TEST_HOST, TEST_PORT, mock_app, backlog=100, num_workers=2)
        server.start(blocking=False)

        mock_socket_instance.listen.assert_called_with(100)

        server.stop()
