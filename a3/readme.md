# Assignment 3 - Reliable HTTP Over UDP

<!-- Jamie Kirkwin, CSC 361, V00875987 -->

## Intro

For this assignment I built Python programs which communicate over UDP sockets 
using a TCP/HTTP-esque protocol, RDP (not to be confused with remote desktop) as
specified in the assignment spec.

## Running the code

Set your working directory to be the one which contains `a3`. If you've cloned 
the repo, this would be `CSC361`.

To run the unit tests: 
```bash
python3 -m a3.test.<TestName>
```

To run the server process: 
```bash
python3 -m a3.src.RDP_Server <Server IP> <Server Port>
```

To run the client process (After running the server process):
```bash
python3 -m a3.src.RDP_Client <Server IP> <Server Port> <Filename> <Result Filename>
```

You can alternatively run the client and server from the `a3` directory using 
`src.modulename` instead of `a3.src.modulename`.

## Client
The client implementation is `RDP_Client.py` as per the specification.

After connecting to the server (see __Protocol__), the client will send a GET
message and will receive a set of datagrams holding the content of the specified
file, after which the connection will terminate.

The client will then save the file locally.

The client's buffer size is the same as the maximum packet size: 1024 bytes.

The client is implemented as a simple script which runs `main` once and 
terminates. 

The client process logs informational messages including success/failure of the 
request, and success/failure of a md5-based checksum between the result and the 
source file sent by the server.

## Server
The server implementation is called `RDP_Server.py` as per the specification.

The server will wait for a client connection, and will then provide the 
requested file via APP messages, before closing the connection.

The server's buffer size is the same as the maximum packet size: 1024 bytes.

The server process will continue to run after a connection. Multiple requests 
can be made without restarting the server.

The server is implemented as a script which creates and starts a `Server` 
object.

The server logs informational messages about the status of the connection and 
file transfer.

## Protocol

As defined here, the RDP will not be a symmetric protocol; that is, the 
structure and timing of messages sent by the client and server are different.

Elements of the protocol (as described below) that pertain to both client and 
server are housed in `src/RDP_Protocol.py`. These include abstractions for 
connections and messages, constants, and functions used to read, write, and time
messages/acknowledgements.

### Packet Structure

Packets are comprised of a 6 byte fixed header and a variable length 
payload. Total packet length must not exceed 1024 bytes.

Each message has the following fields:
* Is Acknowledgement (A) - A single bit which indicates whether the 
acknowledgement number field has meaning.
* Packet Type - Indicates what this packet is used for. (7 bits) 
Allowed values are:
    * 0 (ACK_ONLY): No information besides an acknowledgement
    * 1 (SYN): A synchronization message to begin a connection
    * 2 (FIN): A finish message to terminate a connection
    * 3 (APP): An application-data-carrying message
    
* Reserved for future use (1 byte)
* Sequence Number - The index of the message in the uni-directional message
 stream (1 byte)
* Acknowledgement Number - The sequence number of the previously received and
  successfully processed message (1 byte)
* Payload length - The number of bytes in the payload. (2 bytes)

Note that sequence and acknowledgement numbers are incremented on a per-message
basis, rather than indexing to the binary data stream as is done in TCP. Note 
also that a message with sequence number `x` is ACK'd by a message with 
acknowledgement number `x`, __not__ `x+1`.

The Packet Type and A bit share a single byte, with the least significant 4 bits
used for the packet type, and the most significant bit used for the A flag. 
<pre>
0                                   1                                   2
+----+------------------------------+-----------------------------------+ 0
|  A |        Packet Type           |           Reserved                |
+----+------------------------------+-----------------------------------+ 2
|           Seq No.                 |           Ack No.                 |
+-----------------------------------+-----------------------------------+ 4
|       Payload Length MSB          |        Payload Length MSB         | 
+-----------------------------------------------------------------------+ 6
|                                                                       |
|                           Payload                                     |
|                                                                       |
+-----------------------------------------------------------------------+
</pre>

### Sequence and ACK Number Semantics

A message with sequence number `x` is to be acknowledged by a message with 
acknowledgement number `x`.

The sequence number of a uni-directional stream will be incremented by 1 for 
every packet sent that is not of type ACK_ONLY. 

The only message sent between the client and server that does not have the A bit
set is the initial SYN message sent from client to server to initiate a 
connection.

The acknowledgement number field of a message must contain the acknowledgement 
number of the most recently received message that was successfully processed. 

Sequence numbers have a maximum value of 255 and a minimum value of 0. If a 
message has sequence number 255, then the next non-ACK_ONLY message will have 
sequence number 0.

The initial sequence number of a message stream in either direction may start 
with any value in the range [0, 255].

### Connection Establishment
Similar to TCP, there is a three way handshake in order to begin a connection.

The client sends the first message (A SYN message with no ACK) to initiate the
connection. All other messages exchanged will have the ack bit set. 
The client will wait until it receives a SYN-ACK packet from the server and will
retransmit the initial SYN as needed, up to a maximum amount of times after which
it will give up and consider the server unreachable. 

On receipt of the SYN message, the server will send back a SYN message with the 
ACK bit set and the acknowledgement number equal to the sequence number of the 
previous message.

After the server's SYN message has been ACK'd, the server views the connection 
as established and it awaits an APP message to begin the data transfer phase. 
If the client retransmits a SYN message while the server considers the 
connection established, the server will respond with the appropriate ACK 
message and consider the connection reset.

After the client has sent an ACK for the server's SYN message, it will send a 
GET request in an APP message with the same ACK number. If the initial ACK is 
lost and the APP/ACK packet arrives at the server, the server must proceed 
directly from the connection establishment phase to the data transfer phase.

### Data Transfer

For the client, this phase begins once it has sent an ACK for the server's SYN 
message. The client will then send an APP message containing the name of the 
file being requested (analogous to an HTTP GET request).

For the server, this phase begins once it receives an APP message from the 
client following connection establishment. On receipt of the request, the server 
will process it and send an appropriate response. If a timeout is exceeded 
before the GET request is received, the server considers the connection lost.

In the case that the server has access to the given file and the file content 
does not fit inside a RDP packet, the server will split the response into 
fragments that each fit within an RDP packet. These messages will have 
increasing sequence numbers and will all have an ACK number corresponding to the
GET request packet. All of these messages with have PACKET_TYPE = APP. Each 
message will begin with 3 bytes indicating the HTTP return code. 

For example, if the file is unavailable to the server, it will send a single APP
message containing exactly the UTF-8 encoding of `404` as payload. If the server
is able to find the file, the payload of each APP packet sent will begin with 
`200`.

The client will send ACK messages for each received DATA packet, and the server
will wait until an ACK is received before sending the next DATA packet. If an 
ACK is not received in a set timeout, the server will re-transmit the last sent
packet. If a number of retransmissions occur for a single packet, the server 
will consider the connection lost and re-enter its disconnected listening state.

### Connection Release

Once the server has received an ACK for the final DATA packet for the HTTP 
response, it will send a FIN packet containing no payload.

On receipt of the FIN packet, the client will begin its connection release 
procedure. It will send back a FIN message which acknowledges the server's FIN
message. The client will then wait for a period of time to ensure that the 
server received the second FIN message. If the client receives a re-transmitted
FIN message from the server during this period, it will re-transmit its reply.

### Overview
[comment]: https://textart.io/sequence
<pre>
+---------+      +---------+
| Client  |      | Server  |
+---------+      +---------+
     |                |
     | SYN            |
     |--------------->|
     |                |
     |        SYN,ACK |
     |<---------------|
     |                |
     | ACK            |
     |--------------->|
     |                |
     | GET, ACK       |
     |--------------->|
     |                |
     |      DATA, ACK |
     |<---------------|
     |                |
     | ACK            |
     |--------------->|
     |       .        |
     |       .        |
     |       .        |
     |                |
     |      DATA, ACK |
     |<---------------|
     |                |
     | ACK            |
     |--------------->|
     |                |
     |       FIN, ACK |
     |<---------------|
     |                |
     | FIN, ACK       |
     |--------------->|
     |                |
     |                |
     |                |
 </pre>