import hashlib
import random
import sys

from a3.src.RDP_Protocol import *

BUFF_SIZE = 2 * MAX_PACKET_SIZE


class ClientConnection(Connection):
    """ A `Connection` that holds a socket
    """
    def __init__(self, remote_adr, remote_seq_num, seq_num, sock):
        super().__init__(remote_adr, remote_seq_num, seq_num)
        self.sock = sock


def main(server_adr, filename, result_filename):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        connection = connect_to_server(server_adr, sock)

        content = get_from_server(filename, connection)

        if content:
            create_file(result_filename, content)
            if checksum_matches(filename, result_filename):
                print("="*5 + " CHECKSUM VERIFIED " + "="*5)
            else:
                print("!"*5 + " INVALID CHECKSUM " + "!"*5)
        else:
            print("Unable to retrieve '{}' from server.".format(filename))


def create_file(name, content, binary=False):
    mode = "wb" if binary else "w"
    with open(name, mode) as f:
        f.write(content)
    print("Created '{}'".format(name))


def get_from_server(filename, connection):
    """ Sends a request to the server for the given file.

    :param filename: The file to request
    :param connection: The connection to the server
    :return: The content of the file, if successful. None otherwise.
    """
    request = create_app_message(connection.get_next_seq_and_increment(),
                                 connection.last_index_received,
                                 filename)

    ack = send_until_ack_in(request, connection.sock, connection.remote_adr)
    if ack:
        return receive_file_content(connection, request, ack)
    else:
        print("ERROR: No ACK received")
        return None


# todo break this up into smaller methods
def receive_file_content(connection, request, ack):
    """ Read each APP message from the server, ACKing each one, until the
    connection is terminated.

    :param connection: The connection to the server
    :param request: The request that was sent
    :param ack: The ack for the request


    :return: The content of the file returned. None if no content was retrieved.
    """

    # todo check that the file was provided (e.g. not 404)

    if not (ack.is_app() or ack.is_fin()):
        print("ERROR: ack not an application or fin message.")
    else:
        content = ""
        data_msg = ack

        while data_msg.is_app():
            if data_msg.seq_no == connection.last_index_received:
                # Client ACK was lost. We have already processed this message.
                acknowledge_message(connection, data_msg)

            elif data_msg.seq_no == connection.next_expected_index():
                # Next chunk
                content += data_msg.get_payload_as_text()

            # Get the next message
            try:
                timeout = DEFAULT_ACK_TIMEOUT_SECONDS * DEFAULT_RETRY_THRESHOLD
                data_msg = try_read_message(connection.sock, timeout)
                if data_msg.src_adr != connection.remote_adr:
                    print("WARNING: Dropping packet from bad sender.")
            except socket.timeout:
                print("ERROR: Server stopped responding.")
                return None

        if data_msg.is_fin():
            handle_disconnection(data_msg, connection)
        else:
            print("ERROR: Non-FIN packet received")

        return content


def handle_disconnection(fin_in, connection):
    ack_no = fin_in.seq_num
    seq_no = connection.get_next_seq_and_increment()
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
    while remaining > 0:
        try:
            message = try_read_message(connection.sock, remaining)
            if message == fin_in:
                send_message(connection.sock, fin_out, connection.remote_adr)
        except socket.timeout:
            pass  # we will exit the loop on the next iteration
        remaining = stop_time - time.time()


def acknowledge_message(connection, inbound_msg):
    connection.last_index_received = inbound_msg.seq_no
    ack = create_ack_message(connection.seq_num, connection.last_index_received)
    send_message(connection.sock, ack, connection.remote_adr)


def connect_to_server(adr, sock):
    """ Perform a 3-way handshake with the server at the given remote address

    :param adr: The address of the server
    :param sock: The socket to use
    :return: The connection object created if successful, None otherwise.
    """
    seq_no = random.randint(0, MAX_SEQ_NUMBER)
    syn = create_syn_message(seq_no)

    response = send_until_ack_in(message_to_bytes(syn), sock, adr)
    if not response:
        print("No response from server")
        return None
    elif not response.is_syn():
        print("WARNING: Ack for SYN was not a SYN.")

    connection = ClientConnection(adr, response.seq_no, seq_no, sock)

    acknowledge_message(connection, response)

    return connection


def checksum_matches(filename1, filename2):
    """ Compares the md5 hashes of the content of the pair of files.
    """
    with open(filename1, "rb") as f1, open(filename2, "rb") as f2:
        hash1 = hashlib.md5(f1.read())
        hash2 = hashlib.md5(f2.read())
        return hash1 == hash2


if __name__ == '__main__':
    if len(sys.argv) not in [4, 5]:
        print("Usage: python3 -m a3.src.RDP_Client "
              "<Server IP> <Server Port> <Filename> [Result Filename]")
    else:
        ip = sys.argv[1]
        port = int(sys.argv[2])
        filename = sys.argv[3]
        result_filename = sys.argv[4] if len(sys.argv == 5) \
            else "RDP_RESULT_" + filename

        main((ip, port), filename, result_filename)

# todo add unit tests
