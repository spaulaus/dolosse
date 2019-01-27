"""
file: list_mode_data_decoder.py
brief: Decodes binary data produced by an XIA Pixie16 module
author: S. V. Paulauskas
date: January 17, 2019
"""
from functools import partial
import struct
import threading
import psycopg2

import constants.data as data


class ListModeDataDecoder(threading.Thread):
    """
    Class that loops through a data stream to locate and process Pixie16
    list mode data.
    """

    def __init__(self, stream, mask, db_connection, table):
        """
        Constructor
        :param stream: The stream that we'll read data from
        :param mask: the data mask that we'll use to decode data
        :param db_connection: the database connection for us to put data into
        :param table: the table name storing raw data.
        """
        threading.Thread.__init__(self)
        self.stream = stream
        self.mask = mask
        if db_connection:
            self.db_connection = db_connection
            self.cursor = db_connection.cursor()
        else:
            raise ConnectionError("Database connection could not be established during decoding!")
        self.table = table
        self.finished = False

    def run(self):
        """ Decodes data from Pixie16 binary data stream """
        inserts = ""
        for chunk in iter(partial(self.stream.read, data.WORD), b''):
            word0 = struct.unpack('I', chunk)[0]
            word1 = struct.unpack('I', self.stream.read(data.WORD))[0]
            word2 = struct.unpack('I', self.stream.read(data.WORD))[0]
            word3 = struct.unpack('I', self.stream.read(data.WORD))[0]

            decoded_data = {
                'channel': (word0 & self.mask.channel()[0]) >> self.mask.channel()[1],
                'slot': (word0 & self.mask.slot()[0]) >> self.mask.slot()[1],
                'crate': (word0 & self.mask.crate()[0]) >> self.mask.crate()[1],
                'header_length': (word0 & self.mask.header_length()[0]) >>
                                 self.mask.header_length()[1],
                'event_length': (word0 & self.mask.event_length()[0]) >>
                                self.mask.event_length()[1],
                'finish_code': (word0 & self.mask.finish_code()[0]) >> self.mask.finish_code()[1],
                'event_time_low': word1,
                'event_time_high': (word2 & self.mask.event_time_high()[0]) >>
                                   self.mask.event_time_high()[1],
                'cfd_fractional_time': (word2 & self.mask.cfd_fractional_time()[0]) >>
                                       self.mask.cfd_fractional_time()[1],
                'cfd_trigger_source_bit': (word2 & self.mask.cfd_trigger_source()[0]) >>
                                          self.mask.cfd_trigger_source()[1],
                'cfd_forced_trigger_bit': (word2 & self.mask.cfd_forced_trigger()[0]) >>
                                          self.mask.cfd_forced_trigger()[1],
                'energy': (word3 & self.mask.energy()[0]) >> self.mask.energy()[1],
                'trace_length': (word3 & self.mask.trace_length()[0])
                                >> self.mask.trace_length()[1],
                'trace_out_of_range': (word3 & self.mask.trace_out_of_range()[0])
                                      >> self.mask.trace_out_of_range()[1]
            }
            if decoded_data['trace_length'] == 32768:
                decoded_data['trace_length'] = 0
            inserts += "INSERT INTO %s VALUES(" % self.table
            inserts += "%(crate)s, %(slot)s, %(channel)s, %(header_length)s, " % decoded_data
            inserts += "%(event_length)s, '%(finish_code)s', %(event_time_low)s, " % decoded_data
            inserts += "%(event_time_high)s, %(cfd_fractional_time)s, " % decoded_data
            inserts += "'%(cfd_trigger_source_bit)s', '%(cfd_forced_trigger_bit)s', " % decoded_data
            inserts += "%(energy)s, %(trace_length)s, '%(trace_out_of_range)s'); " % decoded_data

        self.cursor.execute(inserts)
        self.db_connection.commit()
        self.finished = True