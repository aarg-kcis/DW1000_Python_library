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
        assert self.type == TAG, "Tags are not equipped to find distance from anchors"
        round1 = DW1000.wrapTimestamp(self.timePollAckReceived - self.timePollSent)
        reply1 = DW1000.wrapTimestamp(self.timePollAckSent - self.timePollReceived)
        round2 = DW1000.wrapTimestamp(self.timeRangeReceived - self.timePollAckSent)
        reply2 = DW1000.wrapTimestamp(self.timeRangeSent - timePollAckReceived)
        return (round1 * round2 - reply1 * reply2) / (round1 + round2 + reply1 + reply2)

    def is_inactive(self):
        return is_inactive

    def activate(self):
        self.is_inactive = False

    def deactivate(self):
        self.is_inactive = True

    def incrementSequenceNumber(self):
        self.sequenceNumber += 1
