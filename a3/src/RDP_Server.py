import os
import sys
from socket import *

from .RDP_Protocol import *

BUFF_SIZE = MAX_PACKET_SIZE  # todo why is this unused?
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
        sock = socket.socket(AF_INET, SOCK_DGRAM)
        sock.bind(self.adr)
        self.sock = sock

        # Allow clients to query the new address. Useful when the address given
        # at construction is a wildcard.
        self.adr = self.sock.getsockname()

    def _serve_loop(self):
        while True:
            try:
                print("Serving on {}".format(self.adr))

                block = CONNECTION_TIMEOUT if self.conn else None
                message = try_read_message(self.sock, block)
                self._dispatch(message)
            except socket.timeout:
                self._abandon_connection("Connection timeout expired")

    def _abandon_connection(self, cause):
        print("Client connectivity lost ({}). Abandoning connection"
              .format(cause))
        self.conn = None

    def _dispatch(self, message):
        """ Dispatch an inbound message to the appropriate handler.
        """
        if self.conn and self.conn.remote_adr != message.src_adr:
            print("Existing connection. Dropping packet received from {}"
                  .format(message.src_adr))

        elif message.is_syn():
            ack = self._receive_connection(message)
            if ack and not ack.is_ack_only():
                # We do not need to wait for the ACK_ONLY message if it is lost
                # before processing the following GET message as it will also
                # ACK the initial SYN message with the same sequence number.
                self._dispatch(ack)

        elif not self.conn:
            print("Received non-SYN message without a connection. Dropping.")

        elif message.seq_no != self.conn.next_expected_index():
            # todo relax this constraint - previous seq num is probably fine
            error_message = "WARNING: Bad sequence number: {}. Expected {}" \
                .format(message.seq_no, self.conn.last_index_received + 1)
            self._abandon_connection(error_message)

        elif message.packet_type == "APP":
            self._process_get_request(message)

        else:
            print("Failed to dispatch message. Dropping packet.")

    def _receive_connection(self, syn):
        """ Processes a SYN message and creates a connection.

        If there is already a connection between the client and server,
        this packet will effectively reset the connection.

        :return: The ACK message, if received.
        """
        assert syn.is_syn(), "Programming error. Requires SYN packet."

        if self.conn:
            assert self.conn.remote_adr == syn.src_adr
            print("WARNING: Received SYN message from already connected client")
        else:
            print("Connection request (SYN) from {}".format(syn.src_adr))

        self.conn = Connection(syn.src_adr, syn.seq_num)

        ack_no = self.conn.last_index_received
        seq_no = self.conn.get_next_seq_and_increment()
        reply = create_syn_message(ack_no, seq_no)

        ack = self._send_until_ack_in(reply)
        return ack

    def _process_get_request(self, message):
        assert self.conn, \
            "Programming Error. Cannot process APP packet without connection."

        filename = message.payload  # Not directly following HTTP structure.
        print("Received request from client for '{}'".format(filename))

        if not os.path.isfile(filename):
            string = "404 No Such File: {}".format(filename)
            ack = self._send_data(string.encode())  # todo ensure client checks if request was successful
            if not ack:
                return
        else:
            chunks = self._get_data_from_file(filename)
            for chunk in chunks:
                ack = self._send_data(chunk)
                if not ack:
                    return

        self._close_connection()

    def _send_data(self, data):
        """ Sends the given application data to the client.

        Wraps the given data in an APP message and sends it to the client. Waits
        until an ACK is received before returning.

        :return `None` if the connection was lost. The ack message to the data
        message sent otherwise.
        """

        assert len(data) <= MAX_PAYLOAD_SIZE, "Data chunk too large"

        ack_no = self.conn.last_index_received
        seq_no = self.conn.get_next_seq_and_increment

        msg = create_app_message(seq_no, ack_no, data)
        return self._send_until_ack_in(msg)

    @staticmethod
    def _get_data_from_file(filename):  # todo parameterize the chunk size or add a prefix to allow us to stick an http header in there.
        chunks = []
        with open(filename, 'rb') as file:
            chunk = file.read(MAX_PAYLOAD_SIZE)
            while chunk:
                chunks.append(chunk)
                chunk = file.read(MAX_PAYLOAD_SIZE)

        return chunks

    def _close_connection(self):
        if not self.conn:
            print("WARNING: No connection to close")
            return
        else:
            print("Closing connection")

        seq = self.conn.get_next_seq_and_increment()
        ack = self.conn.last_index_received
        fin_msg = create_fin_message(seq, ack)

        fin_ack_msg = self._send_until_ack_in(fin_msg)
        if not fin_ack_msg:
            print("INFO: No ACK received in response to FIN message.")
        elif not fin_ack_msg.is_fin():
            print("WARNING: FIN message ACK was not itself a FIN message.")

        self.conn = None

    def _send_until_ack_in(self, message):
        """ Transmits the message given and waits for an ACK. Abandons the
        connection if one is not received.
        :return: The ACK `Message` if received,  `None` otherwise
        """
        ack = send_until_ack_in(message, self.sock, self.conn.remote_adr)
        if not ack:
            self._abandon_connection("Maximum retries exceeded")

        return ack


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: " 
              "python3 -m a3.src.RDP_Server <Server IP> <Server Port>")
    else:
        ip = sys.argv[1]
        port = int(sys.argv[2])
        adr = (ip, port)
        server = Server(adr)
        server.serve()
