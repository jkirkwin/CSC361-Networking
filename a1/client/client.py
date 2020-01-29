'''
CSC 361 Programming Assignment 1
A very simple HTTP client that sends a GET request and prints the result.

Args: Server IP, Server Port, Name of file to request
'''

import sys
import socket as soc

def createGetRequest(fileName):
    return "GET /{} HTTP/1.1\r\n\r\n".format(fileName)

def main(serverIp, serverPort, fileName):
    print('='*40)
    print('Connecting to {}:{} to access "{}"'.format(serverIp, serverPort, fileName))
    print('='*40)
    
    # Connect and send request
    clientSocket = soc.socket(soc.AF_INET, soc.SOCK_STREAM)
    clientSocket.connect((serverIp, port))
    request = createGetRequest(fileName)
    clientSocket.send(request)

    # Retrieve and display response
    buffSize = 1024
    response = clientSocket.recv(buffSize)
    result = '' 
    while response:
        result = result + response
        response = clientSocket.recv(buffSize)     
    print(result)

    clientSocket.close()

if __name__ == '__main__':
    ip = sys.argv[1]
    port = int(sys.argv[2])
    filename = sys.argv[3]
    main(ip, port, filename)
