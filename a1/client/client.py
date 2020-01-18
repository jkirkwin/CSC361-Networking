'''
CSC 361 Programming Assignment 1
A very simple HTTP client.
'''

import sys
import socket as soc

def createRequest(fileName):
    return "GET {} HTTP/1.1".format(fileName)

def main(argv):
    serverIp = argv[0]
    serverPort = int(argv[1])
    serverAdr = (serverIp, serverPort)
    fileName = argv[2]

    print('Connecting to {} on port {} to access "{}"'.format(serverIp, serverPort, fileName))

    clientSocket = soc.socket(soc.AF_INET, soc.SOCK_STREAM)
    clientSocket.connect(serverAdr)

    request = createRequest(fileName)
    clientSocket.send(request)

    buffSize = 1024
    response = clientSocket.recv(buffSize)

    clientSocket.close()

    print("Response Received:")
    print(response)

if __name__ == '__main__':
    main(sys.argv[1:])