#!/usr/bin/env python
# *-* coding: utf-8 *-*
# TODO:
#    * Introspect for service help
#    * Sessions to allow only one session to control the arm at once. It should
#      have timeout functionality, session release, aquire, etc.
#    * JSON/HTML?YAML/TEXT optional output from services
#    * Handle assertions and errors in page handlers and return HTML error code.
"""
MeArm controller REST service.

This app exposes a RESTful web service to control the MeArm from the a
RaspberryPi connected to the MeArmI²C arduino via I²C.
"""

import os, os.path
import json
import time
import uuid
import cherrypy

from MeArm import armDef, MeArm

## The maximum inactive period for the bearer of the control stick.
CONTROL_STICK_TIMEOUT = 60

def checkControlExpiration():
    """
    Checks if the control stick control session has expired, and if so, reset it
    to None.
    """
    # If no-one has the stick, we return
    if cherrypy.controlStick is None:
        return
    # Has it expired?
    if time.time() > cherrypy.controlStick['tmout']:
        # Yep, release control
        cherrypy.controlStick = None

def controlStickTool(noControlError=False):
    """
    Tool that gets called before every requests to see if the caller has the
    "control stick". Having the control stick means that the user of this
    session is allowed to control the arm, to ensure that only one user can take
    control at a time.

    To get the "control stick", the user first needs to call the
    services/takeStick endpoint. If the control stick is available, the user's
    session will get a UUID (if it does not already have one) and the control
    stick assigned to that session.

    The control stick itself is the locally added cherrypy.controlStick
    attribute. When the stick is not in anyone's control, this attribute is
    None. As soon as someone takes control, it is set to the following dict:
        
        {'sid': session ID of controller,
         'tmout': a unix time stamp of when control will be lost without any
                  further control actions.
        }

    Every call through this tool by the session owner that has control of the
    stick, will set the time out for the control period to the current time +
    CONTROL_STICK_TIMEOUT unless the current time is past the last tmout value,
    in which case cherrypy.controlStick is reset to None. This will either
    extend the current controll period, or relinquish control of the stick on
    timeout.
    """
    # Preset the request.inControl indicator to False to show the current
    # session does not have control of the arm.
    cherrypy.request.inControl = False

    # Get the session ID from the session if any
    sid = cherrypy.session.get('id', None)
    # Check for expiration regardless of stick control
    checkControlExpiration()

    # If the control stick is in no-ones hands, or not in the hands of the
    # current session owner, return or raise error
    if cherrypy.controlStick is None or cherrypy.controlStick['sid'] != sid:
        if noControlError:
            raise cherrypy.HTTPError(400, "You do not have control.")
        return

    # The current session own the stick, so extend the period before timeout.
    cherrypy.controlStick['tmout'] = time.time() + CONTROL_STICK_TIMEOUT
    # Indicate that this session has control
    cherrypy.request.inControl = True

# Add the control stick tool before the handler is called.
cherrypy.tools.controlStick = cherrypy.Tool('before_handler',
                                             controlStickTool)



class UI(object):
    """
    This class exposes the main web UI to load the HTML.
    """

    @cherrypy.expose
    def index(self):
        """
        Main index.
        """
        return open('web/html/index.html')


def servicesErrorHandler(status, message, traceback, version):
    """
    Formats the error as a JSON string.

    @param status: The HTTP error status
    @param message: The error message
    @param traceback: The traceback if any
    @param version: The cherrypy version
    """
    # The basic info
    err = {'status': status, 'message': message}
    # add a traceback if any
    if traceback:
        err['traceback'] = traceback

    # Set content type header
    cherrypy.response.headers["content-type"] = "application/json";
    # Serialize to json and return
    return json.dumps(err)

class WebService(object):
    """
    The service base for the MeArm exposed REST services.

    The dispatch method for this class and all it's sub-path end points will all
    use the MethodDispatcher and therefore it only handles the GET method which
    will give help on how to use the service.
    """
    exposed = True
    _cp_config = {'error_page.default': servicesErrorHandler}

    serviceHelp = """
    <!DOCTYPE>
    <html>
    This will be the service help page for MeArm Service.
    </html>
    """

    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.response_headers(headers=[('Content-Type', 'text/html')])
    def GET(self):
        return self.serviceHelp

class Arm(object):
    """
    The service base for the Arm exposed REST services.

    The dispatch method for this class and all it's sub-path end points will all
    use the MethodDispatcher and therefore it only handles the GET method which
    will give help on how to use the service.
    """
    exposed = True

    serviceHelp = """
    <!DOCTYPE>
    <html>
    This will be the service/arm help page for MeArm Service.
    </html>
    """

    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.response_headers(headers=[('Content-Type', 'text/html')])
    def GET(self):
        return self.serviceHelp

class Joint(object):
    """
    Base class for service exposure for control and access to one joint in the
    arm.

    Instances of this class are meant to be hooked into the services endpoint to
    expose a controler endpoint for the given joint.

    On instantiation, this instance will automatically set it's own instance
    level 'exposed'attribute to True to allow cherrypy to dispatch to methods in
    this joint handler.
    """

    def __init__(self, jointName):
        """
        Instantiates a joint for the given joint name.

        @param jointName: The joint this instance will be controlling. It must
               one of the strings: 'Base', 'Shoulder', 'Wrist' or 'Grip'.
        """
        self.jointName = jointName
        # Expose this instace to cherrypy
        self.exposed = True

    def GET(self, *args, **kwargs):
        """
        Return the current joint position, min or max positions, or all joint
        info.

        Only using the base joint request path will return the current joint
        position. Any or all of the other information can be accessed by
        appending an additional component to the base path to indicate the
        information required:

            ../services/joint        -return the current joint position
            ../services/joint/pos    -return the current joint position
            ../services/joint/min    -return the joint minimum position
            ../services/joint/max    -return the joint maximum position
            ../services/joint/limits -return the joint min and max positions
            ../services/joint/info   -return the current, min and max positions

        @keyword args: Optionally one of 'pos', 'min', 'max', 'limits' or 'info'
                 to indicate other than standard postion to return.

        @return: A dictionary with keys 'pos', 'min', 'max' keywords with the
                 requested values. One or more of these keys will be present.
        """
        print "In control: ", cherrypy.request.inControl

        arm = cherrypy.config['MeArmIF']
        joint = getattr(arm, self.jointName.lower())

        # Any additional detail required?
        print args
        detail = None if len(args)==0 else args[0].lower()
        print detail
        if detail not in [None, 'pos', 'min', 'max', 'limits', 'info']:
            raise cherrypy.HTTPError(400, "Invalid joint details request: {}"\
                                     .format(detail))
        # Set up the return
        res = {}
        if detail in [None, 'pos', 'info']:
            res['pos'] = arm.getPos(joint)
        if detail in ['min', 'limits', 'info']:
            res['min'] = joint['min']
        if detail in ['max', 'limits', 'info']:
            res['max'] = joint['max']

        return res

    @cherrypy.tools.controlStick(noControlError=True)
    def PUT(self, *args, **kwargs):
        """
        Set the current joint position and/or min and/or max limit.

        We expect a JSON document in the format:
            { 'pos': integer ≥ min and ≤ max,
              'min': integer ≥ 0 and ≤ 180,
              'max': integer ≥ 0 and ≤ 180,
            }
        where any of the fields are optional, but at least one is required.
        """
        print "In control: ", cherrypy.request.inControl
        # Get the JSON doc as input from the request
        json = getattr(cherrypy.request, 'json', None)
        arm = cherrypy.config['MeArmIF']
        joint = getattr(arm, self.jointName.lower())
        # Validate the input and set each attribute as requested
        if json is None:
            raise cherrypy.HTTPError(400, "Expected a JSON postion object.")
        if len(json)==0:
            raise cherrypy.HTTPError(400, "Expected a non-empty JSON object.")
        for k in json:
            if k not in ['pos', 'min', 'max']:
                raise cherrypy.HTTPError(400, "Invalid attribute: {}".format(k))
            v = json[k]
            if not isinstance(v, (int, float)):
                raise cherrypy.HTTPError(400, "Integer or float expected for "\
                                         "'{}', got: {}".format(k, v))
            # Set the attribute
            try:
                if k == 'pos':
                    json[k] = arm.goto(joint, v)
                else:
                    a = {k+'L': v}
                    arm.setLimit(joint, **a)
                    json[k] = joint[k]
            except (ValueError, IOError), e:
                raise cherrypy.HTTPError(400, str(e.args[0]))

        return json

class ControlStick(object):
    """
    Control stick service.

    This services will allow taking the control stick ("GET") and releasing it
    again on completion ("DELETE") by a user/session.
    """
    exposed = True

    def GET(self, name=None):
        """
        Grabs the control stick if it is available.

        On success returns: 200 - OK, you've got the stick
        If not available returns: 402 - Payment required
        """
        # Validate and clean name
        name = None if name.strip()=="" else name.strip()

        # If the stick is not avail, and I'm not already in control, return 402
        if cherrypy.controlStick is not None and not cherrypy.request.inControl:
            msg = "Ask {0[name]} at {0[ip]}, or wait {1}s"\
                    .format(cherrypy.controlStick,
                            cherrypy.controlStick['tmout']-time.time())
            raise cherrypy.HTTPError(402, msg)

        # If the stick is avaiable, grab it
        if cherrypy.controlStick is None:
            # Does this session have an ID?
            if not cherrypy.session.get('id', False):
                cherrypy.session['id'] = str(uuid.uuid1())
            # Grab the stick
            cherrypy.controlStick = {
                'sid': cherrypy.session['id'],
                'tmout': time.time() + CONTROL_STICK_TIMEOUT,
                'name': 'Anonymous' if name is None else name,
                'ip': cherrypy.request.remote.ip
            }

        # At this point we either already had control, or we just took control.
        cherrypy.response.status = "200 OK, you've got the stick."

    def DELETE(self):
        """
        Release stick if you have it.
        """
        # If you are in control, release it
        if cherrypy.request.inControl:
            cherrypy.controlStick = None
            cherrypy.request.inControl = False
        else:
            # It's not your's to release
            raise cherrypy.HTTPError('400', "Not your's to release...")

        cherrypy.response.status = "200 OK, thanks for playing."

class Camera(object):
    """
    Base class for camera interfacing.
    """

    @cherrypy.expose()
    def URL(self):
        """
        Returns the video stream URL as a plain text string.
        """
        return cherrypy.config['camera.url']

    @cherrypy.expose()
    def view(self):
        """
        Sample HTML5 page for streaming camera view
        """
        pg = """<!DOCTYPE html>
        <html>
            <head>
                <title>Sample HTML5 Camera Stream</title>
            </head>
            <body>
            <h4>Camera view</h4>
            <img src="{}"></img>
            </body>
        </html>
        """.format(cherrypy.config['camera.url'])
        cherrypy.response.headers["content-type"] = "text/html";
        import re
        # Remove the spaces on the start of lines from the HTML
        return re.sub('^ {8}', '', pg, flags=re.M)

if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8081,
        'server.thread_pool': 10,
        'server.thread_pool_max': -1,
        # Set up arm instance in config
        'MeArmIF': MeArm(**armDef),
        # Camera config
        'camera.url': 'http://fruitix:8080/?action=stream',
    })
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
            # Make sure we switch the control stick tool on.
            'tools.controlStick.on': True,
        },
        '/services': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.json_in.on': True,
            'tools.json_out.on': True,
        },
        '/services/arm': {
            # Return an error unless the requestor has the stick
            #'tools.controlStick.noControlError': True,
        },
        '/services/camera': {
            # Default dispatcher
            'request.dispatch': cherrypy.dispatch.Dispatcher(),
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'text/plain')],
            'tools.json_in.on': False,
            'tools.json_out.on': False,
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './web'
        }
    }
    # Hang the UI off '/'
    webapp = UI()

    # Set up the main /services/ endpoint
    webapp.services = WebService()
    webapp.services.arm = Arm()
    # Add the various joints
    webapp.services.arm.base = Joint('Base')
    webapp.services.arm.shoulder = Joint('Shoulder')
    webapp.services.arm.wrist = Joint('Wrist')
    webapp.services.arm.grip = Joint('Grip')
    # Set up the control stick endpoint
    webapp.services.control = ControlStick()
    # The camera interface
    webapp.services.camera = Camera()

    # The actual control stick container.
    cherrypy.controlStick = None

    # Start the app
    cherrypy.quickstart(webapp, '/', conf)
