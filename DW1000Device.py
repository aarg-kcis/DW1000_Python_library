import DW1000
class DW1000Device:
    TAG = 0
    ANCHOR = 1
    def __init__(self, address, type_of_tag):
        self.address                = address
        self.type                   = type_of_tag
        self.is_inactive            = False
        self.timePollSent           = 0
        self.timeRangeSent          = 0
        self.timePollAckReceived    = 0
        self.timePollAckSent        = 0
        self.timePollReceived       = 0
        self.timeRangeReceived      = 0
        self.sequenceNumber         = 0

    def getRange(self):
        assert self.type == DW1000Device.TAG, "Tags are not equipped to find distance from anchors"
        round1 = DW1000.wrapTimestamp(self.timePollAckReceived - self.timePollSent)
        reply1 = DW1000.wrapTimestamp(self.timePollAckSent - self.timePollReceived)
        round2 = DW1000.wrapTimestamp(self.timeRangeReceived - self.timePollAckSent)
        reply2 = DW1000.wrapTimestamp(self.timeRangeSent - self.timePollAckReceived)
        return (round1 * round2 - reply1 * reply2) / (round1 + round2 + reply1 + reply2)

    def is_inactive(self):
        return is_inactive

    def activate(self):
        self.is_inactive = False

    def deactivate(self):
        self.is_inactive = True

    def incrementSequenceNumber(self):
        self.sequenceNumber += 1

    def __str__(self):
        return """address: {}\n   
        type: {}\n 
        is_inactive: {} \n
        timePollSent: {} \n       
        timeRangeSent: {} \n  
        timePollAckReceived: {} \n   
        timePollAckSent: {}  \n      
        timePollReceived: {} \n   
        timeRangeReceived: {} \n      
        sequenceNumber: {} """.format(self.address, self.type,          
        self.is_inactive,           self.timePollSent,          self.timeRangeSent,         self.timePollAckReceived,        self.timePollAckSent,  
        self.timePollReceived,         self.timeRangeReceived,
        self.sequenceNumber)