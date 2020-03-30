"""
    Utilities and constants related to the RDP (Reliable HTTP Server over UDP
    Protocol) as defined in the assignment 3 specification and related
    documentation.
"""
import logging
import socket
import time

DEFAULT_ACK_TIMEOUT_SECONDS = 2
DEFAULT_RETRY_THRESHOLD = 5

MAX_PACKET_SIZE = 1024
HEADER_SIZE = 6
MAX_PAYLOAD_SIZE = MAX_PACKET_SIZE - HEADER_SIZE

MAX_SEQ_NUMBER = 255
MAX_ACK_NUMBER = 255

FIN_KEEP_ALIVE = DEFAULT_ACK_TIMEOUT_SECONDS * 2

# Ugly, but we need bidirectional mapping and this is unlikely to change.
PACKET_TYPES_IDS = {
    "ACK": 0,
    "SYN": 1,
    "FIN": 2,
    "APP": 3,
}
PACKET_IDS_TYPES = ["ACK", "SYN", "FIN", "APP"]


class Connection:
    """ Represents an RDP connection between the owner of an instance and some
    remote party.
    """
    def __init__(self, remote_adr, remote_seq_num, seq_num=0):
        self.remote_adr = remote_adr
        self.last_index_received = remote_seq_num
        self.seq_num = seq_num % MAX_SEQ_NUMBER

    def get_next_seq_and_increment(self):
        seq = self.seq_num
        self.seq_num = (seq + 1 % MAX_SEQ_NUMBER)
        return seq

    def next_expected_index(self):
        return (self.last_index_received + 1) % MAX_ACK_NUMBER

    def increment_next_expected_index(self):
        self.last_index_received = self.next_expected_index()


class Message:
    """ Represents an RDP message with header fields and a payload.
    """

    def __init__(self,
                 packet_type,
                 seq_no,
                 ack_no,
                 payload=bytearray(),
                 src_adr=None,
                 dest_adr=None):
        """ Not for external use. Use factory methods to ensure consistency.
        """

        self.packet_type = packet_type  # String, key to types dict
        self.ack_no = ack_no
        self.seq_no = seq_no
        self.payload = payload
        self.src_adr = src_adr
        self.dest_adr = dest_adr

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


def message_from_bytes(binary_message, src_adr=None, dest_adr=None):
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

    # Remaining bytes are the payload
    payload_len = get_payload_len(binary_message[:HEADER_SIZE])
    payload = binary_message[HEADER_SIZE: payload_len + HEADER_SIZE]

    return Message(packet_type, seq_no, ack_no, payload, src_adr, dest_adr)


def get_payload_len(header_bytes):
    # Fifth and sixth bytes hold payload length
    msb = header_bytes[4]
    lsb = header_bytes[5]
    return (msb << 8) | lsb


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

    if msg.is_ack():
        binary_msg[3] = msg.ack_no

    len_msb = (payload_len >> 8) & 0xFF
    binary_msg[4] = len_msb
    len_lsb = payload_len & 0xFF
    binary_msg[5] = len_lsb

    binary_msg[6:] = msg.payload

    return binary_msg


def is_ack_for_message(message, ack):
    return ack.is_ack() and message.seq_no == ack.ack_no


def send_until_ack_in(message, sock, remote_adr):
    """ Transmits the message given and waits for an ACK.

    Sends the message in binary form to the given address via the given
    socket. The message will be re-sent after each timeout until either an
    ACK is received or the maximum number of timeouts is reached.

    :return: The ACK `Message` if received,  `None` otherwise
    """

    attempts = 0
    while attempts < DEFAULT_RETRY_THRESHOLD + 1:
        send_message(sock, message, remote_adr)
        ack = await_ack(message, sock, remote_adr)
        if ack:
            return ack
        else:
            attempts += 1

    return None


def await_ack(msg_out, sock, remote_adr, timeout=DEFAULT_ACK_TIMEOUT_SECONDS):
    """ Waits for up to the given timeout to receive an ack for the message.

    Repeatedly reads the socket until either the timeout expires or the message
    read is an ack for the given outbound message. All other messages read are
    discarded.

    :param msg_out: The message to be ACK'd
    :param sock: The socket on which to listen.
    :param remote_adr: The address of the socket from which the ack must come.
    :return: The ACK message if one is received. `None` otherwise.
    """
    logging.debug("Awaiting ACK")

    stop_time = time.time() + timeout

    time_remaining = stop_time - time.time()
    while time_remaining > 0:
        ack = try_receive_ack(msg_out, time_remaining, sock, remote_adr)
        if ack:
            logging.debug("ACK received")
            return ack
        else:
            time_remaining = stop_time - time.time()

    logging.debug("No ACK received")
    return None


def try_receive_ack(msg_out, timeout, sock, remote_adr):
    """ Wait for the specified timeout for an ACK to the given message.

    If the first message read from the socket is not the desired ack from the
    correct sender, it is discarded and the method returns `None`.
    """
    logging.debug("Attempting to receive ACK")
    try:
        msg_in = try_read_message(sock, timeout)
        if msg_in.src_adr == remote_adr and is_ack_for_message(msg_out, msg_in):
            logging.debug("ACK received")
            return msg_in
        else:
            logging.debug("Received message from {}, but not valid ACK."
                          .format(msg_in.src_adr))
    except socket.timeout:
        pass

    logging.debug("No ACK received")
    return None


def try_read_message(sock, timeout=None):
    """ Tries to read a message from the socket.

        :raises `socket.timeout` if a time_out is given and a message cannot be
        read before it
    """
    logging.debug("Attempting to read message")

    sock.settimeout(timeout)
    (message_bytes, src_adr) = sock.recvfrom(MAX_PACKET_SIZE)
    dest_adr = sock.getsockname()
    message = message_from_bytes(message_bytes, src_adr, dest_adr)

    logging.debug("Message (seq {}) read successfully from {}"
                  .format(message.seq_no, src_adr))

    return message


def send_message(sock, message, dest_adr):
    """ Sends the message to the provided address and updates message metadata.
    """
    logging.debug("Sending message to {}".format(dest_adr))

    message.dest_adr = dest_adr
    message.src_adr = sock.getsockname()
    sock.sendto(message_to_bytes(message), dest_adr)


def send_ack(msg_in, connection, sock):
    """ Creates and sends an ACK for the message. Does not update connection
    state.
    """
    logging.debug("Sending ACK")

    ack = create_ack_message(connection.seq_num, msg_in.seq_num)
    send_message(sock, ack, connection.remote_adr)

