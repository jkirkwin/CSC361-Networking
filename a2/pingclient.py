import sys
import time
from socket import *

NUM_PINGS = 100
BUFF_SIZE = 1024


def main(remote_addr):
    """ Repeatedly ping the remote host.

    :param remote_addr: The IP address and port of the host to ping
    """
    print("Pinging Server at ".format(remote_addr))

    client_socket = socket(AF_INET, SOCK_DGRAM)

    for i in range(NUM_PINGS):
        print("")
        while not ping(client_socket, remote_addr, i):
            print("Ping {} dropped...Sending retransmission".format(i))


def ping(client_socket, server_addr, message_id):
    """ Send a ping message to the remote address.

    Constructs and sends a ping message with the given id to the to the server
    via the provided socket and processes the reply. If the server gives a
    positive reply, outputs the (RTT) for the message. The RTT is computed as
    the difference between the timestamp of the response and the *most recent*
    ping transmission.

    :param client_socket: The socket with which to send the ping.
    :param server_addr: The address of the remote host to ping.
    :param message_id: A unique identifier for the ping message.
    :return: ``True`` if the ping was successful. ``False`` otherwise.
    """
    # Send the ping
    timestamp = time.time()
    msg = create_message(message_id, time.ctime(timestamp))
    client_socket.sendto(msg, server_addr)

    # Process reply
    reply = get_reply(client_socket, server_addr)
    if msg.upper() == reply:
        # Ping successful
        reply_timestamp = time.time()
        print("Received reply from {}: {}".format(server_addr, reply))
        print("RTT {} seconds".format(reply_timestamp - timestamp))
        return True
    else:
        # Packet was dropped.
        return False


def create_message(index, timestamp):
    """ return a binary ping message using the index and current timestamp """
    return "ping {} {}".format(index, timestamp).encode()


def get_reply(client_socket, expected_addr):
    """ Get a reply message from the given remote host.

    Performs a simple read from the socket. The server process is running on 
    the same host (although in an emulated network) so we are guaranteed that 
    there will be no dropped packets. Packets received from other senders will
    be silently discarded.

    :param client_socket: The socket which will receive the reply
    :param expected_addr: The address from which the reply must come

    :return: The reply that is received.
    """
    reply = ''
    reply_received = False
    while not reply_received:
        # Discard packets from senders other than the server being pinged.
        (reply, reply_addr) = client_socket.recvfrom(BUFF_SIZE)
        reply_received = reply_addr == expected_addr

    return reply


if __name__ == '__main__':
    ip = sys.argv[1]
    port = int(sys.argv[2])
    main((ip, port))
