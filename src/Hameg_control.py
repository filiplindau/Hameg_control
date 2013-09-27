# -*- coding:utf-8 -*-
"""
Created on Sep 13, 2013

@author: Laser
"""
import socket
import numpy as np
import time

class Hameg_control(object):
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.socket = None
        
        self.connect()
        
    def connect(self):
        if self.socket != None:
            self.close()
            
        self.socket = socket.socket()
        self.socket.connect((self.ip, self.port))
        self.socket.settimeout(0)
            
    def close(self):
        if self.socket != None:
            self.socket.close()
            
    def sendCommand(self, cmd):
        if self.socket == None:
            self.connect()
        try:
            self.socket.send(cmd)
        except socket.error, e:
            print str(e)
        
    def getResponse(self):
        if self.socket == None:
            self.connect()
        resp = ' '
        data = ''
        while resp != '':
            try:
                resp = self.socket.recv(1024)
            except socket.error:
                resp = ''
            data = ''.join((data, resp))
        return data
    
    def sendReceive(self, cmd):
        if self.socket == None:
            self.connect()
        try:
            self.socket.send(cmd)
        except socket.error, e:
            print str(e)
        
        self.socket.settimeout(0.5)
        try:
            resp = self.socket.recv(2048)
        except socket.error, e:
            resp = ''
            print str(e)
        data = resp
        self.socket.settimeout(0.05)
        while resp != '':
            try:
                resp = self.socket.recv(2048)
            except socket.error, e:
                resp = ''
                print str(e)
            data = ''.join((data, resp))
        return data
    
    def getWaveform(self, channel):
        cmd = ''.join(('CHAN', str(channel), ':DATA?\n'))
        d_raw = self.sendReceive(cmd)
        print d_raw[0:10], d_raw[-2:], d_raw.__len__()
        data = np.fromstring(d_raw[2 + int(d_raw[1]):-1], dtype='u1') 
        return data

    def getData(self):
        cmd = ''.join(('CHAN', str(0), ':DATA?\n'))
        try:
            self.socket.send(cmd)
        except socket.error, e:
            print str(e)

        d = ' '
        self.socket.settimeout(None)
        t0 = time.clock()
        while d[-1] != '\n':
            resp = self.socket.recv(8148)
            print time.clock() - t0, resp.__len__()
            d = ''.join((d, resp))
        return d
            
    
    def getDataHeader(self, channel):
        cmd = ''.join(('CHAN', str(channel), ':DATA:HEAD?\n'))
        data = self.sendReceive(cmd)
        return data
    
    def setDataFormat(self, form):
        if form.lower() == 'real':
            cmd = 'FORM REAL\n'
        elif form.lower() == 'int':
            cmd = 'FORM UINT,8\n'
        else:
            cmd = 'FORM ASC\n'
        data = self.sendCommand(cmd)
        
    def getDataFormat(self):
        cmd = 'FORM?'
        data = self.sendReceive(cmd)
        return data        
        
        

if __name__ == '__main__':
    hc = Hameg_control('130.235.94.72', 5025)
    
