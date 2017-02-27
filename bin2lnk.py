'''
bin2lnk:
convert binary file to file format used by LnK script

Created on 02/10/2017

@author: lhu
'''

import bellagio.SystemLib.testbed_logging.testbedlog as tblog
from bellagio.SystemLib.TestbedException.BellagioError import BellagioError
import os
from __builtin__ import classmethod


class Bin2Lnk(object):
    '''
    Singleton class to convert binary file
    '''
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    
    _instance = None
    tmp_txt = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Bin2Lnk, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        if self.tmp_txt == None:
            self.tmp_txt = "tmp.txt"
            self.char_size = 2                          #size of a ascii "char"
            self.dp_line_size = 4 * self.char_size      #size of one line dp file
            self.version=102                            #bin2lnk version
            tblog.infoLog("bin2lnk initialization")

    @classmethod
    def getInstance(cls):
        '''
        This will ensure only one time (first) initialization for object. Will be used for UI tool.
        '''
        if not cls._instance:
            cls._instance = Bin2Lnk()
        return cls._instance

    def updateVer(self, ver=102):
        '''
        Update bin2lnk version: 103 is for ROM/FW version > 1.1.04?
        '''
        self.version = ver
        tblog.infoLog("bin2lnk ver: {0}" .format(ver))

    def bin2txt(self, bin_file, txt_file):
        '''
        convert binary to txt file and pad it to 4-byte aligned
            bin_file:   binary file
            txt_file:   swire txt file
        '''
        if not os.path.isfile(bin_file):
            raise BellagioError("bin2lnk could not find binary input!")

        with open(bin_file, "rb") as bin_input, open(txt_file, 'w') as txt_output:
            byte = bin_input.read(1)
            tblog.infoLog("bin2txt {0:02X}" .format(ord(byte)))
            count = 0
            while byte != "":
                line = "{0:02X}" .format(ord(byte))
                txt_output.write(line)
                byte = bin_input.read(1)
                count += 1

            tblog.infoLog("bin2txt size {0}" .format(count))
            if count&0x3:
                for i in range(4 - (count&0x3)):
                    txt_output.write("00")

        bin_input.close()
        txt_output.close()
        tblog.infoLog("binary to txt done!")

    def bin2Dp(self, bin_file, dp_file):
        '''
        convert binary to swire dp downloading file
            bin_file:   binary file
            dp_file:   swire dp file
        '''
        tblog.infoLog("bin2Dp: input-{0} output-{1}" .format(bin_file, dp_file))

        if not os.path.isfile(bin_file):
            raise BellagioError("bin2lnk could not find binary input!")

        self.bin2txt(bin_file, self.tmp_txt);    #convert binary to txt first

        if not os.path.isfile(self.tmp_txt):
            raise BellagioError("bin2lnk failed to generate tmp txt!")

        with open(self.tmp_txt, "r") as txt_input, open(dp_file, 'w') as dp_output:
            '''
            ###8-byte 00 header, no need after v103
            '''
            if self.version < 103:
                for i in range(2):
                    dp_output.write("00000000\n")

            dword = txt_input.read(self.dp_line_size)       #read 4-char per line for DP format
            tblog.infoLog("bin2Dp: {0}" .format(dword))
            count = 0
            while dword != "":
                l = list(dword)
                '''
                ###use big-endian
                '''
                line = "{0}{1}{2}{3}\n" .format(l[6]+l[7], l[4]+l[5], l[2]+l[3], l[0]+l[1])
                dp_output.write(line)
                dword = txt_input.read(self.dp_line_size)
                count += 1
            tblog.infoLog("bin2txt size {0}" .format(count))

        txt_input.close()
        dp_output.close()
        #os.remove(self.tmp_txt)
        tblog.infoLog("binary to dp done!")

if __name__ == "__main__":
    tblog.setDebugMode(True)
    bin2lnk = Bin2Lnk.getInstance()
    bin2lnk.bin2Dp("1.bin", "1.txt")

