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
REPLY_DELAY_TIME_US = 7000
# ALPHA = .000001
# k = 0
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
    if expectedMsgId.keys() == [] :
        print "sas", expectedMsgId.keys(), expectedMsgId.keys()==[]
    	transmitPoll()
    	noteActivity()
    else:
	    for i in expectedMsgId.keys():
	        transmitPoll(i)
	        expectedMsgId[i] = C.POLL_ACK
	    noteActivity()


def transmitPoll(address=0xFF):
    """
    This function sends the polling message which is the first transaction to enable ranging functionalities. 
    It checks if an anchor is operational.
    """    
    global data, lastPoll
    #print "polling"
    while (millis() - lastPoll < POLL_RANGE_FREQ):
        pass
    DW1000.newTransmit()
    data[0] = C.POLL
    data[16] = myAddress
    data[17] = address
    if address != 0XFF:
        data[18] = anchor_list[address].sequenceNumber
    DW1000.setData(data, LEN_DATA)
    DW1000.startTransmit()
    lastPoll = millis()


def transmitRange(address):
    """
    This function sends the range message containing the timestamps used to calculate the range between the devices.
    """
    global data
    #print "transmitting range"
    DW1000.newTransmit()
    data[0] = C.RANGE
    data[16] = myAddress
    data[17] = address
    data[18] = anchor_list[address].sequenceNumber
    anchor_list[address].timeRangeSent[data[18]] = DW1000.setDelay(7000, C.MICROSECONDS)
    DW1000.setTimeStamp(data, anchor_list[address].timePollSent[data[18]], 1)
    DW1000.setTimeStamp(data, anchor_list[address].timePollAckReceived[data[18]], 6)
    DW1000.setTimeStamp(data, anchor_list[address].timeRangeSent[data[18]], 11)
    print anchor_list[address]
    DW1000.setData(data, LEN_DATA)
    DW1000.startTransmit()


def addAnchor(address):
    global anchor_list, expectedMsgId

    anchor_list[address] = DW1000Device(address, DW1000Device.ANCHOR)
    expectedMsgId[address] = C.POLL_ACK


def loop():
    global sentAck, receivedAck, data, expectedMsgId, anchor_list, myAddress, k, ALPHA

    if (sentAck == False and receivedAck == False):
        if ((millis() - lastActivity) > C.RESET_PERIOD):
            resetInactive()
        return

    if sentAck:
        sentAck = False
        msgID = data[0]
        is_brodcast =  data[17] == 0xFF
        if not is_brodcast:
            anchor = anchor_list[data[17]]
            sequence = anchor.sequenceNumber
        if msgID == C.POLL:
            # Check if broadcast message
            if not is_brodcast:
                print "Sending poll to {}".format(data[17])
                anchor.timePollSent[sequence] = DW1000.getTransmitTimestamp()
                print "time poll sent-->",anchor_list[data[17]].timePollSent 
            noteActivity()
        elif msgID == C.RANGE:
            print "Range message sent to {}".format(data[17])
            anchor.timeRangeSentActual[sequence]   = DW1000.getTransmitTimestamp()
            print "time range sent-->",anchor_list[data[17]].timeRangeSentActual[sequence] 
            noteActivity()

    if receivedAck:
        receivedAck = False
        data = DW1000.getData(LEN_DATA)
        msgID       = data[0]
        sender      = data[16]
        receiver    = data[17]
        sequence    = data[18]
        # Check if sender is in anchor_list or not 
        if sender not in anchor_list:
            print "Adding {} to anchor list".format(sender)
            # Add anchor to anchor_list
            addAnchor(sender)
            transmitPoll(sender)
            # print anchor_list
            noteActivity()
            # Now Expecting a POLL_ACK from the added anchor
        else:
            # Check if message was intended for this TAG or not
            if receiver != myAddress:
                print "Message wasn't for me :("
                # Message wasn't for this tag, so we will ignore this 
                returns
            else:
                # Message was meant for us 
                if msgID != expectedMsgId[sender]:
                    print "MessageID not expected :( got {} expected {}".format(msgID, expectedMsgId[sender])
                    # Message ID received wasn'nt what we expected so resetting
                    expectedMsgId[sender] = C.POLL_ACK
                    transmitPoll(sender)
                    return
                # Message ID is what we expected
                anchor = anchor_list[sender]
                if msgID == C.POLL_ACK:
                    print "Got poll ACK"
                    anchor.timePollAckReceived[sequence] = DW1000.getReceiveTimestamp()
                    print "time poll ack received-->",anchor_list[data[16]].timePollAckReceived 
                    expectedMsgId[sender] = C.RANGE_REPORT
                    transmitRange(sender)
                    noteActivity()
                elif msgID == C.RANGE_REPORT:
                    print "Got Range report"
                    # errorInRange = anchor.timeRangeSentActual[sequence] - anchor.timeRangeSent[sequence]
                    # print "errorInRange", errorInRange
                    # k = k + (ALPHA**-1)*errorInRange
                    # print "k : {}, Alpha: {}".format(k, ALPHA)
                    # ALPHA = =
                    anchor.incrementSequenceNumber()
                    expectedMsgId[sender] = C.POLL_ACK
                    anchor.deletePreviousSequenceData()
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
