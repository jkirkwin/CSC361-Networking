# Assignment 3 - Reliable HTTP Over UDP

## Intro

For this assignment I need to build two Python scripts which will communicate 
over UDP sockets using a TCP/HTTP-esque protocol, RDP (not to be confused with 
remote desktop.

The most notable difference is that sequence and acknowledgement numbers 
increment by one for each meaningful (non-ack-only) packet, rather than indexing
into the byte stream.

## Client
The client implementation will be called `RDP_Client.py` as per the 
specification.

After connecting to the server (see __Protocol__), the client will send a GET
message and will receive a set of datagrams holding the content of the specified
file.

The client will then save the file locally.

The client's buffer size is larger than the maximum packet size.

## Server
The server implementation will be called `RDP_Server.py` as per the 
specification.

The server will wait for a client connection, and will then provide the 
requested file via DATA messages, before closing the connection.

The server's buffer is the same size as that of the maximum packet, at 1024 
bytes.
## Protocol

As defined here, the RDP will not be a symmetric protocol; that is, the 
structure and timing of messages sent by the client and server are different.

### Packet Structure

Packets are comprised of a 6 byte fixed header and a variable length 
payload. Total packet length must not exceed 1024 bytes.

Each message has the following fields:
* Is Acknowledgement (A) - Indicates whether the acknowledgement number field 
has meaning.
* Packet Type - Indicates what this packet is used for. Allowed values are:
    * 0 (ACK ONLY): No information besides an acknowledgement
    * 1 (SYN): A synchronization message to begin a connection
    * 2 (FIN): A finish message to terminate a connection
    * 3 (APP): An application-data-carrying message
    
* Reserved for future use (1 byte)
* Sequence Number - The index of the message in the uni-directional message
 stream
* Acknowledgement Number - The sequence number of the previously received and
  successfully processed message
* Payload length - The number of bytes in the payload.

Note that sequence and acknowledgement numbers are incremented on a per-message
basis, rather than indexing to the binary data stream as is done in TCP. Note 
also that a message with sequence number `x` is ACK'd by a message with 
acknowledgement number `x`, __not__ `x+1`.

The Packet Type and A bit share a single byte, with the least significant 4 bits
used for the packet type, and the most significant bit used for the A flag. 

Both the sequence number and acknowledgement number fields, in that order, are 
one byte each. 
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

### Connection Establishment
Similar to TCP, there is a three way handshake in order to begin a connection.
The client sends the first message (A SYN message with no ACK) to initiate this connection.

The client will send an initial ACK message to the server with the ACK bit set 
to false. All other messages exchanged will have the ack bit set. The client 
will wait until it receives a SYN-ACK packet from the server and will retransmit
as needed, up to a maximum amount of times after which it will give up and 
consider the connection lost. 

On receipt of the SYN message, the server will send back a SYN message with the 
ACK bit set and the acknowledgement number equal to the sequence number of the 
previous message.

Every time the server sends a message, it will wait until the client sends back 
an appropriate ACK. All messages sent by the server will have the ack bit set 
and the acknowledgement number set to the sequence number of the most recently 
processed packet.

After the server's SYN message has been ACK'd, the server views the connection 
as established and it awaits an APP message to begin the data transfer phase. 
If the client retransmits a SYN message while the server considers the 
connection established, the server will respond with the appropriate ACK 
message.

After the client has sent an ACK for the server's SYN message, it will send a 
GET request in an APP message with the same ACK number. If the initial ACK is 
lost and the APP/ACK packet arrives at the server, the server must proceed 
directly from the connection establishment phase to the data transfer phase.

### Data Transfer

For the client, this phase begins once it has sent an ACK for the server's SYN 
message. The client will then send an HTTP GET message.

For the server, this phase begins once it receives a GET message from the client
following connection establishment. On receipt of the GET request, the server 
will process the request and send an appropriate HTTP response. If a timeout is
exceeded before the GET request is received, the server considers the connection 
lost.

In the case that the server has access to the given file and the file content 
does not fit inside a RDP packet, the server will split the HTTP response into 
fragments that each fit within an RDP packet. These messages will have 
increasing sequence numbers and will all have an ACK number corresponding to the
GET request packet. All of these messages with have PACKET_TYPE = APP.

The client will send ACK messages for each received DATA packet, and the server
will wait until an ACK is received before sending the next DATA packet. If an 
ACK is not received in a set timeout, the server will re-transmit the last sent
packet. If a number of retransmissions occur for a single packet, the server 
will consider the connection lost.

### Connection Release

Once the server has received an ACK for the final DATA packet for the HTTP 
response, it will send a FIN packet.

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