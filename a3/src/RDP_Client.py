import hashlib
import random
import sys

from .RDP_Protocol import *

logging.basicConfig(level=logging.DEBUG)

CLIENT_PORT = 55555
CLIENT_ADR = ('', CLIENT_PORT)


class ClientConnection(Connection):
    """ A `Connection` that holds a socket
    """
    def __init__(self, remote_adr, remote_seq_num, seq_num, sock):
        super().__init__(remote_adr, remote_seq_num, seq_num)
        self.sock = sock


def main(server_adr, filename, result_filename):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(CLIENT_ADR)

        connection = connect_to_server(server_adr, sock)
        if connection:
            content = get_from_server(filename, connection)

            if content:
                create_file(result_filename, content, binary=True)
                if checksum_matches(filename, content):
                    logging.info("CHECKSUM VERIFIED")
                else:
                    logging.warning("INVALID CHECKSUM")
            else:
                logging.error("Unable to retrieve '{}' from server.".
                              format(filename))


def connect_to_server(adr, sock):
    """ Perform a 3-way handshake with the server at the given remote address

    :param adr: The address of the server
    :param sock: The socket to use
    :return: The connection object created if successful, None otherwise.
    """
    seq_no = random.randint(0, MAX_SEQ_NUMBER)
    logging.info("Initial Sequence Number: {}".format(seq_no))

    syn = create_syn_message(seq_no)

    logging.info("Connecting to server {}".format(adr))

    response = send_until_ack_in(syn, sock, adr)
    if not response:
        logging.error("No response from server")
        return None
    elif not response.is_syn():
        logging.warning("Ack for SYN was not a SYN.")

    connection = ClientConnection(adr, response.seq_no, seq_no, sock)

    send_ack(response, connection, sock)
    return connection


def get_from_server(filename, connection):
    """ Sends a request to the server for the given file.

    :param filename: The file to request
    :param connection: The connection to the server
    :return: The binary content of the file, if successful. None otherwise.
    """
    request = create_app_message(connection.increment_and_get_seq(),
                                 connection.last_index_received,
                                 filename.encode())

    logging.info("Sending request to server")

    ack = send_until_ack_in(request, connection.sock, connection.remote_adr)
    if ack:
        if not (ack.is_app()):
            logging.error("ACK not an application message.")
            return None
        else:
            return receive_file_content(connection, ack)
    else:
        logging.error("No ACK received for GET request")
        return None


def receive_file_content(connection, app):
    """ Receives the file content from the server.

    Read each APP message from the server, ACKing each one, until the connection
    is terminated.

    :param connection: The connection to the server
    :param app: The first app message from the server


    :return: The binary content of the file returned. None if no content was
    retrieved.
    """
    assert app.is_app(), "Programming error"

    content = b""
    message_in = app

    while message_in.is_app():
        # Process the current message
        content = process_app_message(message_in, connection, content)
        if not content:
            return None

        # Get the next message
        try:
            timeout = DEFAULT_ACK_TIMEOUT_SECONDS * DEFAULT_RETRY_THRESHOLD
            message_in = try_read_message(connection.sock, timeout)
            if message_in.src_adr != connection.remote_adr:
                logging.warning("Dropping packet from bad sender.")
        except socket.timeout:
            logging.error("Server stopped responding.")
            return None

    # Disconnect
    if message_in.is_fin():
        logging.debug("FIN received, disconnecting")
        handle_disconnection(message_in, connection)
    else:
        logging.error("Non-FIN packet received during file transfer")
        connection.sock.close()

    return content


def create_file(name, content, binary=False):
    mode = "wb" if binary else "w"
    with open(name, mode) as f:
        f.write(content)
    logging.info("Created '{}'".format(name))


def process_app_message(msg, connection, current_content):
    """ Processes the given APP message.

    :param msg The APP message received from the server
    :param connection The current connection
    :param current_content A binary string containing all previously received
    content from the server

    :return: The total content received from the server. `None` if an error
    occurred.
    """
    if msg.seq_no == connection.next_expected_index():
        # Inspect HTTP header
        rdp_payload = msg.payload
        http_code = rdp_payload[:HTTP_CODE_LEN]

        if http_code != HTTP_OK_ENCODED:
            logging.error("Bad HTTP Code received: {}"
                          .format(http_code.decode()))
            return None
        else:
            # Next chunk
            logging.debug("Received chunk of file from server")
            current_content += rdp_payload[HTTP_CODE_LEN:]
            send_ack(msg, connection, connection.sock)
            connection.increment_next_expected_index()

    elif msg.seq_no == connection.last_index_received:
        # Client ACK was lost. We have already processed this message.
        logging.debug("Re-ACKing seq {}".format(msg.seq_no))
        send_ack(msg, connection, connection.sock)

    else:
        # Unknown seq no
        s = "Bad sequence number {} during file transfer. Expected {}." \
            .format(msg.seq_no,
                    connection.next_expected_index())
        logging.error(s)
        return None

    return current_content


def handle_disconnection(fin_in, connection):
    ack_no = fin_in.seq_no
    seq_no = connection.increment_and_get_seq()
    fin_out = create_fin_message(seq_no, ack_no)

    send_message(connection.sock, fin_out, connection.remote_adr)

    fin_keep_alive(fin_in, fin_out, connection)

    connection.sock.close()


def fin_keep_alive(fin_in, fin_out, connection):
    """ Keeps the Client process alive for the designated time period.

    Re-sends the FIN-ACK message if a duplicate FIN is received from the server.

    :param fin_in The FIN message received from the server
    :param fin_out The FIN-ACK message reply to `fin_in`
    :param connection The ClientConnection object to provide the socket and
    remote address
    """
    remaining = FIN_KEEP_ALIVE
    stop_time = time.time() + remaining

    logging.debug("Beginning keep alive period")

    while remaining > 0:
        try:
            message = try_read_message(connection.sock, remaining)
            if message == fin_in:
                send_message(connection.sock, fin_out, connection.remote_adr)
        except socket.timeout:
            pass  # we will exit the loop on the next iteration
        remaining = stop_time - time.time()

    logging.debug("Keep alive period complete")


def checksum_matches(content, filename):
    """ Compares the md5 hash of the binary string given and the content of the
    file specified.
    """
    with open(filename, "rb") as f:
        content_hash = hashlib.md5(content)
        file_hash = hashlib.md5(f.read())
        return content_hash == file_hash


if __name__ == '__main__':
    if len(sys.argv) not in [4, 5]:
        print("Usage: python3 -m a3.src.RDP_Client "
              "<Server IP> <Server Port> <Filename> <Result Filename>")
    else:
        ip = sys.argv[1]
        port = int(sys.argv[2])
        filename = sys.argv[3]
        result_filename = sys.argv[4]
        main((ip, port), filename, result_filename)

# todo add unit tests/no-loss test
