'''
LnkScriptMod:
code to generate/manipulate LnK script

Created on 02/01/2017

@author: lhu
'''

import bellagio.SystemLib.testbed_logging.testbedlog as tblog
from bellagio.SystemLib.TestbedException.BellagioError import BellagioError
from bellagio.SystemLib.LnK.bin2lnk import Bin2Lnk
import os
import re
import datetime
from __builtin__ import classmethod

class LnkScriptMod(object):
    '''
    Singleton class to manipulate LnK script xml file
    '''
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    
    _instance = None
    
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LnkScriptMod, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        #default sys file
        self.sys_file = r'A110.11.12_B71214_KN_VQ_SysConfigSWIRE.bin'
        self.sys_txt_file = os.path.splitext(self.sys_file)[0] + r'_32Bit_1ch.txt'
        self.sys_xml_file = r'DP_DL_'+os.path.splitext(self.sys_file)[0] + r'.xml'

        #default fw file
        self.fw_file = r'A110.11.12_B71214_KN_VQ_BoskoAppSWIRE.bin'
        self.fw_txt_file = os.path.splitext(self.fw_file)[0] + r'_32Bit_1ch.txt'
        self.fw_xml_file = r'DP_DL_'+os.path.splitext(self.fw_file)[0] + r'.xml'

        self.sys_xml_template_file = r'FW_DL_DP_SysConfig.xml'
        self.sys_txt_replace = r'SYS_CONFIG.txt'

        self.fw_xml_template_file = r'FW_DL_DP_BoskoApp.xml'
        self.fw_txt_replace = r'BOSKO_FW.txt'

        #control port related script template file
        self.cp_header_file = r'CP_DL_header.xml'
        self.cp_content_file = r'CP_DL_content.xml'
        self.cp_dl_sys_file = r'CP_DL_' + os.path.splitext(self.sys_file)[0] + r'.xml'
        self.cp_dl_fw_file = r'CP_DL_' + os.path.splitext(self.fw_file)[0] + r'.xml'

        self.output_path = r'c:\ProgramData\Bellagio\\'
        self.tmp_txt = r"tmp.txt"
        self.char_size = 2  #size of one ascii "char"
        self.dword_size = self.char_size*4  #size of one ascii "dword"(CP send a DWORD every time)

        tblog.infoLog("LnkScriptMod initialization: {0} {1}" .format(self.sys_txt_file, self.fw_txt_file))

    @classmethod
    def getInstance(cls):
        '''
        This will ensure only one time (first) initialization for object. Will be used for UI tool.
        '''
        if not cls._instance:
            cls._instance = LnkScriptMod()
        return cls._instance

    def updateDirFile(self, sys_name, fw_name, output_dir, sys_xml, fw_xml, cp_header, cp_content):
        '''
        update default file/dir name
            sys_name:   sys config binary file name
            fw_name:    bosko fw binary file name
            output_dir: output directory
            sys_xml:    data port sys config download script file name
            fw_xml:     data port bosko fw download script file name
            cp_header:  cp dl script header
            cp_content: cp dl script content
        '''
        if sys_name:
            self.sys_file = sys_name
            self.sys_txt_file = os.path.splitext(self.sys_file)[0] + r'_32Bit_1ch.txt'
            self.sys_xml_file = r'DP_DL_' + os.path.splitext(self.sys_file)[0] + r'.xml'
            self.cp_dl_sys_file = r'CP_DL_' + os.path.splitext(self.sys_file)[0] + r'.xml'
        if fw_name:
            self.fw_file = fw_name
            self.fw_txt_file = os.path.splitext(self.fw_file)[0] + r'_32Bit_1ch.txt'
            self.fw_xml_file = r'DP_DL_' + os.path.splitext(self.fw_file)[0] + r'.xml'
            self.cp_dl_fw_file = r'CP_DL_' + os.path.splitext(self.fw_file)[0] + r'.xml'
        if output_dir:
            self.output_path = output_dir
        if sys_xml:
            self.sys_xml_template_file = sys_xml
        if fw_xml:
            self.fw_xml_template_file = fw_xml
        if cp_header:
            self.cp_header_file = cp_header 
        if cp_content:
            self.cp_content_file = cp_content 

    def bin2Dat(self):
        '''
        convert config/fw binary file to LnK data port downloadable file
        '''
        bin2lnk = Bin2Lnk()

        if not os.path.isfile(self.output_path + self.sys_file):
            raise BellagioError("Could not find sys config bin!")
        bin2lnk.bin2Dp(self.output_path+self.sys_file, self.output_path+self.sys_txt_file)

        if not os.path.isfile(self.output_path + self.fw_file):
            raise BellagioError("Could not find Bosko FW bin!")
        bin2lnk.bin2Dp(self.output_path+self.fw_file, self.output_path+self.fw_txt_file)

        tblog.infoLog("LnkScriptMod: converted bin to data port data file!")

    def modDataPortScript(self):
        '''
        modify LnK data port script template to update downloadable data file
        '''
        if not os.path.isfile(self.output_path + self.sys_xml_template_file):
            raise BellagioError("Could not find LnK DP DL script file for sys config!")

        '''
        ###convert binary to DP DL file
        '''
        self.bin2Dat()

        ###replace sys_config txt in DP download script template
        with open(self.output_path + self.sys_xml_template_file) as infile, open(self.output_path+self.sys_xml_file, 'w') as outfile:
            for line in infile:
                if re.search(self.sys_txt_replace, line):
                    #update DP DL txt file
                    line = line.replace(self.sys_txt_replace, self.output_path+self.sys_txt_file)
                elif re.search('_DATE_', line):
                    #update date
                    line = line.replace("_DATE_", datetime.datetime.now().strftime("%m/%d/%Y"))
                outfile.write(line)

        infile.close()
        outfile.close()

        ###replace bosko_fw txt in DP download script template
        if not os.path.isfile(self.output_path + self.fw_xml_template_file):
            raise BellagioError("Could not find LnK script xml file for bosko fw!")

        with open(self.output_path + self.fw_xml_template_file) as infile, open(self.output_path+self.fw_xml_file, 'w') as outfile:
            for line in infile:
                if re.search(self.fw_txt_replace, line):
                    #update DP DL txt file
                    line = line.replace(self.fw_txt_replace, self.output_path+self.sys_txt_file)
                elif re.search('_DATE_', line):
                    #update date
                    line = line.replace("_DATE_", datetime.datetime.now().strftime("%m/%d/%Y"))
                outfile.write(line)

        infile.close()
        outfile.close()

        tblog.infoLog("LnkScriptMod: LnK script xml file revised!")

    def bin2CtrlPort(self, bin_file, cp_dl_script):
        '''
        convert config/fw binary file to LnK data control port script file
            bin_file: binary_file name(config or FW)
            cp_dl_script: output CP DL script file name
        '''
        if not os.path.isfile(self.output_path + self.cp_header_file):
            tblog.infoLog("LnkScriptMod: failed to find CP header script!")
            raise BellagioError("LnkScriptMod: failed to find CP header script!")

        if not os.path.isfile(self.output_path + self.cp_content_file):
            tblog.infoLog("LnkScriptMod: failed to find CP content script!")
            raise BellagioError("LnkScriptMod: failed to find CP content script!")

        '''
        ###convert binary to txt and align to 4-byte
        '''
        bin2lnk = Bin2Lnk()
        bin2lnk.bin2txt(bin_file, self.tmp_txt)

        '''
        ###generate CP DL script from header, content and input data
        '''
        with open(self.output_path + self.cp_header_file) as cp_header, open(cp_dl_script, 'w') as cp_dl_out, open(self.tmp_txt) as input_data:
            event_str = "0"
            for header_line in cp_header:
                '''
                ###write header file to output till last line
                '''
                if not re.search('Command', header_line):
                    '''
                    #1. write header to output
                    #2. scan event number
                    #3. update current date
                    '''
                    found = re.search('(?<=Event #)\w+', header_line)
                    if found:
                        event_str = found.group(0)
                        #tblog.infoLog("event number: {0}" .format(event_str))
                    if re.search('_DATE_', header_line):
                        #update date
                        header_line = header_line.replace("_DATE_", datetime.datetime.now().strftime("%m/%d/%Y"))
                    #tblog.infoLog("{0}" .format(header_line))
                    cp_dl_out.write(header_line)
                else:
                    '''
                    ###loop input data into content script and insert
                    '''
                    event_num = int(event_str) + 2              #Event # LHDEBUG...original # start from "+2"
                    tblog.infoLog("start event number in int: {0}" .format(event_num))

                    dword = input_data.read(self.dword_size)
                    #tblog.infoLog("dword read: {0}" .format(dword))

                    while dword != "":
                        '''
                        ###reset data count and addr
                        '''
                        data_count = 0
                        reg_addr = 2000
                        l = list(dword)

                        with open(self.output_path + self.cp_content_file) as cp_content:
                            for line in cp_content:
                                if re.search('event_num', line):
                                    '''
                                    ###update event
                                    '''
                                    new_line = line.replace("event_num", str(event_num))
                                    event_num += 1
                                elif re.search('reg_addr', line) and re.search('data', line):
                                    '''
                                    ###update register address and data
                                    '''
                                    new_line1 = line.replace("reg_addr", str(reg_addr))
                                    new_line = new_line1.replace("data", l[data_count*2] + l[data_count*2+1])
                                    #tblog.infoLog("reg_addr: {0} data: {1}" .format(reg_addr, l[data_count*2] + l[data_count*2+1]))
                                    data_count += 1
                                    reg_addr += 1
                                else:
                                    '''
                                    ###do nothing
                                    '''
                                    if re.search('Delay of about 2 us', line):
                                        ###add one frame delay?
                                        event_num += 1
                                    new_line = line
                                cp_dl_out.write(new_line)
                        cp_content.close()

                        '''
                        ###loop data file
                        '''
                        dword = input_data.read(self.dword_size)
                        #tblog.infoLog("dword read: {0}" .format(dword))
                        #break   ###debug...
                    ###write "<Command>" line
                    cp_dl_out.write(header_line)
                    #break       ###break "for" loop
            '''
            ###last two lines
            cp_dl_out.write(r"</Command>")
            cp_dl_out.write("\n\n")
            cp_dl_out.write(r"</Generate>")
            '''

        cp_header.close()
        cp_dl_out.close()
        input_data.close()
        os.remove(self.tmp_txt)
        tblog.infoLog("LnkScriptMod: converted bin to control port script file{0}!" .format(cp_dl_script))

    def genCtrlPortScript(self):
        if not os.path.isfile(self.output_path + self.sys_file):
            raise BellagioError("Could not find sys config bin!")
        self.bin2CtrlPort(self.output_path+self.sys_file, self.output_path+self.cp_dl_sys_file)

        if not os.path.isfile(self.output_path + self.fw_file):
            raise BellagioError("Could not find Bosko FW bin!")
        self.bin2CtrlPort(self.output_path+self.fw_file, self.output_path+self.cp_dl_fw_file)

if __name__ == "__main__":
    tblog.setDebugMode(True)
    lnkMod = LnkScriptMod.getInstance()
    #data port file
    lnkMod.modDataPortScript()
    #control port script
    lnkMod.genCtrlPortScript()

