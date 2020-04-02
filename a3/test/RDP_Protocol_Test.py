import os
import queue
import random
import threading
import unittest

from a3.src.RDP_Protocol import *

LOOPBACK_IP = '127.0.0.1'
TEST_PORT = 56565
LOOPBACK_ADR = (LOOPBACK_IP, TEST_PORT)

TEST_TIMEOUT = 5


def get_rand_seq_no():
    return random.randint(0, MAX_SEQ_NUMBER - 1)


def _get_msg_pair():
    """ Create a matching message and binary representation
    """

    packet_type = "SYN"
    seq_no = 100
    ack_no = 55
    payload_len = MAX_PAYLOAD_SIZE - 1
    payload = bytearray(payload_len)
    for i in range(payload_len):
        if i % 2 == 0:
            payload[i] = 255  # Alternate between 0x00 and 0xFF

    message = Message(packet_type, seq_no, ack_no, payload)

    # Manually create a binary representation of the message object
    binary_message = bytearray(HEADER_SIZE + payload_len)
    # First bit is ack flag. Remainder of first byte is packet type id.
    ack_flag = 1 << 7
    pt_id = PACKET_TYPES_IDS[packet_type]
    binary_message[0] = ack_flag | pt_id

    # Second byte is reserved. Third and fourth are seq and ack numbers.
    binary_message[2] = seq_no
    binary_message[3] = ack_no

    # Fifth and sixth bytes are payload length
    byte_mask = 0xFF
    len_lsb = payload_len & byte_mask
    len_msb = (payload_len >> 8) & byte_mask
    binary_message[4] = len_msb
    binary_message[5] = len_lsb

    # Remaining bytes are the payload
    binary_message[6:] = payload

    return message, binary_message


class ProtocolTest(unittest.TestCase):
    def setUp(self) -> None:
        self.loopback_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.loopback_sock.bind(LOOPBACK_ADR)

    def tearDown(self) -> None:
        self.loopback_sock.close()

    def test_message_to_from_bytes(self):
        # This is a sanity check
        msg = create_fin_message(10, 31)
        bin_msg = message_to_bytes(msg)
        converted_msg = message_from_bytes(bin_msg)
        self.assertEqual(msg, converted_msg)

    def test_message_to_bytes(self):
        message, binary_message = _get_msg_pair()
        self.assertEqual(binary_message, message_to_bytes(message))

    def test_bytes_to_message(self):
        message, binary_message = _get_msg_pair()
        self.assertEqual(message, message_from_bytes(binary_message))

    def test_send_message_via_socket_sanity_check(self):
        seq = 10
        ack = 20
        message = create_ack_message(seq, ack)
        bin_message = message_to_bytes(message)

        self.loopback_sock.settimeout(TEST_TIMEOUT)
        self.loopback_sock.sendto(bin_message, LOOPBACK_ADR)
        (result, _) = self.loopback_sock.recvfrom(len(bin_message))
        result_message = message_from_bytes(result)

        self.assertEqual(bin_message, result)
        self.assertEqual(message, result_message)

    def test_is_ack_for_message(self):
        out_seq_num = 12
        out_ack_num = 1  # Arbitrary, should not affect result
        message_out = create_app_message(out_seq_num, out_ack_num, b'test123')

        ack_seq_num = out_ack_num  # Should not affect result
        ack_ack_num = out_seq_num
        ack = create_ack_message(ack_seq_num, ack_ack_num)

        bad_ack = create_ack_message(ack_seq_num, ack_ack_num + 1)

        self.assertTrue(is_ack_for_message(message_out, ack))
        self.assertFalse(is_ack_for_message(message_out, bad_ack))

    def test_send_read_message(self):
        def get_rand_payload():
            size = random.randint(0, MAX_PAYLOAD_SIZE - 1)
            return os.urandom(size)

        message1 = create_syn_message(get_rand_seq_no(), get_rand_seq_no())
        message2 = create_app_message(get_rand_seq_no(),
                                      get_rand_seq_no(),
                                      get_rand_payload())

        send_message(self.loopback_sock, message1, LOOPBACK_ADR)
        send_message(self.loopback_sock, message2, LOOPBACK_ADR)

        result1 = try_read_message(self.loopback_sock, TEST_TIMEOUT)
        result2 = try_read_message(self.loopback_sock, TEST_TIMEOUT)

        self.assertEqual(message1, result1)
        self.assertEqual(message2, result2)

    def test_try_receive_ack(self):
        connection = Connection(LOOPBACK_ADR,
                                get_rand_seq_no(),
                                get_rand_seq_no())

        msg_out = create_app_message(connection.seq_num,
                                     connection.last_index_received,
                                     b"hello")

        # Test that a valid ACK is recognized and returned
        valid_ack = create_ack_message(get_rand_seq_no(), msg_out.seq_no)
        assert is_ack_for_message(msg_out, valid_ack), "Programming error."

        send_message(self.loopback_sock, valid_ack, LOOPBACK_ADR)
        result = try_receive_ack(msg_out, TEST_TIMEOUT, self.loopback_sock, LOOPBACK_ADR)
        self.assertTrue(result)
        self.assertEqual(valid_ack, result)

        # Test that a receipt of a bad ack yields None after a timeout.
        bad_ack_no = (msg_out.seq_no + 1) % MAX_SEQ_NUMBER
        invalid_ack = create_ack_message(get_rand_seq_no(), bad_ack_no)
        assert (not is_ack_for_message(msg_out, invalid_ack)), \
            "Programming error."

        send_message(self.loopback_sock, invalid_ack, LOOPBACK_ADR)
        result = try_receive_ack(msg_out,
                                 TEST_TIMEOUT,
                                 self.loopback_sock,
                                 LOOPBACK_ADR)
        self.assertIsNone(result)

    def test_await_ack(self):
        msg_out = create_syn_message(get_rand_seq_no(), get_rand_seq_no())

        non_ack = create_syn_message(get_rand_seq_no(), None)
        assert not is_ack_for_message(msg_out, non_ack), "Programming error."

        ack = create_ack_message(get_rand_seq_no(), msg_out.seq_no)
        assert is_ack_for_message(msg_out, ack), "Programming error."

        # Verify that non-ack messages are discarded
        send_message(self.loopback_sock, non_ack, LOOPBACK_ADR)
        send_message(self.loopback_sock, ack, LOOPBACK_ADR)

        result = await_ack(msg_out, self.loopback_sock, LOOPBACK_ADR)
        self.assertEqual(ack, result)

        # None should be returned if no ack is received before the timeout
        class Worker(threading.Thread):
            """ A worker thread that sleeps for a timeout and calls
            """
            def __init__(self, q, msg, sock, adr, wait_time):
                super().__init__()
                self.q = q
                self.msg = msg
                self.sock = sock
                self.adr = adr
                self.wait_time = wait_time

            def run(self):
                result = await_ack(self.msg,
                                   self.sock,
                                   self.adr,
                                   self.wait_time)
                q.put(result, block=False)

        send_message(self.loopback_sock, non_ack, LOOPBACK_ADR)

        q = queue.Queue()
        await_time = TEST_TIMEOUT / 10
        worker = Worker(q, msg_out, self.loopback_sock, LOOPBACK_ADR, await_time)
        worker.start()
        worker.join(TEST_TIMEOUT / 2)

        result = q.get(block=False)
        self.assertIsNone(result)


class ConnectionTest(unittest.TestCase):

    def setUp(self):
        self.remote_seq_seed = random.randint(0, MAX_SEQ_NUMBER - 1)
        self.local_seq_seed = random.randint(0, MAX_SEQ_NUMBER - 1)
        self.conn = Connection(LOOPBACK_ADR,
                               self.remote_seq_seed,
                               self.local_seq_seed)

    def test_increment_and_get_seq(self):
        result = self.conn.increment_and_get_seq()
        expected = (self.local_seq_seed + 1) % MAX_SEQ_NUMBER
        # Check that the correct result is returned and the connection state is
        # updated
        self.assertEqual(expected, result)
        self.assertEqual(expected, self.conn.seq_num)

        # Check that the ack number is unchanged
        self.assertEqual(self.remote_seq_seed, self.conn.last_index_received)

    def test_get_seq_and_increment(self):
        result = self.conn.get_seq_and_increment()
        expected = self.local_seq_seed
        # Check that the correct result is returned and the connection state is
        # updated
        self.assertEqual(expected, result)
        self.assertEqual((expected + 1) % MAX_SEQ_NUMBER, self.conn.seq_num)

        # Check that the ack number is unchanged
        self.assertEqual(self.remote_seq_seed, self.conn.last_index_received)

    def test_next_expected_index(self):
        expected = (self.remote_seq_seed + 1) % MAX_ACK_NUMBER
        for i in range(0, 10):
            self.assertEqual(expected, self.conn.next_expected_index())

        self.assertEqual(self.remote_seq_seed, self.conn.last_index_received)

    def test_increment_next_expected_index(self):
        for i in range(1, 10):
            expected = (self.remote_seq_seed + i) % MAX_ACK_NUMBER
            self.conn.increment_next_expected_index()
            result = self.conn.last_index_received

            self.assertEqual(expected, result)


if __name__ == '__main__':
    unittest.main()
