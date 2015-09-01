#!/usr/bin/python
# -*- coding: utf-8 -*-

##
# Control interface and API for MeArm-over-I²C controller.
##

import smbus
import time

class MeArmI2C:
    """
    Class that defines the MeArm controller.
    """

    # Class attributes for each register
    RegErr      = ord('e')
    RegConfig   = ord('c')
    RegBase     = ord('b')
    RegShoulder = ord('s')
    RegWrist    = ord('w')
    RegGrip     = ord('g')

    # Register Sub-value indicator
    RegSubMin = 0b11000001
    RegSubMax = 0b11000010


    # Operation error values
    OpErrors = {
        1<<0: {"c": "eDLen", "e": "Data length - too much or too little data"},
        1<<1: {"c": "eNoReg", "e": "Invalid register error"},
        1<<2: {"c": "ePLimit", "e": "Position to set is out of poistion limits"},
        1<<3: {"c": "eSVLimit", "e": "Sub value is out of min/max limits"},
        1<<4: {"c": "eSVRange", "e": "Sub value is out of allowed range"},
        1<<5: {"c": "eInvSubVal", "e": "Invalid sub-value indicator"},
    };


    def __init__(self, i2cAddr, devInf=1):
        """
        Instance intialization.
        
        @param i2cAddr: The address for the MeArm I²C slave
        @param devInf: I²C device interface. On revision 1 boards this is bus 1,
                    and on pre revision 1 boards this is bus 0 (what is revision
                    1 board??)
        """
        self.i2cAddr = i2cAddr
        # Buss instance
        self.bus = smbus.SMBus(1)

    def _settleDelay(self):
        """
        Call this inbetween successive write/read operations to allow the bus to
        settle before the next operation.

        By always using this method, the settle delay time can be adjusted in
        one place for the complete system.
        """
        time.sleep(0.1)

    def getError(self):
        """
        Reads the arm controller error register and raises an excpetion with
        appropriate message in case of an error condition.
        """
        # Write the register address to the slave
        self.bus.write_byte(self.i2cAddr, self.RegErr)
        self._settleDelay()
        # Now read the bus for the value
        val = self.bus.read_byte(self.i2cAddr)
        if val:
            e = self.OpErrors[val]
            raise IOError({"code": e["c"], "err": e["e"]})

    def getRegister(self, reg):
        """
        Reads the given register content from the arm controller.

        @param reg: The register to read. Use the Reg* class attributes to
                    ensure the correct register value is specified.

        @return: the *single* register value read from the arm controller

        @raises: IOError and a message if an error occured reading the register.
        """
        # Write the register address to the slave
        self.bus.write_byte(self.i2cAddr, reg)
        self._settleDelay()
        # Now read the bus for  the value
        val = self.bus.read_byte(self.i2cAddr)
        # Check for error which will raise IOError if there is an error.
        self.getError()

        return val

    def getRegisterSubVal(self, reg, subInd):
        """
        Reads a sub value for the given register.

        @param reg: The register to read. Use the Reg* class attributes to
               ensure the correct register value is specified.
        @param subInd: The sub-value indicator. Use one of the RegSub* class
               attributes to ensure the correct indicator value.

        @return: The requested sub value read from the arm controller

        @raises: IOError and a message if an error occured reading the register.
        """
        # Write the register address and sub value indicator to the slave
        self.bus.write_byte_data(self.i2cAddr, reg, subInd)
        self._settleDelay()
        # Now read the bus for  the value
        val = self.bus.read_byte(self.i2cAddr)
        # Check for error which will raise IOError if there is an error.
        self.getError()

        return val

    def setRegister(self, reg, val):
        """
        Sets the given register value on the arm controller.

        @param reg: The register to set. Use the Reg* class attributes to
                    ensure the correct register value is specified.
        @param val: The value to set the register to.

        @raises: IOError and a message if an error occured reading the register.
        """
        # Set the register
        self.bus.write_byte_data(self.i2cAddr, reg, val);
        self._settleDelay()
        # Check for error
        self.getError()

    def setRegisterSubValue(self, reg, subInd, val):
        """
        Sets the given register sub-value on the arm controller.

        @param reg: The register to set. Use the Reg* class attributes to
               ensure the correct register value is specified.
        @param subInd: The sub-value indicator. Use one of the RegSub* class
               attributes to ensure the correct indicator value.
        @param val: The value to set for this register sub-value.

        @raises: IOError and a message if an error occured reading the register.
        """
        # Set the register sub value
        self.bus.write_i2c_block_data(self.i2cAddr, reg, [subInd, val]);
        self._settleDelay()
        # Check for error
        self.getError()

    def joint(self, name, pos=None):
        """
        Gets or sets the position for a joint.

        @param name: The joint name as defined by one of the Reg* class
               attributes.
        @param pos: If supplied, set the joint position to this position in
               degrees, and returns the new position. If not supplied, or None,
               only return the current position.
        @return: The current or new position that was set.
        @raises: IOError if an error occurs.
        """
        # Do we set or get?
        if pos is None:
            p = self.getRegister(name)
        else:
            self.setRegister(name, pos)
            p = pos

        return p

    def jointLimit(self, name, limInd, lim=None):
        """
        Gets or sets a joint position limit.

        @param name: The joint name as defined by one of the Reg* class
               attributes.
        @param limInd: An indicator of which limit to set. One of the strings
               "min" or "max".
        @param lim: If supplied, set the joint limit to this value in degrees,
               and returns the new limit. If not supplied, or None, only return
               the current limit.

        @return: The current or new joint limit that was set.
        @raises: IOError if an error occurs.
        @raises: ValueError if limInd is invalid.
        """
        # Validate limInd
        if limInd == "min":
            subInd = self.RegSubMin
        elif limInd == "max":
            subInd = self.RegSubMax
        else:
            raise ValueError, "Invalid limit indicator: {}. Should be 'min' or "\
                              "'max' only.".format(limInd)

        # Do we set or get?
        if lim is None:
            l = self.getRegisterSubVal(name, subInd)
        else:
            self.setRegisterSubValue(name, subInd, lim)
            l = lim

        return l

    def close(self):
        """
        Closes the connection to the SMBus.
        """
        self.bus.close()
