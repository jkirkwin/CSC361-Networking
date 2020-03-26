import os
import time
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

    def test_try_receive_ack(self):
        with socket(AF_INET, SOCK_DGRAM) as client_socket:
            client_adr = (LOOPBACK, 55556)
            client_socket.bind(client_adr)

            self.server.conn = Connection(client_adr, 10)
            self.server._create_and_bind_socket()

            msg = create_app_message(self.server.conn.seq_num,
                                     self.server.conn.last_index_received,
                                     b"hello")

            # Test that a valid ACK is recognized and returned
            ack = create_ack_message(msg.ack_no, msg.seq_no)
            assert is_ack_for_message(msg, ack), "Programming error."

            ack_bytes = message_to_bytes(ack)
            client_socket.sendto(ack_bytes, self.server.adr)

            result = self.server._try_receive_ack(msg, TIMEOUT)

            self.assertTrue(result)
            self.assertEqual(ack, result)

            # Test that a receipt of a bad ack yields None after a timeout.
            bad_ack = create_ack_message(ack.seq_no, ack.ack_no + 1)
            assert not is_ack_for_message(msg, bad_ack), "Programming error."

            bad_ack_bytes = message_to_bytes(bad_ack)
            client_socket.sendto(bad_ack_bytes, self.server.adr)

            result = self.server._try_receive_ack(msg, TIMEOUT)

            self.assertIsNone(result)

    def test_send_until_ack_in(self):
        self.fail("Unimplemented") # todo

    def test_receive_connection(self):  # todo
        self.fail("Unimplemented")

    def test_close_connection(self):  # todo
        self.fail("Unimplemented")