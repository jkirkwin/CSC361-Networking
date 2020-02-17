import sys
from select import select
from socket import *
from time import time

NUM_PINGS = 100
BUFF_SIZE = 1024
DEFAULT_TIMEOUT_SECONDS = 1


def main(remote_addr):
    """ Repeatedly ping a remote host.

    :param remote_addr: The IP address and port of the host to ping
    """
    print("Pinging Server at ".format(remote_addr))

    client_socket = socket(AF_INET, SOCK_DGRAM)

    for i in range(NUM_PINGS):
        print("")
        while not ping(client_socket, remote_addr, i):
            pass


def ping(client_socket, server_addr, message_id):
    """ Send a ping message to the remote address and process the response.

    :param client_socket: The socket with which to send the ping.
    :param server_addr: The address of the remote host to ping.
    :param message_id: A unique identifier for the ping message.
    :return: ``True`` if the ping was successful. ``False`` otherwise.
    """
    # Send the ping
    timestamp = time()
    msg = create_message(message_id, timestamp)
    client_socket.sendto(msg, server_addr)

    reply = get_reply(client_socket, server_addr)
    if msg.upper() == reply:
        # Ping successful
        print(reply)
        print("RTT for ping {}: {}".format(message_id, time() - timestamp))
        return True
    else:
        # Packet was dropped.
        # todo should we compute the RTT based on the old timestamp or simply
        #  run the sending protocol again? If we want rtt = time of initial ping
        #  to time of valid reply, then we need to adjust this logic.
        print("Ping {} dropped...".format(message_id))
        return False


def create_message(index, timestamp):
    """ return a binary ping message using the index and current timestamp """
    return "ping {} {}".format(index, timestamp).encode()


def get_reply(client_socket, expected_addr, timeout=DEFAULT_TIMEOUT_SECONDS):
    """ Get a reply message from the given remote host.

    :param client_socket: The socket which will receive the reply
    :param expected_addr: The address from which the reply must come
    :param timeout: The maximum amount of time allowed between a read attempt
                    and data retrieval from the socket.

    :return: The reply that is received. ``None`` if the timeout expires before
             data can be read.
    """
    reply = ''
    reply_received = False
    while not reply_received:
        # Account for the possibility of packets that were really were dropped.
        # TODO ask TAs/Jianping about this - make sure it won't lose you marks.
        ready = select([client_socket], [], [], timeout)  
        if ready[0]:
            (reply, reply_addr) = client_socket.recvfrom(BUFF_SIZE)
            reply_received = reply_addr == expected_addr
        else:
            return None

    return reply


if __name__ == '__main__':
    ip = sys.argv[1]
    port = int(sys.argv[2])
    main((ip, port))
