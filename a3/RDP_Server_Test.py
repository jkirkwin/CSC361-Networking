import os
from socket import *
from unittest import TestCase

from a3.RDP_Protocol import *
from a3.RDP_Server import Server

LOOPBACK = "127.0.0.1"
SOCKET_ADDRESS = (LOOPBACK, 0)
TIMEOUT = 5


class ServerTest(TestCase):

    def setUp(self) -> None:
        self.server = Server(SOCKET_ADDRESS)

    def tearDown(self) -> None:
        try:
            if self.server.sock:
                self.server.sock.close()
        except error:
            pass

    def test_get_data_from_file(self):
        inputs = ["hello".encode(),
                  "hello".encode() * 1000]  # 5000 bytes

        for input in inputs:
            timestamp = str(time.time())
            filename = timestamp + ".bin"
            try:
                file = open(filename, 'wb+', buffering=0)
                file.write(input)
                file.close()

                result = Server._get_data_from_file(filename)

                self.assertEqual(b"".join(result), input)

                for chunk in result:
                    self.assertLessEqual(len(chunk), MAX_PAYLOAD_SIZE)
            finally:
                if os.path.exists(filename):
                    os.remove(filename)

    def test_receive_connection(self):  # todo
        self.fail("Unimplemented")

    def test_close_connection(self):  # todo
        self.fail("Unimplemented")