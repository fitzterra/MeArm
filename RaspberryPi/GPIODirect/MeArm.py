# *-* coding: utf-8 *-*
"""
MeArm controller via pigpio.
"""

import pigpio

# Some defaults to make it easier to instantiate a MeArm object.
armDef = {
    'base': {'gpio':  4, 'min':  0, 'max': 180, 'home': 90, 'inv': True},
    'shoulder': {'gpio': 17, 'min': 50, 'max': 140, 'home': 90},
    'wrist': {'gpio': 27, 'min': 50, 'max': 140, 'home': 90},
    'grip': {'gpio': 22, 'min': 80, 'max': 100, 'home': 90}
}

class MeArm(object):
    """
    MeArm joint/angle controller.
    """

    def __init__(self, base, shoulder, wrist, grip, pwMin=550, pwMax=2500):
        """
        Instance initialization.

        Each of the parameters is a dictionary representing one joint. The
        format is:

            {
                'gpio': The gpio pin this joint's servo is connected to.
                'min': The minimum allowed angle for the joint servo.
                'max': The maximum allowed angle for the joint servo.
                'home': The home angle for the joint servo.
                'inv': Invert direction indicator. True/False and optional.
            }

        @param base: Base joint definition
        @param shoulder: Shoulder joint definition
        @param wrist: Wrist joint definition
        @param grip: Grip joint definition
        @param pwMin: Minimum allowed pulse with for servo to get to 0°
        @param pwMax: Maximum allowed pulse with for servo to get to 180°
        """
        # NOTE: We do not validate here, so we simply assign to instance local
        # params and add names to the joint definitions.
        self.base = base
        self.base['name'] = 'base'

        self.shoulder = shoulder
        self.shoulder['name'] = 'shoulder'

        self.wrist = wrist
        self.wrist['name'] = 'wrist'

        self.grip = grip
        self.grip['name'] = 'grip'

        # Save min/max servo pulse widths
        self.pwMin = pwMin
        self.pwMax = pwMax

        # Calculate the pulse width per degree of angle
        self.pwPdeg = (pwMax - pwMin) / 180.0

        # Set up instance of pigpio
        self.io = pigpio.pi()
        # Home them all
        self.homeAll()

    def angleToPulse(self, a):
        """
        Converts and angle to a pulse width for the servo.

        Calculation is based on the calculated pulse width per degree value.
        """
        return int((a * self.pwPdeg) + self.pwMin)

    def pulseToAngle(self, p):
        """
        Converts a pulse width to an angle for the servo.

        Calculation is based on the calculated pulse width per degree value.
        """
        # For the 9g servos used for testing, the min effective pulse width is
        # 550 and max is 2500 - this does not equate to a perfect 180° and there
        # is some degree of error when converting back to angle from pulse
        # width. The precision modifier below is applied to the calculated value
        # before rounding to 1 decimal digit to get a more accurate angle in
        # degrees.
        pm = 0.05
        calcDeg = (p - self.pwMin) / self.pwPdeg
        return round(calcDeg+pm, 1)

    def getPos(self, joint, deg=True):
        """
        Returns the current pulse width or angle (if deg is True) for the given
        joint.

        @param joint: The joint definition
        @param deg: If true, convert the pulse width to an angle in degrees,
               else return the pulse width.
        @return: None if the servo is current off, or else the angle or pulse
                 width
        """
        pw = self.io.get_servo_pulsewidth(joint['gpio'])
        if pw == 0:
            return None

        # Convert?
        if deg:
            return self.pulseToAngle(pw)
        else:
           return pw

    def goto(self, joint, pos):
        """
        Positions a joint to the requested position.

        @param joint: The joint definition
        @param pos: The position as an angle. May be a floating point value to
               0.1° accuracy.
        @return: The position read from pigpio
        """
        # Validate that the requested angle in withing the join limits before
        # setting the angle
        if (joint['min'] <= pos <= joint['max']):
            # Handle inverted position here
            a = joint['max']-(pos-joint['min']) if joint.get('inv', False) else pos
            self.io.set_servo_pulsewidth(joint['gpio'], self.angleToPulse(a))
        else:
            raise ValueError("Angle {} outside of limits for {} ({} - {})"\
                             .format(pos, joint['name'], joint['min'],
                                     joint['max']))
        return self.getPos(joint)

    def home(self, joint):
        """
        Homes a joint by setting the angle to it's home position.

        @param joint: one of the local joint instance config dictionaries
        """
        self.goto(joint, joint['home'])

    def homeAll(self):
        """
        Homes all joints
        """
        for j in [self.base, self.shoulder, self.wrist, self.grip]:
            self.home(j)

    def setLimit(self, joint, minL=None, maxL=None):
        """
        Set a min and/or max limit for for the given joint.
        """
        # Min?
        if minL is not None:
            # Validate - max is either the new max value, else the current
            mx = maxL if maxL is not None else joint['max']
            if minL > mx:
                raise ValueError("Can not set min limit ({}) higher than max "\
                                 "({}) for {}.").format(minL, mx, joint['name'])
            if minL < 0:
                raise ValueError("Can not set min limit less than 0 for {}.")\
                                 .format(joint['name'])
            # Set the limit
            joint['min'] = minL
            # Do we need to move to this new limit
            if self.getPos(joint) < minL:
                self.goto(joint, minL)
        # Max?
        if maxL is not None:
            # Validate
            if maxL < joint['min']:
                raise ValueError("Can not set max limit ({}) less than min "\
                                 "({}) for {}.".format(maxL, joint['min'],
                                                        joint['name']))
            if maxL > 180:
                raise ValueError("Can not set max limit greater than 180 "\
                                 "for {}.".format(joint['name']))
            # Set the limit
            joint['max'] = maxL
            # Do we need to move to this new limit
            if self.getPos(joint) > maxL:
                self.goto(joint, maxL)

    def qtest(self):
        """
        Runs a quick test for all joints. This is meant to be run with only
        servos connected instead of the complete arm. This precaution is there
        to prevent damage to the arm should any min/max positions be incorrect.
        """
        import time
        # Get all servos to min position
        for j in [self.base, self.shoulder, self.wrist, self.grip]:
            self.goto(j, j['min'])

        # Step all from min to max and back to min wit 0.5° steps
        a = 0.5
        step = 0.5
        while a>=0:
            print a,
            for j in [self.base, self.shoulder, self.wrist, self.grip]:
                try:
                    self.goto(j, a)
                    print "{0:10.2f}".format(self.getPos(j)),
                except ValueError:
                    pass
            print
            a += step
            if a>=180:
                step = -0.5
                a = 180

        for j in [self.base, self.shoulder, self.wrist, self.grip]:
            self.goto(j, j['max'])
            time.sleep(0.5)
            self.goto(j, j['min'])

        self.homeAll()
                


if __name__ == "__main__":
    # Instantiate an arm instance
    arm = MeArm(**armDef)
    # Run the self test
    arm.qtest()


