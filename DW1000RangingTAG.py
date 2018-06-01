"""
This python script is used to configure the DW1000 chip as a tag for ranging functionalities. It must be used in conjunction with the RangingAnchor script. 
It requires the following modules: DW1000, DW1000Constants and monotonic.
"""

import json
import DW1000
import monotonic
import DW1000Constants as C
from DW1000Device import DW1000Device

import socket
from DW1000Device import DW1000Device

"""
Stores the timestamp when the device was last active
Note this timestamp is the host device's timestamp and
differs from that received from DW1000
""" 
lastActivity = 0

"""
Length of data = max(n_tags + 5, )
Length of data in bytes 2x5 for 2 timestamps and 5 bytes for things like
1. Message type
2. Sender ID
3. Receiver ID
4. Type of sender device
5. Sequence number 
"""
LEN_DATA = 20
data = [0] * LEN_DATA

MY_ADDRESS = 12 # gitignore

"""
Contains the DW1000Device objects of type TAG. 
Stored as key val pairs key = device address, val = <DW1000Device object> 
"""
anchorList = {}


"""
Current Device's Address
Has to be unique across all devices
TODO: Implement address as the host device's IP address
"""

"""
The type of node this device is:
TAG     = 0
ANCHOR  = 1
"""
NODE_TYPE = 0

"""
Indices of data hold the following values. Feel free to change them.
1. message type
2. sender address
3. receiver address
4. device type of the sender
5. sequence number
"""
INDEX_MSGTYPE       = 0
INDEX_SENDER        = LEN_DATA - 4
INDEX_RECEIVER      = LEN_DATA - 3
INDEX_DEVICETYPE    = LEN_DATA - 2
INDEX_SEQUENCE      = LEN_DATA - 1
INDEX_POLL_SENT_TS  = 1
INDEX_POLL_ACKR_TS  = 6
INDEX_RNGE_SENT_TS  = 11

"""
Socket object that listens to the main server for this node's activation
"""
listenerSocket      = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
HOST                = "10.2.24.65"
PORT                = 9999
BYTES_TO_RECEIVE    = 15

"""
Current sequence for which the data is received
"""
currentSequence     = 0

"""
To maintain Polling frequency
"""

lastPoll = 0
REPLY_DELAY_TIME_US = 7000


def millis():
    """
    This function returns the value (in milliseconds) of a clock which never goes backwards. It detects the inactivity of the chip and
    is used to avoid having the chip stuck in an undesirable state.
    """
    return int(round(monotonic.monotonic()*C.MILLISECONDS))


def getDetailsFromPacket(packet):
    return packet[INDEX_MSGTYPE], packet[INDEX_SENDER], packet[INDEX_RECEIVER]\
            , packet[INDEX_DEVICETYPE], packet[INDEX_SEQUENCE]


def noteActivity():
    """
    This function records the time of the last activity so we 
    can know if the device is inactive or not.
    """
    global lastActivity
    lastActivity = millis()


def filterData(data):
    global anchorList,addresses
    sender_in_list = 0
    msgType, sender, receiver, deviceType, sequence = getDetailsFromPacket(data)

    if receiver != MY_ADDRESS:
        return False, None

    # check if the expectedMessage for that sender is the same in the packet
    if msgType != anchorList[sender].expectedMessage:
        return False, None
   
    # check if data packet's sequence number is correct
    if sequence != anchorList[sender].sequenceNumber:
        return False, None

    # this check also looks after the fact that this device doesn't 
    # accept messages from the same kind of device
    if deviceType == NODE_TYPE:
        return None, None
    
    # check if data packet was for us
    # if all checks passes then return true and (msgType, sender, ...)
    
    return True, (msgType, sender, receiver, deviceType, sequence)




def handleSent():
    """
    This is a callback called from the module's interrupt handler when 
    a transmission was successful.
    """
    global data, anchorList, listenerSocket

    msgType     = data[INDEX_MSGTYPE]
    sequence    = data[INDEX_SEQUENCE]
    if msgType == C.POLL:
        noteActivity()
        listenerSocket.send("DONE")
    if msgType == C.RANGE:
        noteActivity()
        listenerSocket.send("DONE")

def handleReceived():
    """
    This is a callback called from the module's interrupt handler when a 
    reception was successful.
    """
    global currentSequence, data, anchorList

    print "Received Something"
    data = DW1000.getData(LEN_DATA)
    isDataGood, details = filterData(data)
    msgType, sender, receiver, deviceType, sequence = details
    if not isDataGood:
        DW1000.clearReceiveStatus()
        return
    currentAnchor = anchorList[sender]

    if msgType == C.POLL_ACK:
        if sequence != currentSequence:
            return
        currentAnchor.sequenceNumber = currentSequence
        currentAnchor.timePollAckReceived[currentSequence] = DW1000.getReceiveTimestamp()
        currentAnchor.expectedMessage = C.RANGE_REPORT
    noteActivity()
    DW1000.clearReceiveStatus()


def transmitPoll(address=0xFF) :
    global data,lastPoll,currentSequence, anchorList
    DW1000.newTransmit()
    data[INDEX_MSGTYPE]     = C.POLL
    data[INDEX_SENDER]      = MY_ADDRESS
    data[INDEX_RECEIVER]    = address 
    # Poll in this current method is always for all the devices.!!
    data[INDEX_DEVICETYPE]  = NODE_TYPE
    data[INDEX_SEQUENCE]    = currentSequence
    DW1000.setData(data,LEN_DATA)
    DW1000.startTransmit()


def transmitRange(address) : 
    global data, currentSequence, anchorList
    DW1000.newTransmit()
    data[INDEX_MSGTYPE]     = C.RANGE
    data[INDEX_SENDER]      = MY_ADDRESS
    data[INDEX_RECEIVER]    = address
    data[INDEX_SEQUENCE]    = currentSequence
    data[INDEX_DEVICETYPE]  = NODE_TYPE
    currentAnchor = anchorList[address] 
    currentAnchor.timeRangeSent[currentSequence] = DW1000.setDelay(REPLY_DELAY_TIME_US, C.MICROSECONDS)
    DW1000.setTimeStamp(data, currentAnchor.timePollSent[currentSequence], INDEX_POLL_SENT_TS)
    DW1000.setTimeStamp(data, currentAnchor.timePollAckReceived[currentSequence], INDEX_POLL_ACKR_TS)
    DW1000.setTimeStamp(data, currentAnchor.timeRangeSent[currentSequence], INDEX_RNGE_SENT_TS)

    DW1000.setData(data,LEN_DATA)
    DW1000.startTransmit()


def startReceiver():
    """
    This function configures the chip to prepare for a message reception.
    """
    global data
    print "Initializing Receiver"
    DW1000.newReceive()
    DW1000.startReceive()


def listenForActivation():
    global currentSequence, listenerSocket

    while True:
        message = listenerSocket.recv(BYTES_TO_RECEIVE)
        currentSequence, flag, node_address = message.split()
        currentSequence = int(currentSequence)
        if   flag == "SENDPOLL":
            transmitPoll() # Poll all devices (Note: address not passed)
        elif flag == "SENDPACK":
            startReceiver()
        elif flag == "RANGE":
            tag_address, anchor_address = map(int, node_address.split(','))
            if tag_address == MY_ADDRESS:
                transmitRange(anchor_address)


def populateNodes(nodes):
    global anchorList

    for node in nodes:
        anchorList[node["id"]] = DW1000Device(node["id"], 1)


if __name__ == "__main__":
    try:
        PIN_IRQ = 19
        PIN_SS = 16
        DW1000.begin(PIN_IRQ)
        DW1000.setup(PIN_SS)
        DW1000.generalConfiguration("82:17:5B:D5:A9:9A:E2:9C", C.MODE_LONGDATA_FAST_ACCURACY)
        DW1000.registerCallback("handleSent", handleSent)
        DW1000.registerCallback("handleReceived", handleReceived)
        DW1000.setAntennaDelay(C.ANTENNA_DELAY_RASPI)

        configData = open("config.json", "r").read()
        populateNodes(json.loads(configData)["ANCHORS"])
        listenerThread = threading.Thread(target=listenForActivation)
        listenerThread.start()
        listenerSocket.connect((HOST, PORT))
        noteActivity()

    except KeyboardInterrupt:
        print "Shutting Down."
        DW1000.close()
