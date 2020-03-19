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

# Ugly, but we need bidirectional mapping and this is unlikely to change.
PACKET_TYPES_IDS = {
    "ACK": 0,
    "SYN": 1,
    "FIN": 2,
    "APP": 3,
}
PACKET_IDS_TYPES = ["ACK", "SYN", "FIN", "APP"]

class Message:
    """
        Represents an RDP message with header fields and a payload.
    """

    def __init__(self, packet_type, seq_no, ack_no, payload=None):
        """ Not for external use. Use factory methods to ensure consistency.
        """

        self.ack_no = ack_no
        self.seq_no = seq_no
        self.payload = payload
        self._packet_type = packet_type  # String, key to types dict

    def is_syn(self):
        return self._packet_type == "SYN"

    def is_fin(self):
        return self._packet_type == "FIN"

    def is_app(self):
        return self._packet_type == "APP"

    def is_ack(self):
        # Note that this may return true in addition to is_syn etc.
        return bool(self.ack_no)

    def is_ack_only(self):
        return self._packet_type == "ACK"

    def get_payload_as_text(self):
        assert False, "Unimplemented"


def create_syn_message(seq_no, ack_no):
    """ Utility to create an RDP SYN message
    """
    return Message("SYN", seq_no, ack_no, None)


def create_ack_message(seq_no, ack_no):
    """ Utility to create an RDP DATA message
    """
    return Message("ACK", seq_no, ack_no, None)


def create_app_message(seq_no, ack_no, data):
    """ Utility to create an RDP APP message
    """
    return Message("APP", seq_no, ack_no, data)


def create_fin_message(seq_no, ack_no):
    """ Utility to create an RDP FIN message
    """
    return Message("FIN", seq_no, ack_no, None)


def message_from_bytes(bytes):
    pass  # todo


def message_to_bytes(msg):
    pass  # todo

def is_ack_for_message(message, ack):
    return ack.is_ack() and message.seq_no == ack.ack_no
