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

#index of list
swire_reg_addr = 0
swire_reg_val  = 1
swire_reg_seq  = 2
#swire route setup register LUT
swire_route_properties = {
    '_DPRX_CHANNEL_PREPARE_'    : [0x05, 0x01, 0],
    '_DPRX_CHANNEL_EN_'         : [0x30, 0x01, 1],
    '_DPRX_PORTCTRL_'           : [0x02, 0, 2],
    '_DPRX_WORDLENGTH_'         : [0x03, 23, 3],
    '_DPRX_INTERVAL_LO_'        : [0x32, 0xff, 4],
    '_DPRX_INTERVAL_HI_'        : [0x33, 0x01, 5],
    '_DPRX_BLOCK_OFFSET_'       : [0x34, 0x00, 6],
    '_DPRX_HCTRL_'              : [0x36, 0x11, 7],
    '_DPTX_CHANNEL_PREPARE_'    : [0x05, 0x01, 8],
    '_DPTX_CHANNEL_EN_'         : [0x30, 0x01, 9],
    '_DPTX_PORTCTRL_'           : [0x02, 0, 10],
    '_DPTX_WORDLENGTH_'         : [0x03, 23, 11],
    '_DPTX_INTERVAL_LO_'        : [0x32, 0xff, 12],
    '_DPTX_INTERVAL_HI_'        : [0x33, 0x01, 13],
    '_DPTX_BLOCK_OFFSET_'       : [0x34, 0x00, 14],
    '_DPTX_HCTRL_'              : [0x36, 0x22, 15],
        }

'''
shapiro soundwire route def {route# : [channel#, rx_port, tx_port]}
"rx_port == 0" means input is not SWIRE and we should remove rx setup, stream definition and transfer
'''
swire_route_def_index = {
    'channel_num'   : 0,
    'rx_port'       : 1,
    'tx_port'       : 2,
    }

swire_route_def = {
    3  : [1, 3, 1],
    10 : [1, 0, 1],
    11 : [1, 4, 1],
    12 : [1, 0, 2],
    13 : [1, 4, 2],
    14 : [1, 3, 2],
    17 : [2, 0, 1],
    18 : [2, 0, 1],
    19 : [3, 0, 1],
    20 : [2, 3, 1],
    21 : [2, 4, 2],
    22 : [2, 0, 2],
    23 : [2, 0, 2],
    24 : [3, 3, 1],
    }

#shapiro samplerate(KHz) register(0x8030) value LUT
samplerate_reg_val = {
    8   : 0,
    16  : 1,
    24  : 2,
    32  : 3,
    48  : 4,
    96  : 5,
    192 : 6,
    }

'''
LUT of swire frame shape for different sample rate data stream
    Since there can be more than one setup, the idea here is to keep 'frame rate' = 'sample rate'.
    Then we can simply enable SSP for every frame.

    'sample_rate(KHz)' : [row, col, rx_HStart, rx_HStop, rx_Offset, tx_HStart, tx_HStop, tx_Offset]
'''
frame_shape_index = {    #this is index for frame shape value in LUT
    'row'           : 0,
    'col'           : 1,
    'dp_rx_hstart'  : 2,
    'dp_rx_hstop'   : 3,
    'dp_rx_offset'  : 4,
    'dp_tx_hstart'  : 5,
    'dp_tx_hstop'   : 6,
    'dp_tx_offset'  : 7}

frame_shape_lut = {
    8   : [256, 12, 1, 1, 0, 2, 2, 0],
    16  : [128, 12, 1, 1, 0, 2, 2, 0],
    24  : [128, 8, 1, 1, 0, 2, 2, 0],
    32  : [128, 6, 1, 1, 0, 2, 2, 0],
    48  : [128, 4, 1, 1, 0, 2, 2, 0],
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
    96 : 8,
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
        self.channel_num = 1
        self.dp_rx = 3
        self.dp_tx = 1
        self.swire_bitrate = 24576 #K : default 12.288MHZ with double date rate
        self.rx_wordlength = 23  #bit
        self.rx_samplerate = 48  #KHz
        self.tx_wordlength = 23  #bit
        self.tx_samplerate = 48  #KHz
        self.swire_rows = 48
        self.swire_cols = 2
        self.input_pcm = 1
        self.swire_framerate = 48

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

    '''
    ##############################################################
       Gen swire DP download script
    ##############################################################
    '''
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
            raise BellagioError("Could not find LnK DP DL script file for sys config! {0}" .format(self.output_path + self.sys_xml_template_file))

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
                    line = line.replace(self.fw_txt_replace, self.output_path+self.fw_txt_file)
                elif re.search('_DATE_', line):
                    #update date
                    line = line.replace("_DATE_", datetime.datetime.now().strftime("%m/%d/%Y"))
                outfile.write(line)

        infile.close()
        outfile.close()

        tblog.infoLog("LnkScriptMod: LnK script xml file revised!")
        return self.sys_xml_file, self.fw_xml_file

    '''
    ##############################################################
       Gen swire CP download script
    ##############################################################
    '''
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
        
        return self.cp_dl_sys_file, self.cp_dl_fw_file

    '''
    ##############################################################
       Gen swire route setup script 
    ##############################################################
    '''
    def calTimeInFrames(self, delay_time):
        '''
        calculate how many frames we need for a period of time(ms)
        '''
        return delay_time * self.swire_framerate

    def genSwirePing(self, out_file, delay=1, ssp=0, rows=48, cols=2):
        '''
        Generate SWIRE Ping script
        delay: "ping" is also used for delay: use "calTimeInFrames" to calculate how many frames a delay needs
        ssp: usually "ssp" only needs to be enabled in data stream transfer portion
        '''
        line_ping = r'<Swframe Repeat="_DELAY_" rows="_ROWS_" cols="_COLS_" preq="0" StaticSync="177" Phy="0" DynamicSync="Valid" Parity="Valid" nak="0" ack="0" >' + '\n' + r'   <controlword opcode="0" ssp="_SSP_" breq="0" brel="0" reserved="0" />' + '\n' + '</Swframe>\n'
        line_ping = line_ping.replace("_DELAY_", str(delay))
        line_ping = line_ping.replace("_SSP_", str(ssp))
        line_ping = line_ping.replace("_ROWS_", str(rows))
        line_ping = line_ping.replace("_COLS_", str(cols))
        out_file.write(line_ping)

    def writeReadSwireReg(self, out_file, write, addr, val, dev=1, rows=48, cols=2):
        '''
        generate script to write/read swire reg
        '''
        line_frame_start = r'<Swframe Repeat="1" rows="_ROWS_" cols="_COLS_" preq="0" StaticSync="177" Phy="0" DynamicSync="Valid" Parity="Valid" nak="0" ack="0" >' + '\n'
        line_frame_end = r'</Swframe>' + '\n'
        line_frame = r'   <controlword opcode="_WR_RD_" DeviceAddress="_DEV_" RegisterAddress="_swire_reg_" Data="_swire_val_" />' + '\n'

        line_frame_start = line_frame_start.replace("_ROWS_", str(rows))
        line_frame_start = line_frame_start.replace("_COLS_", str(cols))
        out_file.write(line_frame_start)

        line_frame = line_frame.replace("_swire_reg_", ("0x{0:04x}" .format(addr)))
        line_frame = line_frame.replace("_swire_val_", ("0x{0:02x}" .format(val&0xff)))
        line_frame = line_frame.replace("_DEV_", str(dev))
        if write:
            line_frame = line_frame.replace("_WR_RD_", str(3))
        else:   #read
            line_frame = line_frame.replace("_WR_RD_", str(2))
        out_file.write(line_frame)

        out_file.write(line_frame_end)

    def writeShapiroReg(self, out_file, addr, val, dev=1, rows=48, cols=2):
        '''
        generate script to write Shapiro reg through swire
        '''
        line_comment = '<!-- Shapiro write reg 0x{0:X} = 0x{1:04x} -->\n' .format(addr, val)

        out_file.write(line_comment)

        write = 1
        swire_reg = 0x2000
        self.writeReadSwireReg(out_file, write, swire_reg, val&0xff, dev, rows, cols)

        swire_reg += 1  #0x2001
        self.writeReadSwireReg(out_file, write, swire_reg, (val>>8)&0xff, dev, rows, cols)

        swire_reg += 1  #0x2002
        self.writeReadSwireReg(out_file, write, swire_reg, addr&0xff, dev, rows, cols)

        swire_reg += 1  #0x2003
        self.writeReadSwireReg(out_file, write, swire_reg, (addr>>8)&0xff, dev, rows, cols)

        ###Add 10ms delay between shapiro write/read
        self.genSwirePing(out_file, self.calTimeInFrames(10), 0, rows, cols)

        write = 0
        swire_reg += 1
        self.writeReadSwireReg(out_file, write, swire_reg, 0, dev, rows, cols)

        swire_reg += 1
        self.writeReadSwireReg(out_file, write, swire_reg, 0, dev, rows, cols)

        swire_reg += 1
        self.writeReadSwireReg(out_file, write, swire_reg, 0, dev, rows, cols)

        swire_reg += 1
        self.writeReadSwireReg(out_file, write, swire_reg, 0, dev, rows, cols)

        ###Add 10ms delay between shapiro write/read
        self.genSwirePing(out_file, self.calTimeInFrames(10), 0, rows, cols)

    def genShapiroRouteSetting(self, out_file, route_num, frame_size):
        '''
        Generate shapiro route setup script
        '''
        tblog.infoLog("Shapiro SWIRE route {0} setup" .format(route_num))
        self.writeShapiroReg(out_file, 0x8035, frame_size)
        self.writeShapiroReg(out_file, 0x8030, samplerate_reg_val[self.swire_framerate])
        '''
        FIXME: should use command table for each route?
        '''
        if route_num == 10:
            self.writeShapiroReg(out_file, 0x800c, 0x1002)
            self.writeShapiroReg(out_file, 0x800d, 0x0003)
        if route_num == 19:
            self.writeShapiroReg(out_file, 0x800c, 0x1002)
            self.writeShapiroReg(out_file, 0x800d, 0x0004)
            self.writeShapiroReg(out_file, 0x800c, 0x1202)
            self.writeShapiroReg(out_file, 0x800d, 0x0004)
            self.writeShapiroReg(out_file, 0x800c, 0x1302)
            self.writeShapiroReg(out_file, 0x800d, 0x0004)

        self.writeShapiroReg(out_file, 0x8032, route_num)

    def genSwireRouteSetting(self, out_file):
        '''
        Generate SWIRE route setup script
        '''
        self.genSwirePing(out_file)
        i = 0;
        '''
        Program shapiro registers in sequence
        '''
        for i in range(len(swire_route_properties)):
            for (k, v) in swire_route_properties.items():
                if v[swire_reg_seq] == i:
                    if self.dp_rx == 0 and re.search('DPRX', k):
                        #No swire RX, input from PCM/PDM: just skip
                        break
                    else:
                        self.writeReadSwireReg(out_file, 1, v[swire_reg_addr], v[swire_reg_val])
                        break

    def genSwireFrameShapeSetting(self, out_file):
        '''
        Generate SWIRE frame shape setup script
        '''
        rows_ctrl = swire_rows_ctrl[self.swire_rows]
        cols_ctrl = swire_cols_ctrl[self.swire_cols]
        scp_framectrl_addr = 0x70
        scp_framectrl_val = (rows_ctrl << 3) + cols_ctrl
        tblog.infoLog("swire frame control: 0x{0:02x}" .format(scp_framectrl_val))

        self.genSwirePing(out_file)
        self.writeReadSwireReg(out_file, 1, scp_framectrl_addr, scp_framectrl_val, 15)  #dev=15 to broadcast

    def genSwireStream(self, out_file):
        '''
        Generate SWIRE data stream definition script
        '''
        line_stream = r'   <DataStream Id="A1">' + '\n' + r'      <Structure Channels="_CHANNEL_NUM_" Interval="_INTERVAL_" Hstart="1" Hstop="1" Offset="0" Length="_WORDLENGTH_" Protocol="0" BlockPackingMode="0" BlockGroupCount="1" SubOffset="0" Lane="0" />' + '\n' + '_CONTENT_   </DataStream>\n'
        line_content_t = r'      <Content ChID="_CHANNEL_ID_" Wave="_INPUT_WAVEFORM_" Freq="1000" N="_FRAME_RATE_" M="1" Amplitude="-_AMP_dBFs" />' + '\n'

        line_stream = line_stream.replace("_INTERVAL_", str(self.swire_bitrate/self.rx_samplerate))
        line_stream = line_stream.replace("_CHANNEL_NUM_", str(self.channel_num))
        line_stream = line_stream.replace("_WORDLENGTH_", str(self.rx_wordlength+1)) #stream def requires real length

        line_content = ""
        for i in range(self.channel_num):
            line = line_content_t.replace('_CHANNEL_ID_', str(i))
            line = line.replace("_FRAME_RATE_", str(self.swire_bitrate/(self.swire_rows*self.swire_cols)))
            if self.input_pcm:
                line = line.replace("_INPUT_WAVEFORM_", 'sine')
                line = line.replace("_AMP_", '3')
            else:
                line = line.replace("_INPUT_WAVEFORM_", 'pdm_sine')
                line = line.replace("_AMP_", '16')
            line_content += line

        line_stream = line_stream.replace('_CONTENT_', line_content)
        out_file.write(line_stream)
        tblog.infoLog("swire data stream content: {0}" .format(line_stream))

    def genSwireStreamStart(self, out_file, rows, cols, ch_en):
        '''
        Generate shapiro data stream start script
        '''
        line_sstart = r'<Swframe Repeat="1" rows="_STREAM_ROWS_" cols="_STREAM_COLS_" preq="0" StaticSync="177" Phy="0" DynamicSync="Valid" Parity="Valid" nak="0" ack="0" >' + '\n' + r'   <DataStream Id="A1" >' + '\n' + r'      <Start ChannelEnable="_STREAM_CH_EN_" />' + '\n' + '   </DataStream>\n' + r'   <controlword opcode="0" ssp="0" breq="0" brel="0" reserved="0" />' + '\n' + '</Swframe>\n'
        line_sstart = line_sstart.replace("_STREAM_ROWS_", str(rows))
        line_sstart = line_sstart.replace("_STREAM_COLS_", str(cols))
        line_sstart = line_sstart.replace("_STREAM_CH_EN_", str(ch_en))
        out_file.write(line_sstart)

    def genSwireStreamLoop(self, out_file, rows, cols, loop=100):
        '''
        Generate shapiro data stream transfer script
        '''
        line_stream = r'<Loop Repeat="_LOOP_">' + '\n'
        line_stream = line_stream.replace("_LOOP_", str(loop))
        out_file.write(line_stream)
        
        '''
        calculate frame loop and enable ssp
        FIXME: Should be LCM of frame_rate and 15(frames of dynamic sync period)
                Here use frame_rate*15 temporarily
        '''
        self.genSwirePing(out_file, self.swire_framerate*15, 1, rows, cols)

        out_file.write("</Loop>\n")

    def updateSwireSetting(self):
        '''
        Update swire related settings according to current audio
        Includeing frame shape settting and SWIRE register setting
        '''
        tblog.infoLog("swire route update: channel num {0} frame rate {1}" .format(self.channel_num, self.swire_framerate))

        self.swire_rows = frame_shape_lut[self.swire_framerate][frame_shape_index['row']]
        self.swire_cols = frame_shape_lut[self.swire_framerate][frame_shape_index['col']]

        '''
        ##############################################################
        Take care of special cases for frame shape!!!
        ##############################################################
        '''
        if self.tx_samplerate == 192:
            '''
            For 192KHz, we need to change DP TX offset to fit rx/tx streams in one column
            For other sample rate, we put rx/tx streams in different columns
            FIXME: this only considers route3 case. Need to update for other route later!!!
            '''
            frame_shape_lut[192][frame_shape_index['dp_tx_offset']] = (self.rx_wordlength + 1)*self.channel_num
            tblog.infoLog("192K frame shape LUT: {0}" .format(frame_shape_lut[192]))
        '''
        end of frame shape handling!!!
        '''

        '''
        calculate swire DP register address based on current DP used
        '''
        for (k, v) in swire_route_properties.items():
            if re.search('DPRX', k):
                v[swire_reg_addr] &= 0xff
                v[swire_reg_addr] += (self.dp_rx<<8)
            elif re.search('DPTX', k):
                v[swire_reg_addr] &= 0xff
                v[swire_reg_addr] += (self.dp_tx<<8)

        '''
        calculate swire DP register value
        '''
        rx_sample_interval = (self.swire_bitrate/self.rx_samplerate) - 1
        swire_route_properties['_DPRX_WORDLENGTH_'][swire_reg_val] = self.rx_wordlength
        swire_route_properties['_DPRX_INTERVAL_LO_'][swire_reg_val] = rx_sample_interval & 0xff
        swire_route_properties['_DPRX_INTERVAL_HI_'][swire_reg_val] = (rx_sample_interval >> 8) & 0xff
        swire_route_properties['_DPRX_BLOCK_OFFSET_'][swire_reg_val] = frame_shape_lut[self.swire_framerate][frame_shape_index['dp_rx_offset']]
        swire_route_properties['_DPRX_HCTRL_'][swire_reg_val] = (frame_shape_lut[self.swire_framerate][frame_shape_index['dp_rx_hstart']] << 4) + (frame_shape_lut[self.swire_framerate][frame_shape_index['dp_rx_hstop']] & 0xf)

        tx_sample_interval = (self.swire_bitrate/self.tx_samplerate) - 1
        swire_route_properties['_DPTX_WORDLENGTH_'][swire_reg_val] = self.tx_wordlength
        swire_route_properties['_DPTX_INTERVAL_LO_'][swire_reg_val] = tx_sample_interval & 0xff
        swire_route_properties['_DPTX_INTERVAL_HI_'][swire_reg_val] = (tx_sample_interval >> 8) & 0xff
        swire_route_properties['_DPTX_BLOCK_OFFSET_'][swire_reg_val] = frame_shape_lut[self.swire_framerate][frame_shape_index['dp_tx_offset']]
        swire_route_properties['_DPTX_HCTRL_'][swire_reg_val] = (frame_shape_lut[self.swire_framerate][frame_shape_index['dp_tx_hstart']] << 4) + (frame_shape_lut[self.swire_framerate][frame_shape_index['dp_tx_hstop']] & 0xf)

        '''
        update multiple channel setting
        '''
        chan_val = 0
        for i in range(self.channel_num):
            chan_val += (1<<i)
        tblog.infoLog("CHANNEL num: {0} enable value {1}!" .format(self.channel_num, chan_val))

        swire_route_properties['_DPRX_CHANNEL_PREPARE_'][swire_reg_val] = chan_val
        swire_route_properties['_DPRX_CHANNEL_EN_'][swire_reg_val] = chan_val
        swire_route_properties['_DPTX_CHANNEL_PREPARE_'][swire_reg_val] = chan_val
        swire_route_properties['_DPTX_CHANNEL_EN_'][swire_reg_val] = chan_val


    def setupRouteScript(self, route_num, output_dir, rx_samplerate, rx_wordlength, tx_samplerate, tx_wordlength, frame_size):
        '''
        Setup route script from template
        '''
        template = output_dir + self.route_template
        if not os.path.isfile(template):
            tblog.infoLog("Could not find route template file {0}!" .format(template))
            raise BellagioError("Could not find route template file!")

        #get route definition: channel num/rx port/tx port
        self.channel_num = swire_route_def[route_num][swire_route_def_index['channel_num']]
        self.dp_rx = swire_route_def[route_num][swire_route_def_index['rx_port']]
        self.dp_tx = swire_route_def[route_num][swire_route_def_index['tx_port']]

        self.rx_samplerate = rx_samplerate
        self.rx_wordlength = rx_wordlength - 1    #number: length - 1
        self.tx_samplerate = tx_samplerate
        self.tx_wordlength = tx_wordlength - 1    #number: length - 1

        '''
        Form frame shape based on PCM stream sample rate
            if rx is PCM, use rx
            else if tx is PCM, use tx 
        '''
        if self.dp_rx == 3:
            self.input_pcm = 1
            self.swire_framerate = self.rx_samplerate
        elif self.dp_rx == 4:
            self.input_pcm = 0
            if self.dp_tx == 1:
                self.swire_framerate = self.tx_samplerate
            else:
                #FIXME: for PDM pass-through, set framerate=16KHz?
                self.swire_framerate = 16

        tblog.infoLog("Route{0} def: channel {1}, RX port {2} TX port {3}!" .format(route_num, self.channel_num, self.dp_rx, self.dp_tx))

        self.updateSwireSetting()
        tblog.infoLog("SWIRE route updated")

        #gen route script name
        route_script = output_dir + os.path.splitext(self.route_script)[0] + str(route_num) + '_' + str(rx_samplerate) + 'K_' + str(rx_wordlength) + 'bit_'  + str(tx_samplerate) + 'K_' + str(tx_wordlength) + 'bit_' + str(frame_size) + 'ms.xml'

        #when frame_size = 0.5ms, set shapiro 0x8035 = 0
        if frame_size < 1:
            frame_size = 0

        with open(template) as route_in, open(route_script, 'w') as route_out:
            for line in route_in:
                '''
                Gen script for shaprio route setup
                '''
                if re.search('start shapiro setup', line):
                    route_out.write(line)
                    self.genShapiroRouteSetting(route_out, route_num, frame_size)
                    continue

                '''
                gen script for swire route setup
                '''
                if re.search('start swire channel setup', line):
                    route_out.write(line)
                    self.genSwireRouteSetting(route_out)
                    self.genSwireFrameShapeSetting(route_out)
                    continue

                '''
                gen script for swire data stream transfer and close 
                '''
                if re.search('start data stream', line):
                    #start stream only when input is swire
                    if self.dp_rx != 0:
                        self.genSwireStreamStart(route_out, self.swire_rows, self.swire_cols, swire_route_properties['_DPRX_CHANNEL_EN_'][swire_reg_val])
                    #loop for data transfer
                    self.genSwireStreamLoop(route_out, self.swire_rows, self.swire_cols)

                    #disable swire channel
                    if self.dp_rx != 0:
                        self.writeReadSwireReg(route_out, 1,  swire_route_properties['_DPRX_CHANNEL_EN_'][swire_reg_addr], 0, 1,  self.swire_rows, self.swire_cols)
                    self.writeReadSwireReg(route_out, 1,  swire_route_properties['_DPTX_CHANNEL_EN_'][swire_reg_addr], 0, 1,  self.swire_rows, self.swire_cols)

                    #delay 2 ms
                    self.genSwirePing(route_out, self.calTimeInFrames(2), 0, self.swire_rows, self.swire_cols)

                    #stop shapiro route
                    self.writeShapiroReg(route_out, 0x8033, 0, 1, self.swire_rows, self.swire_cols)
                    continue

                '''
                gen script for swire data stream def
                '''
                if re.search('start stream define', line):
                    route_out.write(line)
                    #only when input is swire
                    if self.dp_rx != 0:
                        self.genSwireStream(route_out)
                    continue

                if re.search('_DATE_', line):
                    #update date
                    line = line.replace("_DATE_", datetime.datetime.now().strftime("%m/%d/%Y"))
                    tblog.infoLog("route setup script updated: {0}" .format(line))

                route_out.write(line)

        route_in.close()
        route_out.close()
        return route_script

    def genRouteScript(self):
        '''
        Generate Shapiro swire route setup script for LnK
        '''
        self.setupRouteScript(3, self.output_path + r'debug\\', 48, 16, 48, 16, 2)
        self.setupRouteScript(3, self.output_path + r'debug\\', 96, 32, 96, 32, 2)
        #self.setupRouteScript(3, self.output_path + r'debug\\', 192, 24, 192, 24, 1)

        self.setupRouteScript(10, self.output_path + r'debug\\', 1536, 1, 48, 24, 2)

        self.setupRouteScript(19, self.output_path + r'debug\\', 3072, 1, 48, 24, 1)

        #self.setupRouteScript(11, self.output_path + r'debug\\', 768, 1, 48, 24, 2)

        #self.setupRouteScript(13, self.output_path + r'debug\\', 768, 1, 768, 1, 8)

        #self.setupRouteScript(24, self.output_path + r'debug\\', 48, 24, 48, 24, 2)

if __name__ == "__main__":
    tblog.setDebugMode(True)
    lnkMod = LnkScriptMod.getInstance()
    ###data port script
    #lnkMod.modDataPortScript()
    ###control port script
    #lnkMod.genCtrlPortScript()
    ###route setup script
    lnkMod.genRouteScript()

