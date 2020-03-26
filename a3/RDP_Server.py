import os
import sys
import time
from socket import *

from a3.RDP_Protocol import *

BUFF_SIZE = MAX_PACKET_SIZE
CONNECTION_TIMEOUT = 10


class Server:

    def __init__(self, adr):
        self.adr = adr
        self.sock = None  # Socket is bound once serve is called
        self.conn = None

    def serve(self):
        """ Serve on the configured port.
        """
        try:
            self._create_and_bind_socket()
            self._serve_loop()
        except:
            # Catch and re-raise any unexpected exception (such as
            # user interrupt) after closing the socket
            raise
        finally:
            self.sock.close()
            self.sock = None

    def _create_and_bind_socket(self):
        sock = socket(AF_INET, SOCK_DGRAM)
        sock.bind(self.adr)
        self.sock = sock

        # Allow clients to query the new address. Useful when the address given
        # at construction is a wildcard.
        self.adr = self.sock.getsockname()

    def _serve_loop(self):
        while True:
            if self.conn:
                self.sock.settimeout(CONNECTION_TIMEOUT)
            else:
                self.sock.setblocking(True)

            try:
                (data, client_address) = self.sock.recvfrom(BUFF_SIZE)
                print("RECV'd data from {}".format(client_address))

                message = message_from_bytes(data)
                self._dispatch(message, client_address)
            except timeout:
                self._abandon_connection("Connection timeout expired")

    def _abandon_connection(self, cause):
        print("Client connectivity lost ({}). Abandoning connection"
              .format(cause))
        self.conn = None

    def _dispatch(self, message, address):
        """ Dispatch an inbound message to the appropriate handler.
        """
        if self.conn and self.conn.client_adr != address:
            print("Existing connection. Dropping packet received from {}"
                  .format(address))

        elif message.is_syn():
            ack = self._receive_connection(message, address)
            if not ack.is_ack_only():
                # We do not need to wait for the ACK_ONLY message if it is lost
                # before processing the following GET message as it will also
                # ACK the initial SYN message with the same sequence number.
                self._dispatch(ack, address)

        elif not self.conn:
            print("Received non-SYN message without a connection. Dropping.")

        elif message.seq_no != \
                (self.conn.last_index_received + 1) % MAX_SEQ_NUMBER:
            error_message = "Bad sequence number: {}. Expected {}" \
                .format(message.seq_no, self.conn.last_index_received + 1)
            self._abandon_connection(error_message)

        elif message.packet_type == "APP":
            self._process_get_request(message)

        else:
            print("Failed to dispatch message. Dropping packet.")

    def _receive_connection(self, client_msg, client_address):
        """ Processes a SYN message and creates a connection.

        If there is already a connection between the client and server,
        this packet will effectively reset the connection.

        :return: The ACK message, if received.
        """
        assert client_msg.is_syn(), "Programming error. Requires SYN packet."
        assert not self.conn, "Programming error. Existing connection."

        print("Connection request (SYN) from {}".format(client_address))

        self.conn = Connection(client_address, client_msg.seq_num)

        ack_no = self.conn.last_index_received
        seq_no = self.conn.get_next_seq_and_increment()
        reply = create_syn_message(ack_no, seq_no)

        ack = self._send_until_ack_in(reply)
        if not ack:  # failed to create connection.
            self.conn = None

        return ack

    def _process_get_request(self, message):
        assert self.conn, \
            "Programming Error. Cannot process APP packet without connection."

        filename = message.payload  # Not directly following HTTP structure.

        if not os.path.isfile(filename):
            self._send_data("404 No Such File: {}".format(
                filename))  # todo ensure client checks if request was successful
        else:
            chunks = self._get_data_from_file(filename)
            for chunk in chunks:
                self._send_data(chunk)

            self._close_connection()

    def _send_data(self, data):
        """ Sends the given application data to the client.

        Wraps the given data in an APP message and sends it to the client. Waits
        until an ACK is received before returning.
        """

        assert len(data) <= MAX_PAYLOAD_SIZE, "Data chunk too large"

        ack_no = self.conn.last_index_received
        seq_no = self.conn.get_next_seq_and_increment

        msg = create_app_message(seq_no, ack_no, data)
        self._send_until_ack_in(msg)

    @staticmethod
    def _get_data_from_file(filename):
        chunks = []
        with open(filename, 'rb') as file:
            chunk = file.read(MAX_PAYLOAD_SIZE)
            while chunk:
                chunks.append(chunk)
                chunk = file.read(MAX_PAYLOAD_SIZE)

        return chunks

    def _close_connection(self):
        seq = self.conn.get_next_seq_and_increment()
        ack = self.conn.last_index_received
        fin_msg = create_fin_message(seq, ack)

        fin_ack_msg = self._send_until_ack_in(fin_msg)
        if not fin_ack_msg.is_fin():
            print("WARNING: FIN message ACK was not itself a FIN message.")

        self.conn = None

    def _send_until_ack_in(self, message):
        """ Transmits the message given and waits for an ACK.

        Sends the message in binary form to the given address via the given
        socket. The message will be re-sent after each timeout until either an
        ACK is received or the maximum number of timeouts is reached.

        :param message: The message object to send
        :return: The ACK `Message` if received,  `None` otherwise
        """

        attempts = 0
        while attempts < DEFAULT_RETRY_THRESHOLD:
            self.sock.sendto(message_to_bytes(message), self.conn.client_adr)

            ack = self._await_ack(message)
            if ack:
                return ack
            else:
                attempts += 1

            self._abandon_connection("Maximum retries exceeded")

    def _await_ack(self, message_out):
        """ Waits for up to `DEFAULT_ACK_TIMEOUT_SECONDS` to receive an ack

        Repeatedly reads the server socket until either the timeout expires, or
        the message read is an ack for the given outbound message. All other
        messages read are discarded.

        :param message_out: The message to be ACK'd
        :return: The ACK message if one is received. `None` otherwise.
        """

        stop_time = time.time() + DEFAULT_ACK_TIMEOUT_SECONDS

        time_remaining = stop_time - time.time()
        while time_remaining > 0:
            ack = self._try_receive_ack(message_out, time_remaining)
            if ack:
                return ack
            else:
                time_remaining = stop_time - time.time()
        return None

    def _try_receive_ack(self, message_out, timeout):
        """ Wait for the specified timeout for an ack to the given message

        If the first message read from the socket is not the desired ack, it is
        discarded and the method returns `None`.
        """
        self.sock.settimeout(timeout)
        try:
            (data, sender_address) = self.sock.recvfrom(BUFF_SIZE)
        except timeout:
            return None

        if sender_address == self.conn.client_adr:
            message_in = message_from_bytes(data)
            if is_ack_for_message(message_out, message_in):
                return message_in


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python RDP_Server.py <Server IP> <Server Port>")
    else:
        ip = sys.argv[1]
        port = int(sys.argv[2])
        adr = (ip, port)
        server = Server(adr)
        server.serve()
