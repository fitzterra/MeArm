#!/usr/bin/env python
# *-* coding: utf-8 *-*
# TODO:
#    * Introspect for service help
#    * Sessions to allow only one session to control the arm at once. It should
#      have timeout functionality, session release, aquire, etc.
#    * JSON/HTML?YAML/TEXT optional output from services
#    * Confirm instantiating the MeArmI2C instance in the global config is the
#      best place to this. Where best to place the MeArm I²C address?
#    * Handle assertions and errors in page handlers and return HTML error code.
"""
MeArm controller REST service.

This app exposes a RESTful web service to control the MeArm from the a
RaspberryPi connected to the MeArmI²C arduino via I²C.
"""

import os, os.path
import json
import cherrypy

from MeArmControl import MeArmI2C

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
    This will be the service help page for MeArmI²C.
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
        # Determine and validate the joint register based on jointName
        self.jointReg = getattr(MeArmI2C, 'Reg'+jointName, None)
        assert self.jointReg is not None, "Invalid joint name: {}"\
                                          .format(jointName)
        self.jointName = jointName
        # Expose this instace to cherrypy
        self.exposed = True

    def GET(self, *args, **kwargs):
        """
        Return the current joint position, min or max positions, or a
        all joint info.

        Only using gthe base joint request path will return the current joint
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
        arm = cherrypy.config['MeArmIF']

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
            res['pos'] = arm.joint(self.jointReg)
        if detail in ['min', 'limits', 'info']:
            res['min'] = arm.jointLimit(self.jointReg, 'min')
        if detail in ['max', 'limits', 'info']:
            res['max'] = arm.jointLimit(self.jointReg, 'max')

        return res

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
        # Get the JSON doc as input from the request
        json = getattr(cherrypy.request, 'json', None)
        arm = cherrypy.config['MeArmIF']
        # Validate the input and set each register as requested
        if json is None:
            raise cherrypy.HTTPError(400, "Expected a JSON postion object.")
        if len(json)==0:
            raise cherrypy.HTTPError(400, "Expected a non-empty JSON object.")
        for k in json:
            if k not in ['pos', 'min', 'max']:
                raise cherrypy.HTTPError(400, "Invalid register: {}".format(k))
            v = json[k]
            if not isinstance(v, int):
                raise cherrypy.HTTPError(400, "Integer expected for '{}', "\
                                         "got: {}".format(k, v))
            if not (0 <= v <= 180):
                raise cherrypy.HTTPError(400, "{} out of limits for {}"\
                                         .format(v, k))
            # Set the register
            try:
                if k == 'pos':
                    json[k] = arm.joint(self.jointReg, v)
                else:
                    json[k] = arm.jointLimit(self.jointReg, k, v)
            except (ValueError, IOError), e:
                raise cherrypy.HTTPError(400, str(e.args[0]))

        return json




if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8081,
        'server.thread_pool': 10,
        'server.thread_pool_max': -1,
        'MeArmIF': MeArmI2C(42),
    })
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
        },
        '/services': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            #'tools.response_headers.on': True,
            #'tools.response_headers.headers': [('Content-Type', 'text/plain')],
            'tools.json_in.on': True,
            'tools.json_out.on': True,
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
    # Add the various joints
    webapp.services.base = Joint('Base')
    webapp.services.shoulder = Joint('Shoulder')
    webapp.services.wrist = Joint('Wrist')
    webapp.services.grip = Joint('Grip')

    # Start the app
    cherrypy.quickstart(webapp, '/', conf)
