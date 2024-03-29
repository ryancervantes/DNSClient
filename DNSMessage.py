#! /usr/bin/python3
"""
Filename: DNSMessage.py
Authors: Ryan Cervantes (rxc3202), Daniel Osvath (do3477)
"""

from enum import Enum


class QR(Enum):
    QUERY = 0
    RESPONSE = 1


class OPCODE(Enum):
    QUERY = 0
    IQUERY = 1
    STATUS = 2
    NOTIFY = 4
    UPDATE = 5


class RCODE(Enum):
    NO_ERROR = 0
    FORMAT_ERROR = 1
    SERVER_FAILURE = 2
    NAME_ERROR = 3
    NOT_IMPLEMENTED = 4
    REFUSED = 5
    YX_DOMAIN = 6
    YX_RR_SET = 7
    NX_RR_SET = 8
    NOT_AUTH = 9
    NOT_ZONE = 10


class QTYPE(Enum):
    A = 1
    NS = 2
    CNAME = 5
    SOA = 6
    MX = 15
    TXT = 16
    AAAA = 28


class Message():
    """ All values stored as byte arrays in big endian"""

    def __init__(self):
        self.identifier = bytearray(2)
        self.flags = bytearray(2)
        self.QDCount = bytearray(2)
        self.ANCount = bytearray(2)
        self.NSCount = bytearray(2)
        self.ARCount = bytearray(2)
        self.questions = []
        self.records = []

    """
    Will parse a pointer to a label if it is in DNS name notation

    @args offset:   the number representing offset in the packet
                    where the label is stored as a bytearry[2]
                    a bytes object of size 2 or an integer
    """

    def _domain_from_pointer(self, label_offset):
        if isinstance(label_offset, bytearray) or isinstance(label_offset, bytes):
            offset = Message.int_to_net(label_offset[0] & 63, 1) + \
                     Message.int_to_net(label_offset[1], 1)
            offset = Message.net_to_int(offset)
            data = self._domain_from_label(self.encode()[offset:], 0)
            return data
        else:
            data = self._domain_from_label(self.encode()[label_offset:], 0)
            return data

    """
    Will parse a label in the form of a bytearray if it is
    in DNS Name Notation

    @args bytearr: the byte array to parse
    @args offset: the first byte of the label (which is the
                    number of bytes to read next)
    """

    def _domain_from_label(self, bytearr, offset):
        data = b''
        start = offset
        # continue reading each of the domains in the label
        while bytearr[start] != 0:
            if not Message._is_pointer_byte(bytearr[start]):
                end = start + bytearr[start]
                data += bytearr[start + 1:end + 1] + b'.'
                start = end + 1
            else:
                data += self._domain_from_pointer(bytearr[start:start + 2])
                break  # a pointer can only end a label
        return bytearray(data)

    """
    Will get the range of bits within a given byte where
    start and end are both inclusive. Byte is given as an int,
    0 indexed
    Bit: 0 0 0 0 0 0 0 0 
    Idx: 7 6 5 4 3 2 1 0 
    """

    @classmethod
    def get_bits(cls, byte, start, end=None):
        end = start if not end else end
        mask = int('11111111', 2)  # to prevent len(int) > 8
        shift = 7 - end
        return ((byte << shift) & mask) >> (start + shift)

    """ Encode an integer into a big endian byte array """

    @classmethod
    def int_to_net(cls, n, byte_length=2):
        return bytearray((n).to_bytes(byte_length, "big"))

    """ Decode a byte array into an integer """

    @classmethod
    def net_to_int(cls, network_bytes):
        return int(network_bytes.hex(), 16)

    """ See if a given byte is a pointer byte """

    @classmethod
    def _is_pointer_byte(cls, byte):
        return Message.get_bits(byte, 6, 7) == Message.get_bits(192, 6, 7)

    """ Decode DNS packet from a bytearray and place fields into this instance """

    def decode(self, bytearr):
        if not isinstance(bytearr, bytearray):
            bytearr = bytearray(bytearr)
        # Get header information
        self.identifier = bytearr[0:2]
        self.flags = bytearr[2:4]
        self.QDCount = bytearr[4:6]
        self.ANCount = bytearr[6:8]
        self.NSCount = bytearr[8:10]
        self.ARCount = bytearr[10:12]
        # Collect Questions 
        questions = []
        start = 12
        for count in range(Message.net_to_int(self.QDCount)):
            end = bytearr.find(b'\x00', start) + 1 + 4  # include the Question Type/ Class
            questions.append(bytearray(bytearr[12:end]))
            start = end
        # Collect Answers
        responses = []
        for count in range(Message.net_to_int(self.ANCount)):
            end = start + 1  # minimum end is next byte (not possible)
            end += 1 + 2 + 2 + 4  # type, class, ttl fields taken into account
            end += Message.net_to_int(bytearr[
                                      end:end + 2]) + 1 + 1  # 1st is \x00 separator, 2nd is to start next
            self.records.append(bytearray(bytearr[start:end]))
            start = end

        self.questions = questions
        self.responses = responses

    """ Encode DNS packet as bytestream to send over network """

    def encode(self):
        payload = b''
        payload += self.identifier
        payload += self.flags
        payload += self.QDCount
        payload += self.ANCount
        payload += self.NSCount
        payload += self.ARCount
        for q in self.questions:
            payload += q
        for r in self.records:
            payload += r
        return payload

    """
    Set ID field for DNS packet 

    @args identifier:   the number used as the ID in the form of an
                        int, bytearray of size 2, or a bytes obj of
                        size 2
    """

    def set_identifier(self, identifier):
        if isinstance(identifier, int):
            self.identifier = Message.int_to_net(identifier)
        elif isinstance(identifier, bytearray):
            self.identifier = identifier
        elif isinstance(identifier, bytes):
            self.identifier = bytearray(identifier)
        else:
            pass
        return self.identifier

    """ 
    Set flags for DNS packet where each flag is named according
    to the following. All set to zero when packet is created

    Query/Response flag     = qr
    Opcode                  = opcode
    Authoritative Answer    = aa
    Truncation Flag         = tc
    Recursion Desired       = rd
    Zero (cant be modifed)  = z
    Response Code           = rcode
    """

    def set_flags(self, qr=0, opcode=0, aa=0, tc=0,
                  ra=0, rd=0, z=0, rcode=0):
        codes = [
            bin(qr)[2:],
            bin(opcode)[2:].zfill(4),
            bin(aa)[2:],
            bin(tc)[2:],
            bin(rd)[2:],
            bin(ra)[2:],
            bin(0)[2:].zfill(3),
            bin(rcode)[2:].zfill(4)
        ]
        flag_string = ""
        for code in codes:
            flag_string += code
        hex_str = int(flag_string, 2).to_bytes(2, "big")
        self.flags = bytearray(hex_str)
        return self.flags

    """
    Modify Question count manually. Will not add any records
    must add those manually afterwards
    
    @args count: the amount of Questions in the packet
    """

    def set_QDCount(self, count):
        self.QDCount = Message.int_to_net(count)

    """
    Modify Answer Record count manually. Will not add any records
    must add those manually afterwards
    
    @args count: the amount of Answer Records in the packet
    """

    def set_ANCount(self, count):
        self.ANCount = Message.int_to_net(count)

    """
    Modify Authority Record count manually. Will not add any records
    must add those manually afterwards

    @args count: the amount of Authority Records in the packet
    """

    def set_NSCount(self, count):
        self.NSCount = Message.int_to_net(count)

    """ 
    Modify Additional Record count manually

    @args count: the new amount of questions in the packet
    """

    def set_ARCount(self, count):
        self.ARCount = Message.int_to_net(count)

    """
    Will add a question to the DNS packet given an FQDN and the
    type of question to be made

    @args qtype: the type of query made (refer to QTYPE enum)
    @return: will return the bytearray representing the question
    """

    def add_question(self, fqdn, qtype=QTYPE.A.value, rsrc_class=1):
        question = bytearray(b'')
        # Generate the Question Name field
        qname = bytearray(b'')
        for domain in fqdn.split("."):
            qname += len(domain).to_bytes(1, "big")
            qname += bytes(domain, 'utf-8')
        qname += bytes([0])  # end the labels
        # qname += bytes((4 - len(qname) % 4))  # pad to nearest word
        question += qname
        # Generate Question Type field
        question += Message.int_to_net(qtype)
        # Generate Question Class field
        question += Message.int_to_net(rsrc_class)
        self.questions.append(question)
        return question

    """
    Will interpret each of the fields as an int (in the 
    case of the flags it will interpret each field as an int)
    and then return a tuple in the order they are found in the
    DNS packet.
    """

    def get_header(self, interpret=False):
        qr = Message.get_bits(self.flags[0], 7)
        opcode = Message.get_bits(self.flags[0], 3, 6)
        aa = Message.get_bits(self.flags[0], 2)
        tc = Message.get_bits(self.flags[0], 1)
        rd = Message.get_bits(self.flags[0], 0)
        ra = Message.get_bits(self.flags[1], 7)
        z = Message.get_bits(self.flags[1], 5, 6)
        rcode = Message.get_bits(self.flags[1], 0, 4)
        return (Message.net_to_int(self.identifier),
                (qr, opcode, aa, tc, rd, ra, z, rcode),
                Message.net_to_int(self.QDCount),
                Message.net_to_int(self.ANCount),
                Message.net_to_int(self.NSCount),
                Message.net_to_int(self.ARCount))

    def get_questions(self, interpret=False):
        pass

    """
    Will parse the responses held in the Answer section of the 
    DNS packet and will return a list of tuples in the following format:
    (name, record_type, record_class, ttl, rsrc_len, rsrc_data) where
    each field is a bytearray
    """

    def get_responses(self, interpret=False):

        # TODO: do swtich statement with dictionary
        def decode_resource(rsrc_data, record_type):
            case = Message.net_to_int(record_type)
            if case == QTYPE.CNAME.value:
                if Message._is_pointer_byte(rsrc_data[0]):
                    return self._domain_from_pointer(rsrc_data[0:2])
                else:
                    return self._domain_from_label(rsrc_data, 0)
            elif case == QTYPE.A.value:
                return rsrc_data
            else:
                pass

        decoded_responses = []
        for record in self.records:
            # if first two bits are turned on, it is a pointer
            if Message._is_pointer_byte(record[0]):
                # the rest of the 2-byte field is an offset
                name = self._domain_from_pointer(record[0:2])
                record_type = record[2:4]
                record_class = record[4:6]
                ttl = record[6:10]
                data_len = record[10:12]
                rsrc_data = record[12:]
                decoded_rsrc = decode_resource(rsrc_data, record_type)
                decoded_responses.append(
                    (name, record_type, record_class, ttl, data_len, decoded_rsrc))
            else:  # its just a regular label
                self._domain_from_label(record, 0)
        return decoded_responses
