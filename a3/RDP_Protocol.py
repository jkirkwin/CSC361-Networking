"""
    Utilities and constants related to the RDP (Reliable HTTP Server over UDP
    Protocol) as defined in the assignment 3 specification and related
    documentation.
"""

DEFAULT_ACK_TIMEOUT_SECONDS = 2
DEFAULT_RETRY_THRESHOLD = 5

MAX_PACKET_SIZE = 1024
HEADER_SIZE = 6
MAX_PAYLOAD_SIZE = MAX_PACKET_SIZE - HEADER_SIZE

MAX_SEQ_NUMBER = 255
MAX_ACK_NUMBER = 255

# Ugly, but we need bidirectional mapping and this is unlikely to change.
PACKET_TYPES_IDS = {
    "ACK": 0,
    "SYN": 1,
    "FIN": 2,
    "APP": 3,
}
PACKET_IDS_TYPES = ["ACK", "SYN", "FIN", "APP"]


class Connection:
    def __init__(self, remote_adr, remote_seq_num, seq_num=0):
        self.remote_adr = remote_adr
        self.last_index_received = remote_seq_num
        self.seq_num = seq_num % MAX_SEQ_NUMBER

    def get_next_seq_and_increment(self):
        seq = self.seq_num
        self.seq_num = (seq + 1 % MAX_SEQ_NUMBER)
        return seq


class Message:
    """
        Represents an RDP message with header fields and a payload.
    """

    def __init__(self, packet_type, seq_no, ack_no, payload=bytearray()):
        """ Not for external use. Use factory methods to ensure consistency.
        """

        self.packet_type = packet_type  # String, key to types dict
        self.ack_no = ack_no
        self.seq_no = seq_no
        self.payload = payload

    def __eq__(self, other):
        return message_to_bytes(self) == message_to_bytes(other)

    def is_syn(self):
        return self.packet_type == "SYN"

    def is_fin(self):
        return self.packet_type == "FIN"

    def is_app(self):
        return self.packet_type == "APP"

    def is_ack(self):
        # Note that this may return true in addition to is_syn etc.
        return self.ack_no is not None

    def is_ack_only(self):
        return self.packet_type == "ACK"

    def get_payload_as_text(self):
        return self.payload.decode()


def create_syn_message(seq_no, ack_no=None):
    """ Utility to create an RDP SYN message
    """
    return Message("SYN", seq_no, ack_no)


def create_ack_message(seq_no, ack_no):
    """ Utility to create an RDP DATA message
    """
    return Message("ACK", seq_no, ack_no)


def create_app_message(seq_no, ack_no, data):
    """ Utility to create an RDP APP message
    """
    return Message("APP", seq_no, ack_no, data)


def create_fin_message(seq_no, ack_no):
    """ Utility to create an RDP FIN message
    """
    return Message("FIN", seq_no, ack_no)


def message_from_bytes(binary_message):
    """ Creates a message from the given bytearray representation.
    """
    # First byte holds ack bit and packet type
    ack_bit_mask = 0x80  # 1000 0000
    ack_bit = binary_message[0] & ack_bit_mask

    packet_type_id = binary_message[0] & (~ack_bit_mask)
    packet_type = PACKET_IDS_TYPES[packet_type_id]

    # Second byte is reserved

    # Third byte holds sequence number
    seq_no = binary_message[2]

    # Fourth byte holds ACK number
    ack_no = binary_message[3] if ack_bit else None

    # Fifth and sixth bytes hold payload length
    pl_msb = binary_message[4]
    pl_lsb = binary_message[5]
    payload_len = (pl_msb << 8) | pl_lsb

    # Remaining bytes are the payload
    payload = binary_message[HEADER_SIZE: payload_len + HEADER_SIZE]

    return Message(packet_type, seq_no, ack_no, payload)


def message_to_bytes(msg):
    """ Converts the given message into its binary representation
    """
    payload_len = min(len(msg.payload), MAX_PAYLOAD_SIZE)
    binary_msg = bytearray(HEADER_SIZE + payload_len)

    packet_type = PACKET_TYPES_IDS[msg.packet_type]
    ack_bit_mask = 0x80
    first_byte = packet_type | ack_bit_mask if msg.is_ack() else packet_type
    binary_msg[0] = first_byte

    binary_msg[2] = msg.seq_no
    binary_msg[3] = msg.ack_no

    len_msb = (payload_len >> 8) & 0xFF
    binary_msg[4] = len_msb
    len_lsb = payload_len & 0xFF
    binary_msg[5] = len_lsb

    binary_msg[6:] = msg.payload

    return binary_msg


def is_ack_for_message(message, ack):
    return ack.is_ack() and message.seq_no == ack.ack_no
