import random
import sys
from socket import *
from time import time

BUFF_SIZE = 1024


def main(local_address):
    """ Handles incoming ping messages.

    :param local_address: The IP and port to listen on.
    :return: ``None``
    """

    print("Running Ping Server on {}".format(local_address))

    server_socket = socket(AF_INET, SOCK_DGRAM)
    server_socket.bind(local_address)

    while True:
        (message, client_address) = server_socket.recvfrom(BUFF_SIZE)
        server_socket.sendto(get_reply(message), client_address)


def get_reply(message):
    """ Create a reply string for the given ping message.

    This function simulates packet loss in the network by randomly rejecting
    incoming messages. In this case, the created reply is a custom message used
    to indicate that the client must re-send its ping. Otherwise, the reply is
    an echo of the inbound message with all characters capitalized.

    :param message: The ping message to reply to.
    :return: The reply to send.
    """

    simulated_loss = random.randint(1, 10) < 4
    if simulated_loss:
        message_id = message.split()[1]
        print("Simulating dropped packet for ping {}".format(message_id))
        return "lost {} {}".format(message_id, time())
    else:
        return message.upper()


if __name__ == '__main__':
    ip = sys.argv[1]
    port = int(sys.argv[2])
    main((ip, port))
