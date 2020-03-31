import os
import sys
from socket import *

from .RDP_Protocol import *

logging.basicConfig(level=logging.DEBUG)

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

        logging.debug("Created and bound socket to port {}".format(self.adr[1]))

    def _serve_loop(self):
        logging.info("Serving on {}".format(self.adr))
        while True:
            try:
                block = CONNECTION_TIMEOUT if self.conn else None
                message = try_read_message(self.sock, block)

                logging.debug("Read message from serve loop")

                self._dispatch(message)
            except socket.timeout:
                self._abandon_connection("Connection timeout expired")

    def _abandon_connection(self, cause):
        logging.warning("Client connectivity lost ({}). Abandoning connection"
                        .format(cause))
        self.conn = None

    def _dispatch(self, message):
        """ Dispatch an inbound message to the appropriate handler.
        """
        if self.conn and self.conn.remote_adr != message.src_adr:
            logging.warning("Existing connection with {}. "
                            "Dropping packet received from {}"
                            .format(self.conn.adr, message.src_adr))

        elif message.is_syn():
            ack = self._receive_connection(message)
            if ack and not ack.is_ack_only():
                # We do not need to wait for the ACK_ONLY message if it is lost
                # before processing the following GET message as it will also
                # ACK the initial SYN message with the same sequence number.
                self._dispatch(ack)

        elif not self.conn:
            logging.warning("Received non-SYN message without a connection. "
                            "Dropping.")

        elif message.seq_no != self.conn.next_expected_index():
            # todo relax this constraint - previous seq num is probably fine
            error_message = "Bad sequence number: {}. Expected {}"\
                .format(message.seq_no, self.conn.last_index_received + 1)
            self._abandon_connection(error_message)

        elif message.packet_type == "APP":
            self._process_get_request(message)

        else:
            logging.warning("Failed to dispatch message. Dropping packet.")

    def _receive_connection(self, syn):
        """ Processes a SYN message and creates a connection.

        If there is already a connection between the client and server,
        this packet will effectively reset the connection.

        :return: The ACK message, if received.
        """
        assert syn.is_syn(), "Programming error. Requires SYN packet."

        if self.conn:
            assert self.conn.remote_adr == syn.src_adr
            logging.warning("Received SYN message from already connected client")
        else:
            logging.info("Connection request (SYN) from {}".format(syn.src_adr))

        self.conn = Connection(syn.src_adr, syn.seq_no)

        ack_no = self.conn.last_index_received
        seq_no = self.conn.get_seq_and_increment()
        reply = create_syn_message(seq_no, ack_no)

        logging.info("Using base sequence number {}".format(seq_no))

        ack = self._send_until_ack_in(reply)
        return ack

    def _process_get_request(self, message):
        assert self.conn, \
            "Programming Error. Cannot process APP packet without connection."

        filename = message.payload  # Not directly following HTTP structure.
        logging.info("Received request from client for '{}'".format(filename))

        if not os.path.isfile(filename):
            logging.info("No such file '{}'".format(filename))

            content = "404 No Such File: {}".format(filename)
            ack = self._send_data(content.encode())  # todo ensure client checks if request was successful
            if not ack:
                return
        else:
            chunks = self._get_data_from_file(filename)
            logging.info("Sending data in {} chunks".format(len(chunks)))
            for chunk in chunks:
                ack = self._send_data(chunk)
                if not ack:
                    return

        self._close_connection()

    def _send_data(self, data):
        """ Sends the given application data to the client.

        Wraps the given data in an APP message and sends it to the client. Waits
        until an ACK is received before returning.

        :param data The binary data to be sent

        :return `None` if the connection was lost. The ack message to the data
        message sent otherwise.
        """

        assert len(data) <= MAX_PAYLOAD_SIZE, "Data chunk too large"

        ack_no = self.conn.last_index_received
        seq_no = self.conn.get_seq_and_increment

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
            logging.warning("Cannot close connection. No connection to close")
            return
        else:
            logging.info("Closing connection")

        seq = self.conn.get_seq_and_increment()
        ack = self.conn.last_index_received
        fin_msg = create_fin_message(seq, ack)

        fin_ack_msg = self._send_until_ack_in(fin_msg)
        if not fin_ack_msg:
            logging.warning("No ACK received in response to FIN message.")
        elif not fin_ack_msg.is_fin():
            logging.warning("FIN message ACK was not itself a FIN message.")

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
