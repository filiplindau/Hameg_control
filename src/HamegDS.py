# -*- coding:utf-8 -*-
"""
Created on Oct 2, 2013

@author: Laser
"""

import PyTango
import sys
import Hameg_visa_control as hc
import threading
import time
import numpy as np
from socket import gethostname
import Queue


class OscilloscopeCommand:
    def __init__(self, command, data=None):
        self.command = command
        self.data = data

class Channel(object):
    def __init__(self):
        self.coupling = 'dc'
        self.offset = 0.0
        self.range = 1.0
        self.state = False
        self.data = np.zeros(6000)

class OscilloscopeSetting(object):
    def __init__(self):
        self.channels = [Channel() for k in range(4)]
        self.triggerSource = 'ch1'
        self.triggerLevel = 0.1
        self.triggerOffset = 0.0
        self.triggerMode = 'auto'
        self.timeBase = 1e-4
        self.timeVector = np.zeros(6000)
        
#==================================================================
#   HamegDS Class Description:
#
#         Control of a Hameg HMOx0xx oscilloscope
#
#==================================================================
#     Device States Description:
#
#   DevState.ON :       Connected to oscilloscope
#   DevState.FAULT :    Error detected
#   DevState.UNKNOWN :  Communication problem, disconnected
#   DevState.STANDBY :  Connected to oscilloscope, not acquiring
#   DevState.INIT :     Initializing oscilloscope. Could take time.
#==================================================================


class HamegDS(PyTango.Device_4Impl):

#------------------------------------------------------------------
#     Device constructor
#------------------------------------------------------------------
    def __init__(self, cl, name):
        PyTango.Device_4Impl.__init__(self, cl, name)
        HamegDS.init_device(self)

#------------------------------------------------------------------
#     Device destructor
#------------------------------------------------------------------
    def delete_device(self):
        print "[Device delete_device method] for device", self.get_name()
        self.stopStateThread()
        self.oscilloscope.close()


#------------------------------------------------------------------
#     Device initialization
#------------------------------------------------------------------
    def init_device(self):
        print "In ", self.get_name(), "::init_device()"        
        self.set_state(PyTango.DevState.UNKNOWN)
        self.get_device_properties(self.get_device_class())
        
        try:
            self.stopStateThread()
            self.osclloscope.close()
        except Exception, e:
            pass

        self.stateThread = threading.Thread()
        threading.Thread.__init__(self.stateThread, target=self.stateHandlerDispatcher)
        
        self.commandQueue = Queue.Queue(100)
        
        self.stateHandlerDict = {PyTango.DevState.ON: self.onHandler,
                                PyTango.DevState.STANDBY: self.standbyHandler,
                                PyTango.DevState.ALARM: self.alarmHandler,
                                PyTango.DevState.FAULT: self.faultHandler,
                                PyTango.DevState.INIT: self.initHandler,
                                PyTango.DevState.UNKNOWN: self.unknownHandler,
                                PyTango.DevState.OFF: self.offHandler}

        self.stopStateThreadFlag = False
        
        self.stateThread.start()
        
        self.hardwareLock = threading.Lock()
        self.stopHardwareThreadFlag = False
        
        self.oscilloscope = None
        self.oscilloscopeSetting = OscilloscopeSetting()

#------------------------------------------------------------------
#     Always excuted hook method
#------------------------------------------------------------------
    def always_executed_hook(self):
        pass


    def stateHandlerDispatcher(self):
        prevState = self.get_state()
        while self.stopStateThreadFlag == False:
            try:
                state = self.get_state()
                self.stateHandlerDict[state](prevState)
                prevState = state
            except KeyError:
                self.stateHandlerDict[PyTango.DevState.UNKNOWN](prevState)
                prevState = state


    def unknownHandler(self, prevState):
        self.info_stream('Entering unknownHandler')
        connectionTimeout = 1.0
        
        while self.get_state() == PyTango.DevState.UNKNOWN:
            self.info_stream('Trying to connect...')
            try:                
                self.oscilloscope = hc.Hameg_control(self.IPAddress)
                self.set_state(PyTango.DevState.INIT)
                self.info_stream('... connected')
                break
            
            except Exception, e:
                self.error_stream(''.join(('Could not create oscilloscope object.', str(e))))
                self.set_state(PyTango.DevState.UNKNOWN)
                self.set_status(''.join(('Could not create oscilloscope object.', str(e))))
                

            time.sleep(connectionTimeout)

    def initHandler(self, prevState):
        self.info_stream('Entering initHandler')
        self.set_state(PyTango.DevState.INIT)
        s_status = 'Starting initialization\n'
        self.set_status(s_status)
        self.info_stream(s_status)
        initTimeout = 1.0  # Retry time interval
        
        exitInitFlag = False  # Flag to see if we can leave the loop
        
        while exitInitFlag == False:
            time.sleep(initTimeout)
            exitInitFlag = True  # Preset in case nothing goes wrong
            try:
                s = ''.join(('Setting up device ', str(self.IPAddress), '\n'))
                s_status = ''.join((s_status, s))
                self.set_status(s_status)
                self.info_stream(s)            
                self.oscilloscope.setupInstrument()
            except Exception, e:
                self.error_stream('Could not open setup oscilloscope')
                exitInitFlag = False
                continue
            s = 'Setting attributes\n'
            s_status = ''.join((s_status, s))
            self.set_status(s_status)
            self.info_stream(s)
            try:
                attrs = self.get_device_attr()
                self.oscilloscopeSetting.timeBase = attrs.get_w_attr_by_name('TimeBase').get_write_value()
            except Exception, e:
                self.error_stream('Could not retrieve attribute TimeBase, using default value')
            try:                
                s = ''.join(('Time base ', str(self.oscilloscopeSetting.timeBase), ' s'))
                self.info_stream(s)
                self.info_stream(str(self.oscilloscope.trange))
                self.oscilloscope.setTimeRange(self.oscilloscopeSetting.timeBase)
            except Exception, e:
                exitInitFlag = False
                self.set_status(''.join(('Could not set time base: ', str(e))))
                self.error_stream(''.join(('Could not set time base: ', str(e))))
                continue

#            try:
#                self.info_stream('Trigger source')
#                self.oscilloscopeSetting.triggerSource = attrs.get_w_attr_by_name('TriggerSource').get_write_value()
#                s = ''.join(('Trigger source ', self.oscilloscopeSetting.triggerSource))
#                self.info_stream(s)
#            except Exception, e:
#                self.error_stream('Could not retrieve attribute TriggerSource, using default value')
#            try:
#                self.oscilloscope.setTrigSource(self.oscilloscopeSetting.triggerSource)
#            except Exception, e:
#                exitInitFlag = False
#                self.set_status(''.join(('Could not set trigger source: ', str(e))))
#                self.error_stream(''.join(('Could not set trigger source: ', str(e))))
#                continue

            try:
                self.oscilloscopeSetting.triggerLevel = attrs.get_w_attr_by_name('TriggerLevel').get_write_value()
                s = ''.join(('Trigger level ', str(self.oscilloscopeSetting.triggerLevel), ' V'))
                self.info_stream(s)
            except Exception, e:
                self.error_stream('Could not retrieve attribute TriggerLevel, using default value')
            try:
                self.oscilloscope.setTrigLevel(self.oscilloscopeSetting.triggerSource, self.oscilloscopeSetting.triggerLevel)
            except Exception, e:
                exitInitFlag = False
                self.set_status(''.join(('Could not set trigger level: ', str(e))))
                self.error_stream(''.join(('Could not set trigger level: ', str(e))))
                continue

            try:
                for ind, channel in enumerate(self.oscilloscopeSetting.channels):
                    self.info_stream(str(ind))
                    self.oscilloscope.setChannelState(ind + 1, channel.state)
#                    self.oscilloscope.setVerticalOffset(ind + 1, channel.offset)
#                    self.oscilloscope.setVerticalRange(ind + 1, channel.range)
                    self.commandQueue.put(OscilloscopeCommand('writeChannelState', (ind, True)))
            except Exception, e:
                exitInitFlag = False
                self.error_stream(''.join(('Could not set channel: ', str(e))))
                continue
                
            while self.commandQueue.empty() != True:
                self.checkCommands()
            self.info_stream('Initialization finished.')
            self.set_state(PyTango.DevState.STANDBY)

    def standbyHandler(self, prevState):
        self.info_stream('Entering standbyHandler')
        self.set_status('Connected to oscilloscope, not acquiring spectra')
        while self.stopStateThreadFlag == False:
            if self.get_state() != PyTango.DevState.STANDBY:
                break
            # Check if any new commands arrived:
            self.checkCommands()
            if self.get_state() != PyTango.DevState.STANDBY:
                break

            try:
                errorQueue = self.oscilloscope.getErrorQueue()
            except Exception, e:
                self.error_stream(''.join(('Error reading device', errorQueue)))
                self.set_state(PyTango.DevState.FAULT)
            time.sleep(0.1)


    def onHandler(self, prevState):
        self.info_stream('Entering onHandler')
        self.set_status('Connected to oscilloscope, acquiring')
#        newSpectrumTimestamp = time.time()
#        oldSpectrumTimestamp = time.time()
#        self.spectrumData = self.spectrometer.CCD
#        nextUpdateTime = time.time()
        try:
            self.oscilloscope.setAcquisition('run')
            self.info_stream('New acquisition: RUN')
        except Exception, e:
            self.set_state(PyTango.DevState.FAULT)
            self.set_status(''.join(('Could not set acquisition', str(e))))
            self.error_stream(''.join(('Could not set acquisition', str(e))))
        ch = 0
        t0 = time.time()
        while self.stopStateThreadFlag == False:
            if self.get_state() != PyTango.DevState.ON:
                break

            # Check if any new commands arrived:
            self.checkCommands()
            
            # Check if we should break this loop and go to a new state handler:
            if self.get_state() != PyTango.DevState.ON:
                break

            try:
                
                if self.oscilloscopeSetting.channels[ch].state == True:
                    self.oscilloscopeSetting.channels[ch].data = self.oscilloscope.getWaveform(ch + 1)
                    t = time.time()
#                    self.info_stream(''.join(('Channel ', str(ch), ': ', str(self.oscilloscopeSetting.channels[ch].data.shape),
#                                              ' points, cycle time: ', str(t - t0), ' s')))
                    t0 = t
                ch += 1
                if ch > 3:
                    ch = 0


            except Exception, e:
                # Immediately try again
                self.error_stream(''.join(('Error read waveform ', str(ch), ' : ', str(e))))
                try:
                    if self.oscilloscopeSetting.channels[ch].state == True:
                        self.oscilloscopeSetting.channels[ch].data = self.oscilloscope.getWaveform(ch + 1)
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status('Error reading hardware.')
                    self.error_stream(''.join(('Error getWaveform: ', str(e))))
            time.sleep(0.01)
            
    def alarmHandler(self, prevState):
        pass

    def faultHandler(self, prevState):
        responseAttempts = 0
        maxAttempts = 5
        responseTimeout = 0.5
        self.info_stream('Entering faultHandler.')
        self.set_status('Fault condition detected')
            
        while self.get_state() == PyTango.DevState.FAULT:
            # Test to just read the hardware the first time
            if responseAttempts == 0:
                try:
                    self.oscilloscope.getErrorQueue()
                    self.info_stream('Fault condition cleared.')
                    self.set_state(prevState)
                    break
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)

            try:                
                self.oscilloscope.close()
                self.oscilloscope.connect()
                
                self.set_state(prevState)
                self.info_stream('Fault condition cleared.')
                break
            except Exception, e:
                self.error_stream(''.join(('In faultHandler: Testing controller response. Returned ', str(e))))
                responseAttempts += 1
            if responseAttempts >= maxAttempts:
                self.set_state(PyTango.DevState.UNKNOWN)
                self.set_status('Could not connect to controller')
                self.error_stream('Giving up fault handling. Going to UNKNOWN state.')
                break
            time.sleep(responseTimeout)

    def offHandler(self, prevState):
        self.info_stream('Entering offHandler')
        try:
            self.oscilloscope.close()
        except Exception, e:
            self.error_stream(''.join(('Could not disconnect from oscilloscope, ', str(e))))
                
        self.set_status('Disconnected from oscilloscope')
        while self.stopStateThreadFlag == False:
            if self.get_state() != PyTango.DevState.OFF:
                break
            # Check if any new commands arrived:
            self.checkCommands()
            if self.get_state() != PyTango.DevState.OFF:
                break

            time.sleep(0.2)

    def checkCommands(self):
        try:
            cmd = self.commandQueue.get(block=False)
            self.info_stream(''.join(('In checkCommands: ', str(cmd.command))))
            if cmd.command == 'writeTimeBase':
                try:
                    self.oscilloscope.setTimeRange(cmd.data)
                    self.oscilloscopeSetting.timeBase = self.oscilloscope.trange
                    self.info_stream(''.join(('New time base: ', str(self.oscilloscopeSetting.timeBase))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set time base: ', str(e))))
                    self.error_stream(''.join(('Could not set time base: ', str(e))))
            elif cmd.command == 'writeTriggerMode':
                try:
                    self.oscilloscope.setTrigMode(cmd.data)
                    self.oscilloscopeSetting.triggerMode = self.oscilloscope.getTrigMode()
                    self.info_stream(''.join(('New trigger mode: ', str(self.oscilloscopeSetting.triggerMode))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set trigger mode: ', str(e))))
                    self.error_stream(''.join(('Could not set trigger mode: ', str(e))))
            elif cmd.command == 'writeTriggerOffset':
                try:
                    self.oscilloscope.setTrigOffset(cmd.data)
                    self.oscilloscopeSetting.triggerOffset = self.oscilloscope.getTrigOffset()
                    self.info_stream(''.join(('New trigger offset: ', str(self.oscilloscopeSetting.triggerOffset))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set trigger offset: ', str(e))))
                    self.error_stream(''.join(('Could not set trigger offset: ', str(e))))
            elif cmd.command == 'writeTriggerLevel':
                try:
                    self.oscilloscope.setTrigLevel(self.oscilloscopeSetting.triggerSource, cmd.data)
                    self.oscilloscopeSetting.triggerLevel = self.oscilloscope.getTrigLevel()
                    self.info_stream(''.join(('New trigger level: ', str(self.oscilloscopeSetting.triggerLevel))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set trigger level: ', str(e))))
                    self.error_stream(''.join(('Could not set trigger level: ', str(e))))
            elif cmd.command == 'writeTriggerSource':
                try:
                    self.oscilloscope.setTrigSource(cmd.data)
                    self.oscilloscopeSetting.triggerSource = self.oscilloscope.getTrigSource()
                    self.info_stream(''.join(('New trigger source: ', str(self.oscilloscopeSetting.triggerSource))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set trigger source: ', str(e))))
                    self.error_stream(''.join(('Could not set trigger source: ', str(e))))
            elif cmd.command == 'writeChannelState':
                try:
                    ch = cmd.data[0]
                    data = cmd.data[1]
                    self.oscilloscope.setChannelState(ch + 1, data)
                    self.oscilloscopeSetting.channels[ch].state = self.oscilloscope.getChannelState(ch + 1)
                    self.info_stream(''.join(('New channel ', str(ch + 1), ' state: ', str(self.oscilloscopeSetting.channels[ch].state))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set channel ', str(ch + 1), ' state: ', str(e))))
                    self.error_stream(''.join(('Could not set channel ', str(ch + 1), ' state: ', str(e))))
            elif cmd.command == 'writeChannelCoupling':
                try:
                    ch = cmd.data[0]
                    data = cmd.data[1]
                    self.oscilloscope.setCoupling(ch + 1, data)
                    self.oscilloscopeSetting.channels[ch].coupling = self.oscilloscope.getCoupling(ch + 1)
                    self.info_stream(''.join(('New channel ', str(ch + 1), ' coupling: ', str(self.oscilloscopeSetting.channels[ch].coupling))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set channel ', str(ch + 1), ' coupling: ', str(e))))
                    self.error_stream(''.join(('Could not set channel ', str(ch + 1), ' coupling: ', str(e))))
            elif cmd.command == 'writeChannelOffset':
                try:
                    ch = cmd.data[0]
                    data = cmd.data[1]
                    self.oscilloscope.setVerticalOffset(ch + 1, data)
                    self.oscilloscopeSetting.channels[ch].offset = self.oscilloscope.getVerticalOffset(ch + 1)
                    self.info_stream(''.join(('New channel ', str(ch + 1), ' offset: ', str(self.oscilloscopeSetting.channels[ch].offset))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set channel ', str(ch + 1), ' offset: ', str(e))))
                    self.error_stream(''.join(('Could not set channel ', str(ch + 1), ' offset: ', str(e))))
            elif cmd.command == 'writeChannelRange':
                try:
                    ch = cmd.data[0]
                    data = cmd.data[1]
                    self.oscilloscope.setVerticalRange(ch + 1, data)                    
                    self.oscilloscopeSetting.channels[ch].range = self.oscilloscope.getVerticalRange(ch + 1)
                    self.info_stream(''.join(('New channel ', str(ch + 1), ' range: ', str(self.oscilloscopeSetting.channels[ch].range))))
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set channel ', str(ch + 1), ' range: ', str(e))))
                    self.error_stream(''.join(('Could not set channel ', str(ch + 1), ' range: ', str(e))))
                    
            elif cmd.command == 'on':                
                self.set_state(PyTango.DevState.ON)
#                 self.startHardwareThread()

            elif cmd.command == 'stop':
                self.set_state(PyTango.DevState.STANDBY)
                
            elif cmd.command == 'off':
                self.set_state(PyTango.DevState.OFF)      

            elif cmd.command == 'run':
                self.set_state(PyTango.DevState.ON)

            elif cmd.command == 'single':
                try:
                    self.oscilloscope.setAcquisition('single')
                    self.info_stream('New acquisition: SINGLE')
                except Exception, e:
                    self.set_state(PyTango.DevState.FAULT)
                    self.set_status(''.join(('Could not set acquisition', str(e))))
                    self.error_stream(''.join(('Could not set acquisition', str(e))))
                
            else:
                self.info_stream('Unknown command')      

        except Queue.Empty:
            pass

    def stopStateThread(self):
        self.info_stream('Stopping thread...')
        self.stopStateThreadFlag = True
        if self.stateThread.isAlive() == True:
            self.info_stream('It was alive.')
            self.stateThread.join(3)
        self.info_stream('Now stopped.')
        self.stopStateThreadFlag = False
        self.set_state(PyTango.DevState.UNKNOWN)

#------------------------------------------------------------------
#     Read Attribute Hardware
#------------------------------------------------------------------
    def read_attr_hardware(self, data):
        pass

#==================================================================
#
#     HamegDS read/write attribute methods
#
#==================================================================

#------------------------------------------------------------------
#     TimeVector attribute
#------------------------------------------------------------------

#     Read attribute
    def read_TimeVector(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_TimeVector()")))
        
        attr_read = self.oscilloscopeSetting.timeVector
        attr.set_value(attr_read, attr_read.shape[0])
       
#---- Attribute State Machine -----------------
    def is_TimeVector_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     TimeBase attribute
#------------------------------------------------------------------

#     Read attribute
    def read_TimeBase(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_TimeBase()")))
        
        attr_read = self.oscilloscopeSetting.timeBase
        attr.set_value(attr_read)

#     Write attribute
    def write_TimeBase(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_TimeBase()")))
        data = attr.get_write_value()
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeTimeBase', data))
        
#---- Attribute State Machine -----------------
    def is_TimeBase_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True


#------------------------------------------------------------------
#     TriggerMode attribute
#------------------------------------------------------------------

#     Read attribute
    def read_TriggerMode(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_TriggerMode()")))
        
        attr_read = self.oscilloscopeSetting.triggerMode
        attr.set_value(attr_read)

#     Write attribute
    def write_TriggerMode(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_TriggerMode()")))
        data = attr.get_write_value()
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeTriggerMode', data))
        
#---- Attribute State Machine -----------------
    def is_TriggerMode_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     TriggerOffset attribute
#------------------------------------------------------------------

#     Read attribute
    def read_TriggerOffset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_TriggerOffset()")))
        
        attr_read = self.oscilloscopeSetting.triggerOffset
        attr.set_value(attr_read)

#     Write attribute
    def write_TriggerOffset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_TriggerOffset()")))
        data = attr.get_write_value()
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeTriggerOffset', data))
        
#---- Attribute State Machine -----------------
    def is_TriggerOffset_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     TriggerLevel attribute
#------------------------------------------------------------------

#     Read attribute
    def read_TriggerLevel(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_TriggerLevel()")))
        
        attr_read = self.oscilloscopeSetting.triggerLevel
        attr.set_value(attr_read)

#     Write attribute
    def write_TriggerLevel(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_TriggerLevel()")))
        data = attr.get_write_value()
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeTriggerLevel', data))
        
#---- Attribute State Machine -----------------
    def is_TriggerLevel_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     TriggerSource attribute
#------------------------------------------------------------------

#     Read attribute
    def read_TriggerSource(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_TriggerSource()")))
        
        attr_read = self.oscilloscopeSetting.triggerSource
        attr.set_value(attr_read)

#     Write attribute
    def write_TriggerSource(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_TriggerSource()")))
        data = attr.get_write_value()
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeTriggerSource', data))
        
#---- Attribute State Machine -----------------
    def is_TriggerSource_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel1Data attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel1Data(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel1Data()")))
        
        attr_read = self.oscilloscopeSetting.channels[0].data
        self.info_stream(str(attr_read.shape))
        attr.set_value(attr_read, attr_read.shape[0])
        
#---- Attribute State Machine -----------------
    def is_Channel1Data_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True
    
#------------------------------------------------------------------
#     Channel1State attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel1State(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel1State()")))
        
        attr_read = self.oscilloscopeSetting.channels[0].state
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel1State(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel1State()")))
        data = (0, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelState', data))
        
#---- Attribute State Machine -----------------
    def is_Channel1State_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel1Coupling attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel1Coupling(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel1Coupling()")))
        
        attr_read = self.oscilloscopeSetting.channels[0].coupling
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel1Coupling(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel1Coupling()")))
        data = (0, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelCoupling', data))
        
#---- Attribute State Machine -----------------
    def is_Channel1Coupling_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel1Offset attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel1Offset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel1Offset()")))
        
        attr_read = self.oscilloscopeSetting.channels[0].offset
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel1Offset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel1Offset()")))
        data = (0, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelOffset', data))
        
#---- Attribute State Machine -----------------
    def is_Channel1Offset_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel1Range attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel1Range(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel1Range()")))
        
        attr_read = self.oscilloscopeSetting.channels[0].range
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel1Range(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel1Range()")))
        data = (0, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelRange', data))
        
#---- Attribute State Machine -----------------
    def is_Channel1Range_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True            


#------------------------------------------------------------------
#     Channel2Data attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel2Data(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel2Data()")))
        
        attr_read = self.oscilloscopeSetting.channels[1].data
        self.info_stream(str(attr_read.shape))
        attr.set_value(attr_read, attr_read.shape[0])
        
#---- Attribute State Machine -----------------
    def is_Channel2Data_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True
    
#------------------------------------------------------------------
#     Channel2State attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel2State(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel2State()")))
        
        attr_read = self.oscilloscopeSetting.channels[1].state
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel2State(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel2State()")))
        data = (1, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelState', data))
        
#---- Attribute State Machine -----------------
    def is_Channel2State_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel2Coupling attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel2Coupling(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel2Coupling()")))
        
        attr_read = self.oscilloscopeSetting.channels[1].coupling
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel2Coupling(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel2Coupling()")))
        data = (1, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelCoupling', data))
        
#---- Attribute State Machine -----------------
    def is_Channel2Coupling_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel2Offset attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel2Offset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel2Offset()")))
        
        attr_read = self.oscilloscopeSetting.channels[1].offset
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel2Offset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel2Offset()")))
        data = (1, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelOffset', data))
        
#---- Attribute State Machine -----------------
    def is_Channel2Offset_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel2Range attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel2Range(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel2Range()")))
        
        attr_read = self.oscilloscopeSetting.channels[1].range
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel2Range(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel2Range()")))
        data = (1, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelRange', data))
        
#---- Attribute State Machine -----------------
    def is_Channel2Range_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True            


#------------------------------------------------------------------
#     Channel3Data attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel3Data(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel3Data()")))
        
        attr_read = self.oscilloscopeSetting.channels[2].data
        self.info_stream(str(attr_read.shape))
        attr.set_value(attr_read, attr_read.shape[0])
        
#---- Attribute State Machine -----------------
    def is_Channel3Data_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True
    
#------------------------------------------------------------------
#     Channel3State attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel3State(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel3State()")))
        
        attr_read = self.oscilloscopeSetting.channels[2].state
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel3State(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel3State()")))
        data = (2, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelState', data))
        
#---- Attribute State Machine -----------------
    def is_Channel3State_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel3Coupling attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel3Coupling(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel3Coupling()")))
        
        attr_read = self.oscilloscopeSetting.channels[2].coupling
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel3Coupling(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel3Coupling()")))
        data = (2, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelCoupling', data))
        
#---- Attribute State Machine -----------------
    def is_Channel3Coupling_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel3Offset attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel3Offset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel3Offset()")))
        
        attr_read = self.oscilloscopeSetting.channels[2].offset
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel3Offset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel3Offset()")))
        data = (2, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelOffset', data))
        
#---- Attribute State Machine -----------------
    def is_Channel3Offset_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel3Range attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel3Range(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel3Range()")))
        
        attr_read = self.oscilloscopeSetting.channels[2].range
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel3Range(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel3Range()")))
        data = (2, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelRange', data))
        
#---- Attribute State Machine -----------------
    def is_Channel3Range_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True            

#------------------------------------------------------------------
#     Channel4Data attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel4Data(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel4Data()")))
        
        attr_read = self.oscilloscopeSetting.channels[3].data
        self.info_stream(str(attr_read.shape))
        attr.set_value(attr_read, attr_read.shape[0])
        
#---- Attribute State Machine -----------------
    def is_Channel4Data_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True
    
#------------------------------------------------------------------
#     Channel4State attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel4State(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel4State()")))
        
        attr_read = self.oscilloscopeSetting.channels[3].state
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel4State(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel4State()")))
        data = (3, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelState', data))
        
#---- Attribute State Machine -----------------
    def is_Channel4State_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel4Coupling attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel4Coupling(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel4Coupling()")))
        
        attr_read = self.oscilloscopeSetting.channels[3].coupling
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel4Coupling(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel4Coupling()")))
        data = (3, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelCoupling', data))
        
#---- Attribute State Machine -----------------
    def is_Channel4Coupling_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel4Offset attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel4Offset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel4Offset()")))
        
        attr_read = self.oscilloscopeSetting.channels[3].offset
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel4Offset(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel4Offset()")))
        data = (3, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelOffset', data))
        
#---- Attribute State Machine -----------------
    def is_Channel4Offset_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True

#------------------------------------------------------------------
#     Channel4Range attribute
#------------------------------------------------------------------

#     Read attribute
    def read_Channel4Range(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::read_Channel4Range()")))
        
        attr_read = self.oscilloscopeSetting.channels[3].range
        attr.set_value(attr_read)

#     Write attribute
    def write_Channel4Range(self, attr):
        self.info_stream(''.join(("In ", self.get_name(), "::write_Channel4Range()")))
        data = (3, attr.get_write_value())
        self.info_stream(''.join(("Attribute value = ", str(data))))

        self.commandQueue.put(OscilloscopeCommand('writeChannelRange', data))
        
#---- Attribute State Machine -----------------
    def is_Channel4Range_allowed(self, req_type):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN,
                                PyTango.DevState.INIT]:
            return False
        return True            

#==================================================================
#
#     HamegDS command methods
#
#==================================================================

#------------------------------------------------------------------
#     On command:
#
#     Description: Connect and start aquiring
#                
#------------------------------------------------------------------
    def On(self):
        print "In ", self.get_name(), "::On()"
        #     Add your own code here
        self.commandQueue.put(OscilloscopeCommand('on'))


#---- On command State Machine -----------------
    def is_On_allowed(self):
        if self.get_state() in [PyTango.DevState.UNKNOWN]:
            #     End of Generated Code
            #     Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#     Stop command:
#
#     Description: Stop acquiring
#                
#------------------------------------------------------------------
    def Stop(self):
        print "In ", self.get_name(), "::Stop()"
        #     Add your own code here
        self.commandQueue.put(OscilloscopeCommand('stop'))


#---- Stop command State Machine -----------------
    def is_Stop_allowed(self):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN]:
            #     End of Generated Code
            #     Re-Start of Generated Code
            return False
        return True


#------------------------------------------------------------------
#     Off command:
#
#     Description: Disconnect from oscilloscope
#                
#------------------------------------------------------------------
    def Off(self):
        print "In ", self.get_name(), "::Off()"
        self.commandQueue.put(OscilloscopeCommand('off'))
        #     Add your own code here

#---- Off command State Machine -----------------
    def is_Off_allowed(self):
        if self.get_state() in [PyTango.DevState.UNKNOWN]:
            #     End of Generated Code
            #     Re-Start of Generated Code
            return False
        return True
    
#------------------------------------------------------------------
#     Run command:
#
#     Description: Continuous acquiring
#                
#------------------------------------------------------------------
    def Run(self):
        print "In ", self.get_name(), "::Run()"
        #     Add your own code here
        self.commandQueue.put(OscilloscopeCommand('run'))


#---- Stop command State Machine -----------------
    def is_Run_allowed(self):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN]:
            #     End of Generated Code
            #     Re-Start of Generated Code
            return False
        return True

#------------------------------------------------------------------
#     Single command:
#
#     Description: Single acquistion
#                
#------------------------------------------------------------------
    def Single(self):
        print "In ", self.get_name(), "::Single()"
        #     Add your own code here
        self.commandQueue.put(OscilloscopeCommand('single'))


#---- Stop command State Machine -----------------
    def is_Single_allowed(self):
        if self.get_state() in [PyTango.DevState.OFF,
                                PyTango.DevState.UNKNOWN]:
            #     End of Generated Code
            #     Re-Start of Generated Code
            return False
        return True



    
#==================================================================
#
#     HamegDSClass class definition
#
#==================================================================
class HamegDSClass(PyTango.DeviceClass):

    #     Class Properties
    class_property_list = {
        }


    #     Device Properties
    device_property_list = {
        'IPAddress':
            [PyTango.DevString,
            "IP address number of the oscilloscope",
            [ '130.235.94.72' ] ],
        }


    #     Command definitions
    cmd_list = {
        'On':
            [[PyTango.DevVoid, ""],
            [PyTango.DevVoid, ""]],
        'Stop':
            [[PyTango.DevVoid, ""],
            [PyTango.DevVoid, ""]],
        'Off':
            [[PyTango.DevVoid, ""],
            [PyTango.DevVoid, ""]],
        'Run':
            [[PyTango.DevVoid, ""],
            [PyTango.DevVoid, ""]],
        'Single':
            [[PyTango.DevVoid, ""],
            [PyTango.DevVoid, ""]],
        }


    #     Attribute definitions
    attr_list = {
        'Channel1Range':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel 1 voltage (total) range.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'Channel1Offset':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel 1 voltage (total) offset.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'Channel1Coupling':
            [[PyTango.DevString,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel analog input coupling. Valid entries: DC, DCLimit, AC, ACLimit, or GND",
                'Memorized':"true_without_hard_applied",
            } ],
        'Channel1State':
            [[PyTango.DevBoolean,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel enable state.",
                'Memorized':"true_without_hard_applied",
            } ],
        'Channel1Data':
            [[PyTango.DevDouble,
            PyTango.SPECTRUM,
            PyTango.READ, 6000],
            {
                'description':"Channel 1 trace.",
                'unit': 'V'
            }],
        'Channel2Range':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel voltage (total) range.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'Channel2Offset':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel voltage (total) offset.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'Channel2Coupling':
            [[PyTango.DevString,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel analog input coupling. Valid entries: DC, DCLimit, AC, ACLimit, or GND",
                'Memorized':"true_without_hard_applied",
            } ],
        'Channel2State':
            [[PyTango.DevBoolean,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel enable state.",
                'Memorized':"true_without_hard_applied",
            } ],
        'Channel2Data':
            [[PyTango.DevDouble,
            PyTango.SPECTRUM,
            PyTango.READ, 6000],
            {
                'description':"Channel trace.",
                'unit': 'V'
            }],
        'Channel3Range':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel voltage (total) range.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'Channel3Offset':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel voltage (total) offset.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'Channel3Coupling':
            [[PyTango.DevString,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel analog input coupling. Valid entries: DC, DCLimit, AC, ACLimit, or GND",
                'Memorized':"true_without_hard_applied",
            } ],
        'Channel3State':
            [[PyTango.DevBoolean,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel enable state.",
                'Memorized':"true_without_hard_applied",
            } ],
        'Channel3Data':
            [[PyTango.DevDouble,
            PyTango.SPECTRUM,
            PyTango.READ, 6000],
            {
                'description':"Channel trace.",
                'unit': 'V'
            }],
        'Channel4Range':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel voltage (total) range.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'Channel4Offset':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel voltage (total) offset.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'Channel4Coupling':
            [[PyTango.DevString,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel analog input coupling. Valid entries: DC, DCLimit, AC, ACLimit, or GND",
                'Memorized':"true_without_hard_applied",
            } ],
        'Channel4State':
            [[PyTango.DevBoolean,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Channel enable state.",
                'Memorized':"true_without_hard_applied",
            } ],
        'Channel4Data':
            [[PyTango.DevDouble,
            PyTango.SPECTRUM,
            PyTango.READ, 6000],
            {
                'description':"Channel trace.",
                'unit': 'V'
            }],
        'TriggerSource':
            [[PyTango.DevString,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Trigger source. Valid entries: ch1, ch2, ch3, ch4, ext, line",
                'Memorized':"true_without_hard_applied",
            } ],
        'TriggerLevel':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Voltage level at which the trigger is generated.",
                'Memorized':"true_without_hard_applied",
                'unit': 'V'
            } ],
        'TriggerOffset':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Trigger offset relative the reference time position.",
                'Memorized':"true_without_hard_applied",
                'unit': 's'
            } ],
        'TriggerMode':
            [[PyTango.DevString,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Trigger mode. Valid entries: auto, normal",
                'Memorized':"true_without_hard_applied",
            } ],
        'TimeBase':
            [[PyTango.DevDouble,
            PyTango.SCALAR,
            PyTango.READ_WRITE],
            {
                'description':"Time range for the waveforms.",
                'Memorized':"true_without_hard_applied",
                'unit': 's'
            } ],
        'TimeVector':
            [[PyTango.DevDouble,
            PyTango.SPECTRUM,
            PyTango.READ, 6000],
            {
                'description':"Vector with the time values for the current horizontal setup.",
                'unit': 's'
            }],
                 
        }

#------------------------------------------------------------------
#     HamegDSClass Constructor
#------------------------------------------------------------------
    def __init__(self, name):
        PyTango.DeviceClass.__init__(self, name)
        self.set_type(name);
        print "In HamegDSClass  constructor"

#==================================================================
#
#     SPM002_DS class main method
#
#==================================================================
if __name__ == '__main__':
    try:
        py = PyTango.Util(sys.argv)
        py.add_TgClass(HamegDSClass, HamegDS, 'HamegDS')

        U = PyTango.Util.instance()
        U.server_init()
        U.server_run()

    except PyTango.DevFailed, e:
        print '-------> Received a DevFailed exception:', e
    except Exception, e:
        print '-------> An unforeseen exception occured....', e
