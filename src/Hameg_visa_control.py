# -*- coding:utf-8 -*-
"""
Created on Sep 13, 2013

@author: Laser
"""
import socket
import numpy as np
import time
import visa

class Hameg_control(object):
    def __init__(self, ip, port=5025):
        self.updateTime = 0.2
        self.updateTimeLong = 1.0
        
        self.yrange = np.zeros(4)
        self.yinc = np.zeros(4)
        self.yoff = np.zeros(4)
        self.tinc = 0.0
        self.toff = 0.0
        self.trange = 0.0
        self.timeVector = None
        
        self.ip = ip
        self.visa = None
        
        self.connect()
        time.sleep(0.5)
        
        self.getErrorQueue()
        self.setupInstrument()
                
    def connect(self):
        if self.visa != None:
            self.close()
        self.visa = visa.instrument(''.join(('TCPIP::', self.ip, '::INSTR')))
        self.visa.timeout = 1.0
            
    def close(self):
        if self.visa != None:
            self.visa.close()
        self.visa = None
            
    def sendReceive(self, cmd):
        if self.visa == None:
            self.connect()
        try:
            resp = self.visa.ask(cmd)
        except visa.VisaIOError:
            err = self.getErrorQueue()
            raise ValueError(err[0])
        except Exception, e:            
            raise(e)
        return resp
    
    def sendCommand(self, cmd):
        if self.visa == None:
            self.connect()
        try:
            resp = self.visa.write(cmd)
        except Exception, e:
            print str(e)
            raise(e)
        return resp
    
# Horizontal    
    def getTimeVector(self):
        return self.timeVector
    
    def getHorizontalData(self):
        data = self.getDataHeader(0)
        da = [float(dt) for dt in data.split(',')]
        self.toff = da[0]
        if da[2] != 0:
            self.tinc = (da[1] - da[0]) / da[2]
        else:
            self.tinc = 1
        self.timeVector = np.linspace(da[0], da[1], da[2])
        self.trange = (da[1] - da[0])
        
    def setTimeRange(self, tRange):
        cmd = ''.join(('TIM:RANG ', str(tRange)))
        self.sendCommand(cmd)
        time.sleep(self.updateTime)
        self.getHorizontalData()
        
    def setAcquisitionRate(self, rate):
        if rate.lower() in ['auto', 'mwav', 'msam']:
            cmd = ''.join(('ACQ:WRAT ', rate))
            self.sendCommand(cmd)
        else:
            raise ValueError('Acquisition rate has to be AUTO, MWAV, or MSAM.')

    def getAcquisitionRate(self):
        cmd = ''.join(('ACQ:WRAT?'))
        data = self.sendReceive(cmd)
        return data
        

#Vertical        
    def getWaveform(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('CHAN', str(channel), ':DATA?'))
        d_raw = self.sendReceive(cmd)
        d_int = np.fromstring(d_raw[2 + int(d_raw[1]):], dtype='u1') 
        data = d_int * self.yinc[channel] + self.yoff[channel]
        return data
                   
    def getDataHeader(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('CHAN', str(channel), ':DATA:HEAD?'))
        data = self.sendReceive(cmd)
        return data
    
    def setDataFormat(self, form):
        if form.lower() == 'real':
            cmd = 'FORM REAL'
        elif form.lower() == 'int':
            cmd = 'FORM UINT,8'
        else:
            cmd = 'FORM ASC'
        self.sendCommand(cmd)
        
    def getDataFormat(self):
        cmd = 'FORM?'
        data = self.sendReceive(cmd)
        return data        
  
    def getVerticalData(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('CHAN', str(channel), ':DATA:YOR?'))
        data = self.sendReceive(cmd)
        self.yoff[channel - 1] = np.float(data)
        cmd = ''.join(('CHAN', str(channel), ':DATA:YINC?'))
        data = self.sendReceive(cmd)
        self.yinc[channel - 1] = np.float(data)
        self.yrange[channel - 1] = self.yinc[channel - 1] * 256
        
    def setVerticalRange(self, channel, vRange):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('CHAN', str(channel), ':RANG ', str(vRange)))
        self.sendCommand(cmd)
        time.sleep(self.updateTime)
        self.getVerticalData(channel)
        
    def getVerticalRange(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        return self.yrange[channel - 1]
        
    def setVerticalOffset(self, channel, offset):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('CHAN', str(channel), ':OFFS ', str(offset)))
        self.sendCommand(cmd)
        time.sleep(self.updateTime)
        self.getVerticalData(channel)

    def getVerticalOffset(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        return self.yoff[channel - 1]
        
    def setBandwidth(self, channel, bw):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        if bw.lower() == 'full':
            cmd = ''.join(('CHAN', str(channel), ':BAND FULL'))
        elif bw.lower() == 'b20':
            cmd = ''.join(('CHAN', str(channel), ':BAND B20'))
        else:
            raise ValueError('Bandwidth has to be FULL or B20.')
        self.sendCommand(cmd)

    def getBandwidth(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('CHAN', str(channel), ':BAND?'))
        data = self.sendReceive(cmd)
        return data
            
    def setCoupling(self, channel, coupling):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        if coupling.lower() in ['dc', 'dclimit', 'ac', 'aclimit', 'gnd']:
            cmd = ''.join(('CHAN', str(channel), ':COUP ', coupling))
            self.sendCommand(cmd)
        else:
            raise ValueError('Coupling has to be DC, DCLimit, AC, ACLimit, or GND.')

    def getCoupling(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('CHAN', str(channel), ':COUP?'))
        data = self.sendReceive(cmd)
        return data
    
    def setChannelState(self, channel, state):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        if type(state) == str:
            state = state.lower()
        if state in ['on', True, 1]:
            st = 'ON'
        elif state in ['off', False, 0]:
            st = 'OFF'
        else:
            raise ValueError('Coupling has to be \'On\ / \'Off\', True/False or 1/0')
        cmd = ''.join(('CHAN', str(channel), ':STAT ', st))
        self.sendCommand(cmd)
        if st == 'ON':
            time.sleep(self.updateTimeLong)
            self.getVerticalData(channel)

    def getChannelState(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('CHAN', str(channel), ':STAT?'))
        data = self.sendReceive(cmd)
        return data

# Trigger
    def setTrigMode(self, mode):
        if type(mode) == str:
            mode = mode.lower()
        if mode == 'auto':
            st = 'AUTO'
        elif mode in ['norm', 'normal']:
            st = 'NORM'
        else:
            raise ValueError('Trigger mode has to be AUTO or NORMAL')
        cmd = ''.join(('TRIG:A:MODE ', st))
        self.sendCommand(cmd)
        
    def getTrigMode(self):
        cmd = ''.join(('TRIG:A:MODE?'))
        data = self.sendReceive(cmd)
        return data

    def setTrigLevel(self, channel, level):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('TRIG:A:LEV', str(channel), ':VAL ', str(level)))
        self.sendCommand(cmd)
        
    def getTrigLevel(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('TRIG:A:LEV', str(channel), ':VAL?'))
        data = self.sendReceive(cmd)
        return data

    def setTrigOffset(self, offset):
        cmd = ''.join(('TIM:POS ', str(offset)))
        self.sendCommand(cmd)
        
    def getTrigOffset(self):
        cmd = ''.join(('TIM:POS?'))
        data = self.sendReceive(cmd)
        return data

    def setTrigSource(self, source):
        if type(source) == str:
            source = source.lower()
        if source in ['ch1', 'channel1']:
            st = 'CH1'
        elif source in ['ch2', 'channel2']:
            st = 'CH2'
        elif source in ['ch3', 'channel3']:
            st = 'CH3'
        elif source in ['ch4', 'channel4']:
            st = 'CH4'
        elif source in ['ext', 'external']:
            st = 'EXT'
        elif source in ['line']:
            st = 'LINE'
        else:
            raise ValueError('Trigger mode has to be CH1, CH2, CH3, CH4, EXT, or LINE')
        cmd = ''.join(('TRIG:A:SOUR ', st))
        self.sendCommand(cmd)
        
    def getTrigSource(self):
        cmd = ''.join(('TRIG:A:SOUR?'))
        data = self.sendReceive(cmd)
        return data
    
    def fireSoftwareTrig(self):
        cmd = '*TRG'
        self.sendCommand(cmd)
        
# Measurements
    def setQuickMeasurementEnable(self, channel, enable):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')        
        if enable == True:
            cmd = ''.join(('MEAS', str(channel), ':AON'))
        else:
            cmd = ''.join(('MEAS', str(channel), ':AOFF'))
        self.sendCommand(cmd)
    
    def getQuickMeasurementResults(self, channel):
        if channel < 1 and channel > 4:
            raise ValueError('Channel must be 1-4')
        cmd = ''.join(('MEAS', str(channel), ':ARES?'))
        data = self.sendReceive(cmd)
        return data
    
# System    
    def getErrorQueue(self):
        cmd = 'SYST:ERR:NEXT?'
        resp = ''
        errQueue = []
        t0 = time.time()
        while resp != 'No error':
            data = self.sendReceive(cmd)
            resp = data.split(',')[1].split('"')[1]
            errQueue.append(resp)
            dt = time.time() - t0
            if dt > 0.5:
                resp = 'No error'
        return errQueue
    
    def getOperationComplete(self):
        cmd = '*OPC; *ESR?'
        data = self.sendReceive(cmd)
        # Check bit 0 if the waiting command has finished
        if int(data) & 1 == 1:
            return True
        else:
            return False
        
    def setupInstrument(self):
        cmd = '*RST'
        self.sendCommand(cmd)
        time.sleep(0.5)        
        cmd = '*ESE 1'      # Enable OPC (operation complete bit in event status register
        self.sendCommand(cmd)
        self.setAcquisition('RUN')
        self.fireSoftwareTrig()
        for ch in range(4):
            print ch
            try:
                if self.getChannelState(ch) == '1':
                    self.getVerticalData(ch)
            except:
                pass
        
        self.getHorizontalData()
        self.setDataFormat('int')
        self.setAcquisitionRate('mwav')
        
        
        
    def setAcquisition(self, acq):
        if acq.lower() == 'run':
            cmd = 'RUN'
        elif acq.lower() == 'single':
            cmd = 'SING'
        else:
            cmd = 'STOP'
        self.sendCommand(cmd)
        
        

if __name__ == '__main__':
    hc = Hameg_control('130.235.94.72', 5025)
    
