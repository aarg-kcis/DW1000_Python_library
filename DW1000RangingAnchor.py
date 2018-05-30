"""
This python script is used to configure the DW1000 chip as an anchor 
for ranging functionalities. 
It must be used in conjunction with the RangingTAG script.
It requires the following modules: DW1000, DW1000Constants and monotonic.
"""


import DW1000
import monotonic
import DW1000Constants as C
from DW1000Device import DW1000Device

"""
Stores the timestamp when the device was last active
Note this timestamp is the host device's timestamp and
differs from that received from DW1000
""" 
lastActivity = 0

"""     
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
myAddress = 1

"""
The type of node this device is:
TAG     = 0
ANCHOR  = 1
"""
nodeType = 1

"""
Indices of data hold the following values. Feel free to change them.
1. message type
2. sender address
3. receiver address
4. device type of the sender
5. sequence number of the data
"""
INDEX_MSGTYPE       = 0
INDEX_SENDER        = LEN_DATA - 4
INDEX_RECEIVER      = LEN_DATA - 3
INDEX_DEVICETYPE    = LEN_DATA - 2
INDEX_SEQUENCE      = LEN_DATA - 1


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
    if not isDataGood:
        return

    DW1000.clearReceiveStatus()

def filterData(data):
    global tagList
    msgType, sender, receiver, deviceType, sequence = getDetailsFromPacket(data)
    


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


def transmitPollAck(address):
    """
    This function sends the polling acknowledge message which is used to 
    confirm the reception of the polling message. 
    """        
    global data, myAddress, nodeType
    print "transmitPollAck"
    DW1000.newTransmit()
    data[0] = C.POLL_ACK
    data[16] = myAddress
    data[17] = address
    data[19] = nodeType
    DW1000.setDelay(REPLY_DELAY_TIME_US, C.MICROSECONDS)
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


def addTag(address):
    global tag_list, expectedMsgId

    tag_list[address] = DW1000Device(address, DW1000Device.TAG)
    expectedMsgId[address] = C.POLL


def loop():
    global sentAck, receivedAck, timePollAckSentTS, timePollReceivedTS, timePollSentTS, timePollAckReceivedTS, timeRangeReceivedTS, protocolFailed, data, expectedMsgId, timeRangeSentTS, tag_list, myAddress, nodeType

    if (sentAck == False and receivedAck == False):
        if ((millis() - lastActivity) > C.RESET_PERIOD):
            resetInactive()
        return

    if sentAck:
        sentAck = False
        msgId = data[0]
        tag = tag_list[data[17]]
        sequence = data[18]
        if msgId == C.POLL_ACK:
            print "Sending poll ack to {}".format(data[17])
            tag.timePollAckSent[sequence] = DW1000.getTransmitTimestamp()
            noteActivity()
        if msgId == C.RANGE_REPORT:
            print "Sending Range Report to {}".format(data[17])
            noteActivity()

    if receivedAck:
        print "received something"
        receivedAck = False
        datatmp = DW1000.getData(LEN_DATA)
        msgId           = datatmp[0]
        sender          = datatmp[16]
        receiver        = datatmp[17]
        typeOfSender    = datatmp[19]

        if nodeType == typeOfSender:
            print "message from Anchor..ignore "
            # print nodeType, typeOfSender
            # Only accept packets from tags
            # ignore packets from anchors...
            return
        if sender not in tag_list:
            print "Adding {} to tag list".format(sender)
            data = datatmp[:]
            # print data
            # Add tag to tag_list
            addTag(sender)
            # Send a dummy POLL_ACK so that the tag can add this anchor to its list and send data.
            transmitPollAck(sender)
            print tag_list
        else:
            if receiver == 0xFF:
                print "Ignoring Broadcast Message by {}".format(sender)
                transmitPollAck(sender)
                return
            if receiver != myAddress:
                print "Message was for {} :(".format(receiver)
                print "expecting {}".format(expectedMsgId)
                # Message wasn't meant for us
                return
            # elif receiver == 0xFF:
            #     print "receiving broadcast message..!!"
            #     resetInactive()
            else:
                data = datatmp[:]
                # print data
                if msgId != expectedMsgId[sender]:
                    print "MessageID not expected :( got {} expected {}".format(msgId, expectedMsgId[sender])
                    print "protocolFailed"
                    protocolFailed = True
                tag = tag_list[sender]
                sequence = data[18]
                if msgId == C.POLL:
                    tag.sequenceNumber = sequence
                    print "Got poll for sequence", sequence
                    protocolFailed = False
                    tag.timePollReceived[sequence] = DW1000.getReceiveTimestamp()
                    expectedMsgId[sender] = C.RANGE
                    transmitPollAck(sender)
                    noteActivity()
                if msgId == C.RANGE:
                    print "Got Range report for sequence" , sequence
                    tag.timeRangeReceived[sequence] = DW1000.getReceiveTimestamp()
                    expectedMsgId[sender] = C.POLL
                    if protocolFailed == False:
                        # tag.timePollSent[sequence] = DW1000.getTimeStamp(data, 1)
                        # tag.timePollAckReceived[sequence] = DW1000.getTimeStamp(data, 6)
                        # tag.timeRangeSent[sequence] = DW1000.getTimeStamp(data, 11)
                        # print tag
                        transmitRangeAcknowledge(sender)
                        expectedMsgId[sender] = C.POLL

                        # distance = (tag_list[sender].getRange() % C.TIME_OVERFLOW) * C.DISTANCE_OF_RADIO
                        # print("Distance: %.2f m" %(distance))

                    else:
                        print "range failed"
                        transmitRangeFailed(sender)

        noteActivity()

try:
    PIN_IRQ = 19
    PIN_SS = 16
    DW1000.begin(PIN_IRQ)
    DW1000.setup(PIN_SS)
    DW1000.generalConfiguration("82:17:5B:D5:A9:9A:E2:9C", C.MODE_LONGDATA_FAST_ACCURACY)
    DW1000.registerCallback("handleSent", handleSent)
    DW1000.registerCallback("handleReceived", handleReceived)
    DW1000.setAntennaDelay(C.ANTENNA_DELAY_RASPI)
    receiver()
    noteActivity()
except KeyboardInterrupt:
    print "Shutting Down."
    DW1000.close()
