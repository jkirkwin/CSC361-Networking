from socket import *
from unittest import TestCase

from a3.RDP_Protocol import *

LOOPBACK = '127.0.0.1'
TEST_TIMEOUT = 5


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


class ProtocolTest(TestCase):
    def setUp(self) -> None:
        pass

    def tearDown(self) -> None:
        pass

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
        with socket(AF_INET, SOCK_DGRAM) as sock:
            adr = (LOOPBACK, 56556)
            sock.bind(adr)

            seq = 10
            ack = 20
            message = create_ack_message(seq, ack)
            bin_message = message_to_bytes(message)

            sock.settimeout(TEST_TIMEOUT)
            sock.sendto(bin_message, adr)
            (result, _) = sock.recvfrom(1024)
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