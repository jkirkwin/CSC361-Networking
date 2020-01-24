'''
CSC 361 Programming Assignment 1
A simple HTTP server that accepts only GET requests.
'''

import os
import socket as soc
import sys

httpCodeDescriptions = {
    200: 'OK',
    400: 'Bad Request',
    403: 'Forbidden',
    404: 'Not Found',
    500: 'Internal Server Error',
    501: 'Not Implemented'
}

def getHeader(code=200):
    httpVersion = 'HTTP/1.1'
    desc = str(httpCodeDescriptions[code])
    statusLine = " ".join([httpVersion, str(code), desc]) + '\r\n'
    return statusLine + '\r\n' # Second CRLF indicates the end of the header

def handleGetRequest(filename, clientSocket):
    # Do not allow clients to query server source code.
    if filename == os.path.basename(__file__):
        clientSocket.send(getHeader(403))
        return

    # Ensure file exists
    if not os.path.isfile(filename):
        clientSocket.send(getHeader(404))
        return

    # Process get request
    try:
        file = open(filename)
        outputdata = file.read()        
        file.close()

        clientSocket.send(getHeader(200))
        clientSocket.sendall(outputdata)
    
    except IOError:
        clientSocket.send(getHeader(500)) # Server error
        

def main(ip, port=80):
    # Create, bind the socket
    serverSocket = soc.socket(soc.AF_INET, soc.SOCK_STREAM)
    serverSocket.bind((ip, port))

    BACKLOG = 5 # Conventional queue size 
    serverSocket.listen(BACKLOG)

    while True:
        # Establish the connection
        print('Ready to serve on {}:{} ...'.format(ip, port))
        clientSocket, clientAdr = serverSocket.accept()
        print('Serving client {}'.format(clientAdr))                 

        # Get client request
        BUFFER_SIZE = 1024
        msg = clientSocket.recv(BUFFER_SIZE)
        msgTokens = msg.split()
        
        # Only GET requests are implemented
        requestType = msgTokens[0]
        if requestType != "GET":
            clientSocket.send(getHeader(501))
        else:
            filename = msgTokens[1][1:] # Assume leading slash
            handleGetRequest(filename, clientSocket)

        clientSocket.close()

    serverSocket.close()
    sys.exit()

if __name__ == '__main__':
    main(str(sys.argv[1]), int(sys.argv[2]))
