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

route3_swire_properties = {
    '_DP3_WORDLENGTH_'   : 23,
    '_DP3_INTERVAL_LO_'  : 0xff,
    '_DP3_INTERVAL_HI_'  : 0x01,
    '_DP3_BLOCK_OFFSET_' : 0x00,
    '_DP3_HCTRL_'        : 0x11,
    '_DP1_WORDLENGTH_'   : 23,
    '_DP1_INTERVAL_LO_'  : 0xff,
    '_DP1_INTERVAL_HI_'  : 0x01,
    '_DP1_BLOCK_OFFSET_' : 0x00,
    '_DP1_HCTRL_'        : 0x11,
    '_SCP_FRAMECTRL_'    : 0x08,
    '_CHANNEL_PREPARE_'  : 0x01,
    '_CHANNEL_EN_'       : 0x01}

###shapiro register(0x8030) value for different sample rate(KHz)
samplerate_reg_val = {
    8   : 0,
    16  : 1,
    24  : 2,
    32  : 3,
    48  : 4,
    96  : 5,
    192 : 6 }

'''
LUT of swire frame shape for different sample rate data stream
    Since there can be more than one setup, the idea here is to keep 'frame rate' = 'sample rate'.
    Then we can simply enable SSP for every frame.

    'sample_rate(KHz)' : [row, col, DP3_HStart, DP3_HStop, DP3_Offset, DP1_HStart, DP1_HStop, DP1_Offset]
'''
frame_shape_index = {    #this is index for frame shape value in LUT
    'row'           : 0,
    'col'           : 1,
    'dp3_hstart'    : 2,
    'dp3_hstop'     : 3,
    'dp3_offset'    : 4,
    'dp1_hstart'    : 5,
    'dp1_hstop'     : 6,
    'dp1_offset'    : 7}

frame_shape_lut = {
    8   : [256, 12, 1, 1, 0, 2, 2, 0],
    16  : [128, 12, 1, 1, 0, 2, 2, 0],
    24  : [64, 16, 1, 1, 0, 2, 2, 0],
    32  : [64, 12, 1, 1, 0, 2, 2, 0],
    48  : [64, 8, 1, 1, 0, 2, 2, 0],
    96  : [64, 4, 1, 1, 0, 2, 2, 0],
    192 : [64, 2, 1, 1, 0, 1, 1, 16] }

'''
Swire SCP_FrameCtrl value for rows and cols
'''
swire_rows_ctrl = {
    48 : 0,
    50 : 1,
    60 : 2,
    64 : 3,
    128 : 11,
    192 : 16,
    256 : 19 }  #only part of the table

swire_cols_ctrl = {
    2 : 0,
    4 : 1,
    6 : 2,
    8 : 3,
    10 : 4,
    12 : 5,
    14 : 6,
    16 : 7 }

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
        '''
        ##############################################################
            swire FW download
        ##############################################################
        '''
        #default sys file
        self.sys_file = r'A110.11.12_B71214_KN_VQ_SysConfigSWIRE.bin'
        self.sys_txt_file = os.path.splitext(self.sys_file)[0] + r'_32Bit_1ch.txt'
        self.sys_xml_file = r'DP_DL_'+os.path.splitext(self.sys_file)[0] + r'.xml'

        #default fw file
        self.fw_file = r'A110.11.12_B71214_KN_VQ_BoskoAppSWIRE.bin'
        self.fw_txt_file = os.path.splitext(self.fw_file)[0] + r'_32Bit_1ch.txt'
        self.fw_xml_file = r'DP_DL_'+os.path.splitext(self.fw_file)[0] + r'.xml'

        #data port downloading script template file
        self.sys_xml_template_file = r'FW_DL_DP_SysConfig.xml'
        self.sys_txt_replace = r'SYS_CONFIG.txt'

        self.fw_xml_template_file = r'FW_DL_DP_BoskoApp.xml'
        self.fw_txt_replace = r'BOSKO_FW.txt'

        #control port downloading script template file
        self.cp_header_file = r'CP_DL_header.xml'
        self.cp_content_file = r'CP_DL_content.xml'
        self.cp_dl_sys_file = r'CP_DL_' + os.path.splitext(self.sys_file)[0] + r'.xml'
        self.cp_dl_fw_file = r'CP_DL_' + os.path.splitext(self.fw_file)[0] + r'.xml'

        '''
        ##############################################################
            swire route
        ##############################################################
        '''
        #route setup script template file
        self.route_template = r'route_template.xml'
        self.route_script = r'setup_route.xml'

        #route setup properties
        self.swire_bitrate = 24576 #K : default 12.288MHZ with double date rate
        self.swire_wordlength = 24  #bit
        self.swire_samplerate = 48  #KHz
        self.swire_rows = 48
        self.swire_cols = 2

        '''
        ##############################################################
            general
        ##############################################################
        '''
        self.output_path = r'c:\work\soundwire\autotest\\'
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

    def calTimeInFrames(self, delay_time):
        '''
        calculate how many frames we need for a period of time(ms)
        '''
        return delay_time * self.swire_samplerate

    def updateSwireSetting(self, channel_num, sample_rate, word_length):
        '''
        update swire related settings according to current audio
        '''
        tblog.infoLog("route3 swire update: {0} {1}" .format(sample_rate, word_length))

        self.swire_wordlength = word_length - 1    #number: length - 1
        self.swire_samplerate = sample_rate

        if sample_rate == 192:
            '''
            Only 192KHz, we need to change DP1 offset to fit two streams in one column
            For other sample rate, we put each stream in one column
            '''
            frame_shape_lut[192][frame_shape_index['dp1_offset']] = self.swire_wordlength + 1
            tblog.infoLog("route3 192K frame: {0}" .format(frame_shape_lut[192]))

        self.swire_rows = frame_shape_lut[sample_rate][frame_shape_index['row']]
        self.swire_cols = frame_shape_lut[sample_rate][frame_shape_index['col']]

        #for SCP_FrameCtrl register
        rows_ctrl = swire_rows_ctrl[self.swire_rows]
        cols_ctrl = swire_cols_ctrl[self.swire_cols]

        #in our case(frame rate = sample rate), sample interval = frame size
        sample_interval = (self.swire_rows * self.swire_cols) - 1

        route3_swire_properties['_DP3_WORDLENGTH_'] = self.swire_wordlength
        route3_swire_properties['_DP3_INTERVAL_LO_'] = sample_interval & 0xff
        route3_swire_properties['_DP3_INTERVAL_HI_'] = (sample_interval >> 8) & 0xff
        route3_swire_properties['_DP3_BLOCK_OFFSET_'] = frame_shape_lut[sample_rate][frame_shape_index['dp3_offset']]
        route3_swire_properties['_DP3_HCTRL_'] = (frame_shape_lut[sample_rate][frame_shape_index['dp3_hstart']] << 4) + (frame_shape_lut[sample_rate][frame_shape_index['dp3_hstop']] & 0xf)

        route3_swire_properties['_DP1_WORDLENGTH_'] = self.swire_wordlength
        route3_swire_properties['_DP1_INTERVAL_LO_'] = sample_interval & 0xff
        route3_swire_properties['_DP1_INTERVAL_HI_'] = (sample_interval >> 8) & 0xff
        route3_swire_properties['_DP1_BLOCK_OFFSET_'] = frame_shape_lut[sample_rate][frame_shape_index['dp1_offset']]
        route3_swire_properties['_DP1_HCTRL_'] = (frame_shape_lut[sample_rate][frame_shape_index['dp1_hstart']] << 4) + (frame_shape_lut[sample_rate][frame_shape_index['dp1_hstop']] & 0xf)

        route3_swire_properties['_SCP_FRAMECTRL_'] = (rows_ctrl << 3) + cols_ctrl
        tblog.infoLog("route3 swire frame control: 0x{0:02x}" .format(route3_swire_properties['_SCP_FRAMECTRL_']))
        if channel_num == 2:
            route3_swire_properties['_CHANNEL_PREPARE_'] = 3
            route3_swire_properties['_CHANNEL_EN_'] = 3
            tblog.infoLog("route channel control: 0x{0:02x}" .format(route3_swire_properties['_CHANNEL_EN_']))

    def setupRouteScript(self, route_num, output_dir, sample_rate, word_length, frame_size):
        '''
        Setup route script from template
        '''
        template = output_dir + self.route_template
        if not os.path.isfile(template):
            tblog.infoLog("Could not find route template file {0}!" .format(template))
            raise BellagioError("Could not find route template file!")

        #set channel number based on different route
        channel_num = 1
        if route_num == 20:
            channel_num = 2
        self.updateSwireSetting(channel_num, sample_rate, word_length)
        tblog.infoLog("SWIRE route updated")

        #when frame_size = 0.5ms, set shapiro 0x8035 = 0
        if frame_size < 1:
            frame_size = 0

        #gen route script name
        route_script = output_dir + os.path.splitext(self.route_script)[0] + str(route_num) + '_' + str(sample_rate) + 'K_' + str(word_length) + 'bit_' + str(frame_size) + 'ms.xml'

        start_swire_setup = 0
        with open(template) as route_in, open(route_script, 'w') as route_out:
            for line in route_in:
                '''
                update swire channel setup
                '''
                if re.search('start swire channel setup', line):
                    start_swire_setup = 1
                elif re.search('end swire channel setup', line):
                    start_swire_setup = 0

                if start_swire_setup:
                    #fill in swire channel/DP properties from table
                    for (k, v) in route3_swire_properties.items():
                        if re.search(k, line):
                            line = line.replace(k, ("0x{0:02X}" .format(v)))
                            tblog.infoLog("route3 swire updated: {0}" .format(line))
                            break;
                else:
                    line_updated = 0
                    if re.search('_DATE_', line):
                        #update date
                        line = line.replace("_DATE_", datetime.datetime.now().strftime("%m/%d/%Y"))
                        line_updated = 1
                    if re.search('_INTERVAL_', line):
                        #update sample_interval/channel_num/word_length in swire stream definition
                        line = line.replace("_INTERVAL_", str(self.swire_rows * self.swire_cols))
                        line = line.replace("_CHANNEL_NUM_", str(channel_num))
                        line = line.replace("_WORDLENGTH_", str(word_length))
                        line_updated = 1
                    if re.search('_CHANNEL_ID_0_', line):
                        #update frame_rate/channel_number in swire stream definition
                        line = line.replace("_FRAME_RATE_", str(sample_rate))
                        line = line.replace("_CHANNEL_ID_0_", str(0))
                        line_updated = 1
                    if re.search('_CHANNEL_ID_1_', line):
                        #update frame_rate/channel_number in swire stream definition
                        if channel_num > 1:
                            line = line.replace("_FRAME_RATE_", str(sample_rate))
                            line = line.replace("_CHANNEL_ID_1_", str(1))
                            line_updated = 1
                        else:
                            continue    #one channel route
                    if re.search('_FRAME_SIZE_', line):
                        #update frame size for shapiro
                        line = line.replace("_FRAME_SIZE_", str(frame_size))
                        line_updated = 1
                    if re.search('_SAMPLE_RATE_', line):
                        #update sample rate for shapiro
                        line = line.replace("_SAMPLE_RATE_", str(samplerate_reg_val[sample_rate]))
                        line_updated = 1
                    if re.search('_ROUTE_NUM_', line):
                        #update route number for shapiro
                        line = line.replace("_ROUTE_NUM_", str(route_num))
                        line_updated = 1
                    if re.search('_DELAY_10MS_', line):
                        #update frames for delay
                        line = line.replace("_DELAY_10MS_", str(self.calTimeInFrames(10)))
                        line_updated = 1
                    if re.search('_DELAY_2MS_', line):
                        #update frames for delay
                        line = line.replace("_DELAY_2MS_", str(self.calTimeInFrames(2)))
                        line_updated = 1
                    if re.search('_STREAM_ROWS_', line) or re.search('_STREAM_COLS_', line):
                        #update stream frame shape rows and cols
                        line = line.replace("_STREAM_ROWS_", str(self.swire_rows))
                        line = line.replace("_STREAM_COLS_", str(self.swire_cols))
                        line_updated = 1
                    if re.search('_LOOP_FRAME_', line):
                        '''
                        update frame loop
                        FIXME: Should be LCM of frame_rate and 15(frames of dynamic sync period)
                               Here use frame_rate*15 temporarily
                        '''
                        line = line.replace("_LOOP_FRAME_", str(self.swire_samplerate * 15))
                        line_updated = 1
                    if re.search('_STREAM_CH_EN_', line):
                        #update stream channel enable
                        stream_ch_en = 1
                        if channel_num > 1:
                            stream_ch_en = 3
                        line = line.replace("_STREAM_CH_EN_", str(stream_ch_en))
                        line_updated = 1

                    if line_updated:
                        tblog.infoLog("route3 updated: {0}" .format(line))

                route_out.write(line)

        route_in.close()
        route_out.close()

    def genRouteScript(self):
        '''
        Generate Shapiro swire route setup script for LnK
        '''
        #self.setupRouteScript(3, self.output_path + r'route\\', 48, 16, 2)
        self.setupRouteScript(3, self.output_path + r'route20\\', 48, 16, 2)
        self.setupRouteScript(20, self.output_path + r'route20\\', 48, 24, 2)

if __name__ == "__main__":
    tblog.setDebugMode(True)
    lnkMod = LnkScriptMod.getInstance()
    ###data port script
    #lnkMod.modDataPortScript()
    ###control port script
    #lnkMod.genCtrlPortScript()
    ###route setup script
    lnkMod.genRouteScript()

