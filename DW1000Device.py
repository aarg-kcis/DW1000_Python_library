import DW1000
class DW1000Device:
    TAG = 0
    ANCHOR = 1
    def __init__(self, address, type_of_tag):
        self.address                = address
        self.type                   = type_of_tag
        self.is_inactive            = False
        self.timePollSent           = {}
        self.timePollAckReceived    = {}
        self.timePollAckSent        = {}
        self.timePollReceived       = {}
        self.sequenceNumber         = 0
        self.data                   = []
        self.expectegMessage        = C.POLL if (self.type == ANCHOR) else C.POLL_ACK
        self.timestamps             = [ self.timePollSent, self.timePollAckReceived, \
                                        self.timePollAckSent, self.timePollReceived]

    def deletePreviousSequenceData(self):
        for i in self.timestamps:
            for j in i.keys():
                if j != self.sequenceNumber-1:
                    del i[j]

    def getRange(self):
        assert self.type == DW1000Device.ANCHOR, \
                            "Tags are not equipped to find distance from anchors"
        round1 = DW1000.wrapTimestamp(self.timePollAckReceived[self.sequenceNumber] - \
                                        self.timePollSent[self.sequenceNumber])
        reply1 = DW1000.wrapTimestamp(self.timePollAckSent[self.sequenceNumber] - \
                                        self.timePollReceived[self.sequenceNumber])
        self.deletePreviousSequenceData()
        range = (round1 - reply1) / 2
        return (range % C.TIME_OVERFLOW) * C.DISTANCE_OF_RADIO

    def is_inactive(self):
        return is_inactive

    def activate(self):
        self.is_inactive = False

    def deactivate(self):
        self.is_inactive = True

    def incrementSequenceNumber(self):
        self.sequenceNumber += 1
        self.sequenceNumber = self.sequenceNumber%256

    def __str__(self):
        return \
        """address: {}\n   
        type: {}
        is_inactive: {}
        timePollSent: {}
        timePollReceived: {} 
        timePollAckSent: {} 
        timePollAckReceived: {}
        sequenceNumber: {} """\
        .format(self.address, self.type, self.is_inactive, self.timePollSent, \
                self.timePollReceived, self.timePollAckSent, self.timePollAckReceived, \
                self.sequenceNumber)