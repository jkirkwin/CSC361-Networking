'''
CSC 361 Programming Assignment 1
A very simple HTTP server that accepts only GET requests.
'''

import socket as soc
import sys # In order to terminate the program

##
# TODO Refactor this into smaller functions including a main
##

httpCodeDescriptions = {
    200: 'OK',
    400: 'Bad Request',
    403: 'Forbidden',
    404: 'Not Found',
    500: 'Internal Server Error',
    501: 'Not Implemented'
}

def getStatusLine(code=200):
    httpVersion = 'HTTP/1.1'
    desc = str(httpCodeDescriptions[code])
    return " ".join([httpVersion, str(code), desc])

# Create, bind the socket
serverSocket = soc.socket(soc.AF_INET, soc.SOCK_STREAM)
host = soc.gethostbyname(soc.gethostname()) # Supposedly safer than just using gethostname()
port = 50501 # Arbitrary choice
socketAdr = (host, port)
serverSocket.bind(socketAdr)

backlog = 5 # Conventional queue size 
serverSocket.listen(backlog)

while True:
    # Establish the connection
    print('Ready to serve...')
    clientSocket, addr = serverSocket.accept()
            
    try:
        # Parse the client's request
        bufferSize = 1024
        message = clientSocket.recv(bufferSize)
        msgTokens = message.split()
        
        requestType = msgTokens[0]
        if requestType != "GET":
            clientSocket.send(getStatusLine(501))
            continue

        filename = msgTokens[1]
        file = open(filename[1:])
        outputdata = file.read()
        # TODO check that the client is not trying to get the server source code.

        try:
            file.close()
        except IOError:
            print('Error. Failed to close file ' + filename)
            clientSocket.send(getStatusLine(500))
            continue

        clientSocket.send(getStatusLine(200))

        # Send the content of the requested file to the client
        for i in range(0, len(outputdata)):           
            clientSocket.send(outputdata[i].encode())
        clientSocket.send("\r\n".encode())

    except IOError:
        # Send response message for file not found
        clientSocket.send(getStatusLine(404))

    finally:
        clientSocket.close()

serverSocket.close()
sys.exit() # Terminate the program after sending the corresponding data