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
    def __init__(self, ip, port):
        self.yinc = np.zeros(4)
        self.yoff = np.zeros(4)
        self.tinc = 0.0
        self.toff = 0.0
        self.trange = 0.0
        self.timeVector = None
        
        self.ip = ip
        self.visa = None
        
        self.connect()
        
#        self.getVerticalData(0)
#        self.getVerticalData(1)
#        self.getVerticalData(2)
#        self.getVerticalData(3)
#        
#        self.getHorizontalData()
        
    def connect(self):
        if self.visa != None:
            self.close()
        self.visa = visa.instrument(''.join(('TCPIP::', self.ip, '::INSTR')))
            
    def close(self):
        if self.visa != None:
            self.visa.close()
        self.visa = None
            
    def sendReceive(self, cmd):
        if self.visa == None:
            self.connect()
        try:
            resp = self.visa.ask(cmd)
        except Exception, e:
            print str(e)
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
    
    def getWaveform(self, channel):
        cmd = ''.join(('CHAN', str(channel), ':DATA?'))
        d_raw = self.sendReceive(cmd)
        d_int = np.fromstring(d_raw[2 + int(d_raw[1]):], dtype='u1') 
        print d_int.shape
        data = d_int * self.yinc[channel] + self.yoff[channel]
        return data
    
    def getTimeVector(self):
        return self.timeVector
               
    def getDataHeader(self, channel):
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
        cmd = ''.join(('CHAN', str(channel), ':DATA:YOR?'))
        data = self.sendReceive(cmd)
        self.yoff[channel] = np.float(data)
        cmd = ''.join(('CHAN', str(channel), ':DATA:YINC?'))
        data = self.sendReceive(cmd)
        self.yinc[channel] = np.float(data)
        
    def getHorizontalData(self):
        data = self.getDataHeader(0)
        da = [float(dt) for dt in data.split(',')]
        self.toff = da[0]
        self.tinc = (da[1] - da[0]) / da[2]
        self.timeVector = np.linspace(da[0], da[1], da[2])
        self.trange = (da[1] - da[0])
        
    def setTimeRange(self, tRange):
        cmd = ''.join(('TIM:RANG ', str(tRange)))
        self.sendCommand(cmd)
        self.getHorizontalData()
        
    def setVerticalRange(self, channel, vRange):
        cmd = ''.join(('CHAN', str(channel), ':RANG ', str(vRange)))
        self.sendCommand(cmd)
        self.getVerticalData(channel)
        
    def setVerticalOffset(self, channel, offset):
        cmd = ''.join(('CHAN', str(channel), ':OFFS ', str(offset)))
        self.sendCommand(cmd)
        self.getVerticalData(channel)
        
    def setBandwidth(self, channel, bw):
        if bw.lower() == 'full':
            cmd = ''.join(('CHAN', str(channel), ':BAND FULL'))
        elif bw.lower() == 'b20':
            cmd = ''.join(('CHAN', str(channel), ':BAND B20'))
        else:
            raise ValueError('Bandwidth has to be FULL or B20.')
        self.sendCommand(cmd)

    def getBandwidth(self, channel):
        cmd = ''.join(('CHAN', str(channel), ':BAND?'))
        data = self.sendReceive(cmd)
        return data
            
    def setCoupling(self, channel, coupling):
        if coupling.lower() not in ['dc', 'dclimit', 'ac', 'aclimit', 'gnd']:
            raise ValueError('Coupling has to be DC, DCLimit, AC, ACLimit, or GND.')
        cmd = ''.join(('CHAN', str(channel), ':COUP ', coupling))
        self.sendCommand(cmd)

if __name__ == '__main__':
    hc = Hameg_control('130.235.94.72', 5025)
    
