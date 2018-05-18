"""
This python script is used to configure the DW1000 chip as a tag for ranging functionalities. It must be used in conjunction with the RangingAnchor script. 
It requires the following modules: DW1000, DW1000Constants and monotonic.
"""


import DW1000
import monotonic
import DW1000Constants as C
from DW1000Device import DW1000Device

LEN_DATA = 20
data = [0] * LEN_DATA
lastActivity = 0
lastPoll = 0
sentAck = False
receivedAck = False
timePollSentTS = 0
timeRangeSentTS = 0
timePollAckReceivedTS = 0
REPLY_DELAY_TIME_US = 7000
# The polling range frequency defines the time interval between every distance poll in milliseconds. Feel free to change its value. 
POLL_RANGE_FREQ = 100 
# the distance between the tag and the anchor will be estimated every second.
# NOTE: I changed the value in the contant file ;)
expectedMsgId = {}
anchor_list = {}
# Address of this Device... Every device needs a unique adderss
# NOTE: Tags and anchors cannot have the same address
myAddress = 0 
SEQ_NO = 0

def millis():
    """
    This function returns the value (in milliseconds) of a clock which never goes backwards. It detects the inactivity of the chip and
    is used to avoid having the chip stuck in an undesirable state.
    """
    return int(round(monotonic.monotonic()*C.MILLISECONDS))


def handleSent():
    """
    This is a callback called from the module's interrupt handler when a transmission was successful. 
    It sets the sentAck variable as True so the loop can continue.
    """        
    global sentAck
    sentAck = True


def handleReceived():
    """
    This is a callback called from the module's interrupt handler when a reception was successful. 
    It sets the received receivedAck as True so the loop can continue.
    """            
    global receivedAck
    receivedAck = True

def receiver():
    """
    This function configures the chip to prepare for a message reception.
    """    
    DW1000.newReceive()
    DW1000.receivePermanently()
    DW1000.startReceive()


def noteActivity():
    """
    This function records the time of the last activity so we can know if the device is inactive or not.
    """    
    global lastActivity
    lastActivity = millis()


def resetInactive():
    """
    This function restarts the default polling operation when the device is deemed inactive.
    """
    global expectedMsgId
    print("Reset inactive")	
    for i in expectedMsgId.keys():
        expectedMsgId[i] = C.POLL_ACK
    transmitPoll()
    noteActivity()


def transmitPoll(address=0xFF):
    """
    This function sends the polling message which is the first transaction to enable ranging functionalities. 
    It checks if an anchor is operational.
    """    
    global data, lastPoll, SEQ_NO
    #print "polling"
    while (millis() - lastPoll < POLL_RANGE_FREQ):
        pass
    DW1000.newTransmit()
    data[0] = C.POLL
    data[16] = myAddress
    data[17] = address
    data[18] = SEQ_NO
    SEQ_NO += 1
    DW1000.setData(data, LEN_DATA)
    DW1000.startTransmit()
    lastPoll = millis()


def transmitRange(address):
    """
    This function sends the range message containing the timestamps used to calculate the range between the devices.
    """
    global data, timeRangeSentTS, SEQ_NO
    #print "transmitting range"
    DW1000.newTransmit()
    data[0] = C.RANGE
    data[16] = myAddress
    data[17] = address
    data[18] = SEQ_NO
    SEQ_NO += 1
    anchor_list[address].timeRangeSentTS = DW1000.setDelay(REPLY_DELAY_TIME_US, C.MICROSECONDS)
    DW1000.setTimeStamp(data, anchor_list[address].timePollSent, 1)
    DW1000.setTimeStamp(data, anchor_list[address].timePollAckReceived, 6)
    DW1000.setTimeStamp(data, anchor_list[address].timeRangeSent, 11)
    DW1000.setData(data, LEN_DATA)
    DW1000.startTransmit()


def addAnchor(address):
    global anchor_list, expectedMsgId

    anchor_list[address] = DW1000Device(address, DW1000Device.ANCHOR)
    expectedMsgId[address] = C.POLL_ACK


def loop():
    global sentAck, receivedAck, data, timePollAckReceivedTS, timePollSentTS, timeRangeSentTS, expectedMsgId, anchor_list, myAddress

    if (sentAck == False and receivedAck == False):
        if ((millis() - lastActivity) > C.RESET_PERIOD):
            resetInactive()
        return

    if sentAck:
        sentAck = False
        msgID = data[0]      
        if msgID == C.POLL:
            # Check if broadcast message
            if data[17] != 0xFF:
                print "Sending poll to {}".format(data[17])
                anchor_list[data[17]].timePollSentTS    = DW1000.getTransmitTimestamp()
            noteActivity()
        elif msgID == C.RANGE:
            print "Range message sent to {}".format(data[17])
            anchor_list[data[17]].timeRangeSentTS   = DW1000.getTransmitTimestamp()
            noteActivity()

    if receivedAck:
        receivedAck = False
        data = DW1000.getData(LEN_DATA)
        msgID       = data[0]
        sender      = data[16]
        receiver    = data[17]
        # Check if sender is in anchor_list or not 
        if sender not in anchor_list:
            print "Adding {} to anchor list".format(sender)
            # Add anchor to anchor_list
            addAnchor(sender)
            transmitPoll(sender)
            print anchor_list
            # Now Expecting a POLL_ACK from the added anchor
        else:
            # Check if message was intended for this TAG or not
            if receiver != myAddress:
                print "Message wasn't for me :("
                # Message wasn't for this tag, so we will ignore this 
                return
            else:
                # Message was meant for us 
                if msgID != expectedMsgId[sender]:
                    print "MessageID not expected :( got {} expected {}".format(msgID, expectedMsgId[sender])
                    # Message ID received wasn'nt what we expected so resetting
                    expectedMsgId[sender] = C.POLL_ACK
                    transmitPoll(sender)
                    return
                # Message ID is what we expected
                if msgID == C.POLL_ACK:
                    print "Got poll ACK"
                    anchor_list[sender].timePollAckReceived = DW1000.getReceiveTimestamp()
                    expectedMsgId[sender] = C.RANGE_REPORT
                    transmitRange(sender)
                    noteActivity()
                elif msgID == C.RANGE_REPORT:
                    print "Got Range report"
                    expectedMsgId[sender] = C.POLL_ACK
                    transmitPoll(sender)
                    noteActivity()
                elif msgID == C.RANGE_FAILED:
                    print "range failed"
                    expectedMsgId[sender] = C.POLL_ACK
                    transmitPoll(sender)
                    noteActivity()


try:
    PIN_IRQ = 19
    PIN_SS = 16
    DW1000.begin(PIN_IRQ)
    DW1000.setup(PIN_SS)
    # print("DW1000 initialized")
    # print("############### TAG ##############")	

    DW1000.generalConfiguration("7D:00:22:EA:82:60:3B:9C", C.MODE_LONGDATA_FAST_ACCURACY)
    DW1000.registerCallback("handleSent", handleSent)
    DW1000.registerCallback("handleReceived", handleReceived)
    DW1000.setAntennaDelay(C.ANTENNA_DELAY_RASPI)

    receiver()
    transmitPoll()
    noteActivity()
    while 1:
        loop()

except KeyboardInterrupt:
    DW1000.close()
