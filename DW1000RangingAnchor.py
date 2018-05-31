"""
This python script is used to configure the DW1000 chip as an anchor 
for ranging functionalities. 
It must be used in conjunction with the RangingTAG script.
It requires the following modules: DW1000, DW1000Constants and monotonic.
"""


import DW1000
import socket
import monotonic
import threading
import DW1000Constants as C
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
LEN_DATA = 15
data = [0] * LEN_DATA

"""
Contains the DW1000Device objects of type TAG. 
Stored as key val pairs key = device address, val = <DW1000Device object> 
"""
tagList = {}


"""
Current Device's Address
Has to be unique across all devices
TODO: Implement address as the host device's IP address
"""
MY_ADDRESS = 1

"""
The type of node this device is:
TAG     = 0
ANCHOR  = 1
"""
NODE_TYPE = 1

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

"""
Socket object that listens to the main server for this node's activation
"""
listenerSocket      = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
HOST                = "10.2.24.65"
PORT                = 9999
BYTES_TO_RECEIVE    = 8

"""
Current sequence for which the data is received
"""
currentSequence     = 0


def getDetailsFromPacket(packet):
    return packet[INDEX_MSGTYPE], packet[INDEX_SENDER], packet[INDEX_RECEIVER]\
            , packet[INDEX_DEVICETYPE], packet[INDEX_SEQUENCE]

def millis():
    """
    This function returns the value (in milliseconds) of a clock 
    which never goes backwards. 
    It detects the inactivity of the chip and
    is used to avoid having the chip stuck in an undesirable state.
    """
    return int(round(monotonic.monotonic() * C.MILLISECONDS))

def noteActivity():
    """
    This function records the time of the last activity so we 
    can know if the device is inactive or not.
    """
    global lastActivity
    lastActivity = millis()


def handleSent():
    """
    This is a callback called from the module's interrupt handler when 
    a transmission was successful.
    """
    global sentAck
    sentAck = True


def handleReceived():
    """
    This is a callback called from the module's interrupt handler when a 
    reception was successful.
    """
    print "Received Something"
    data = DW1000.getData(LEN_DATA)
    isDataGood, details = filterData(data)
    msgType, sender, receiver, deviceType, sequence = details
    if not isDataGood:
        DW1000.clearReceiveStatus()
        return
    currentTag = tagList[sender]

    if msgType == C.POLL:
        if sequence != currentSequence:
            return
        currentTag.sequenceNumber = currentSequence
        currentTag.timePollReceived[currentSequence] = DW1000.getReceiveTimestamp()
        currentTag.expectedMessage = C.RANGE
    if msgType == C.RANGE:
        currentTag.timeRangeReceived[currentSequence] = DW1000.getReceiveTimestamp()
        expectedMsgId[sender] = C.POLL
        range = currentTag.getRange()
        print "Range {1:4.2}m".format(range)

    noteActivity()
    DW1000.clearReceiveStatus()

def filterData(data):
    global tagList
    msgType, sender, receiver, deviceType, sequence = getDetailsFromPacket(data)

    # check if data packet was for us
    if receiver != MY_ADDRESS:
        return False, None

    # check if the expectedMessage for that sender is the same in the packet
    if msgType != tagList[sender].expectedMessage:
        return False, None
   
    # check if data packet's sequence number is correct

    if sequence < tagList[sender].sequenceNumber:
        return

    # check if data packet's sender is in tagList
    # this check also looks after the fact that this device doesn't 
    # accept messages from the same kind of device
    if deviceType == NODE_TYPE:
        return None, None
    
    # if all checks passes then return true and (msgType, sender, ...)
    return True, (msgType, sender, receiver, deviceType, sequence)


def resetInactive():
    """
    This function restarts the default polling operation when the device is deemed inactive.
    """
    global expectedMsgId
    print("Reset inactive")
    for i in expectedMsgId.keys():
        expectedMsgId[i] = C.POLL
    receiver()
    noteActivity()


def transmitPollAck(addresses):
    """
    This function sends the polling acknowledge message which is used to 
    confirm the reception of the polling message. 
    """
    DW1000.newTransmit()
    data[INDEX_DEVICETYPE]      = NODE_TYPE
    data[INDEX_RECEIVER]        = receiver
    data[INDEX_MSGTYPE]         = C.POLL_ACK
    data[INDEX_SENDER]          = MY_ADDRESS
    data[INDEX_SEQUENCE]        = currentSequence
    # put the addresses of all the tags that this anchor received the poll from
    data[1: len(addresses)+1]   = addresses
    # uncomment this is getting wierd results !! Dunno what it does..!
    # DW1000.setDelay(REPLY_DELAY_TIME_US, C.MICROSECONDS)
    DW1000.setData(data, LEN_DATA)
    DW1000.startTransmit()


def transmitRangeAcknowledge(address):
    """
    This functions sends the range acknowledge message which tells the 
    tag that the ranging function was successful and another ranging transmission can begin.
    """
    global data, myAddress, nodeType
    ##print "transmitRangeAcknowledge"
    DW1000.newTransmit()
    data[0] = C.RANGE_REPORT
    data[16] = myAddress
    data[17] = address
    data[19] = nodeType
    sequence = tag_list[address].sequenceNumber
    DW1000.setTimeStamp(data, tag_list[address].timePollReceived[sequence], 1)
    DW1000.setTimeStamp(data, tag_list[address].timePollAckSent[sequence], 6)
    DW1000.setTimeStamp(data, tag_list[address].timeRangeReceived[sequence], 11)
    DW1000.setData(data, LEN_DATA)
    DW1000.startTransmit()


def transmitRangeFailed(address):
    """
    This functions sends the range failed message which tells the tag that 
    the ranging function has failed and to start another ranging transmission.
    """
    global data, myAddress
    ##print "transmitRangeFailed"
    DW1000.newTransmit()
    data[0] = C.RANGE_FAILED
    data[16] = myAddress
    data[17] = address

    DW1000.setData(data, LEN_DATA)
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
    global currentSequence
    while True:
        message = listenerSocket.recv(BYTES_TO_RECEIVE)
        # if message is for starting a poll by some tag then activate reveiver
        # currentSequence = getSequenceFromMsg(msg)
        # startReceiver()

        # if message is for starting a poll ack then send poll ack message
        # sequence = getSequenceFromMsg(msg)
        # addresses = [i.address for i in tagList.values() if i.sequenceNumber == sequence]
        # addresses = [i for i in tagList if tagList[i].sequenceNumber == sequence]
        # transmitPollAck(addresses)


try:
    PIN_IRQ = 19
    PIN_SS = 16
    DW1000.begin(PIN_IRQ)
    DW1000.setup(PIN_SS)
    DW1000.generalConfiguration("82:17:5B:D5:A9:9A:E2:9C", C.MODE_LONGDATA_FAST_ACCURACY)
    DW1000.registerCallback("handleSent", handleSent)
    DW1000.registerCallback("handleReceived", handleReceived)
    DW1000.setAntennaDelay(C.ANTENNA_DELAY_RASPI)
    listenerThread = threading.Thread(target=listenForActivation)
    listenerThread.start()
    listenerSocket.connect((HOST, PORT))
    noteActivity()

except KeyboardInterrupt:
    print "Shutting Down."
    DW1000.close()
