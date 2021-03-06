"""
Flask web server for frontend
"""

from flask import Flask, request, render_template, redirect, url_for, jsonify, send_file, json, Response, abort, make_response
import mimetypes
from time import time, sleep
from functools import wraps
from util import log
from uuid import uuid4
import zmq
from ip_receiver import IPReceiver
from werkzeug import secure_filename
from urllib import quote, quote_plus

try:
    import sagecell_config
except ImportError:
    import sagecell_config_default as sagecell_config
MAX_FILES = sagecell_config.flask_config['max_files']

app = Flask(__name__)

# is it safe to have global variables here?
db=None
fs=None
xreq=None
messages=[]
sysargs=None

def print_exception(f):
    """
    This decorator prints any exceptions that occur to the webbrowser.  This printing works even for uwsgi and nginx.
    """
    import traceback
    @wraps(f)
    def wrapper(*args, **kwds):
        try:
            return f(*args, **kwds)
        except:
            return "<pre>%s</pre>"%traceback.format_exc()
    return wrapper

def get_db(f):
    """
    This decorator gets the database and passes it into the function as the first argument.
    """
    import misc
    @wraps(f)
    def wrapper(*args, **kwds):
        global db
        global fs
        global sysargs
        if db is None or fs is None:
            db,fs=misc.select_db(sysargs)
        args = (db.new_context_copy(), fs.new_context_copy()) + args
        return f(*args, **kwds)
    return wrapper

def jsonify_with_callback(callback, *args, **kwargs):
    if callback is None:
        return jsonify(*args, **kwargs)
    else:
        return Response(callback + '(' + json.dumps(json.dumps(kwargs))+')',
                        mimetype="application/javascript")

import string
_VALID_QUERY_CHARS=set(string.letters+string.digits+'-')
@app.route("/")
@get_db
def root(db,fs):
    options={}
    if 'c' in request.values:
        options['code']=request.values['c']
    elif 'z' in request.values:
        import zlib, base64
        try:
            z=request.values['z'].encode('ascii')
            # we allow the user to strip off the = padding at the end
            # so that the URL doesn't have to have any escaping
            # here we add back the = padding if we need it
            z+='='*((4-(len(z)%4))%4)
            options['code']=zlib.decompress(base64.urlsafe_b64decode(z))
        except Exception as e:
            options['code']="# Error decompressing code: %s"%e
    elif 'q' in request.values and set(request.values['q']).issubset(_VALID_QUERY_CHARS):
        options['code']=db.get_input_message_by_shortened(request.values['q'])
    if 'code' in options:
        if isinstance(options['code'], unicode):
            options['code']=options['code'].encode('utf8')
        options['code']=quote(options['code'])
        options['autoeval'] = 'false' if 'autoeval' in request.args and request.args['autoeval'] == 'false' else 'true'
    return render_template('root.html', **options)

@app.route("/static/mathjax/fonts/HTML-CSS/TeX/<fontformat>/<filename>")
def webfont(fontformat, filename):
    response = send_file("static/mathjax/fonts/HTML-CSS/TeX/%s/%s" % (fontformat, filename))
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response

@app.route("/eval", methods=['POST'])
@get_db
def evaluate(db,fs):
    # If the request is a JSON message, such as from an interact update:
    if request.values.get("message") is not None:
        log('Received Request: %s'%(request.values['message'],))
        message=json.loads(request.values['message'])
        session_id=message['header']['session']
        db.new_input_message(message)
        # TODO: computation_id -> session_id
        rval = json.dumps({"computation_id": session_id})
    # Else if the request is the initial form submission at the beginning of a session:
    else:
        log('Received Request: %s' % (request.values,))
        session_id = str(uuid4())
        valid_request = True
        code = ""
        uploaded_files = request.files.getlist("file")
        files = []

        # Checks if too many files were uploaded.
        if len(request.files.getlist("file")) > MAX_FILES:
            code += "print('ERROR: Too many files uploaded. Maximum number of uploaded files is 10.')\n"
            valid_request = False

        if valid_request:
            for file in uploaded_files:
                if file:
                    filename = secure_filename(file.filename)
                    fs.create_file(file, filename=filename, session=session_id)
                    files.append(filename)
            code = json.loads(request.values.get("commands"))
            if not isinstance(code, basestring):
                log("code was not a string: %r"%(code,))
                return jsonify()

            sage_mode = "sage_mode" in request.values
            shortened = str(uuid4())
            message = {"parent_header": {},
                       "header": {"msg_id": request.values.get("msg_id"),
                                  "username": "",
                                  "session": session_id
                                  },
                       "msg_type": "execute_request",
                       "content": {"code": code,
                                   "silent": False,
                                   "files": files,
                                   "sage_mode": sage_mode,
                                   "user_variables": [],
                                   "user_expressions": {}
                                   },
                        "shortened": shortened
                       }
        log("Received Request: %s"%(message))
        db.new_input_message(message)
        import zlib, base64
        z=base64.urlsafe_b64encode(zlib.compress(code.encode('utf8')))
        zipurl = url_for('root', _external=True, z=z)
        queryurl = url_for('root', _external=True, q=shortened)
        rval = json.dumps({"zipurl": zipurl, "queryurl": queryurl,
                           "session_id": session_id})
    if (request.values.get("frame") is not None):
        return Response("<script>parent.postMessage(" + json.dumps(rval) +
                ",\"*\");</script>")
    else:
        r = Response(rval, mimetype="application/json")
        r.headers["Access-Control-Allow-Origin"] = "*"
        return r

from urllib import urlencode, urlopen
from json import loads

@app.route("/output_poll")
@print_exception
@get_db
def output_poll(db,fs):
    """
    Return the output of a computation id (passed in the request)

    If a computation id has output, then return to browser. If no
    output is entered, then return nothing.
    """
    callback=request.values['callback'] if 'callback' in request.values else None
    computation_id=request.values['computation_id']
    sequence=int(request.values.get('sequence',0))
    results = db.get_messages(computation_id,sequence=sequence)
    log("Retrieved messages: %s"%(str(results)[:2000],))
    if results is not None and len(results)>0:
        rval = jsonify_with_callback(callback, content=results)
    else:
        rval = jsonify_with_callback(callback, [])
    rval.headers["Access-Control-Allow-Origin"] = "*"
    return rval

@app.route("/output_long_poll")
@print_exception
@get_db
def output_long_poll(db,fs):
    """
    Implements long-polling to return answers.

    If a computation id has output, then return to browser. Otherwise,
    poll the database periodically to check to see if the computation id
    is done.  Return after a certain number of seconds whether or not
    it is done.

    This currently blocks (calls sleep), so is not very useful.
    """
    default_timeout=2 #seconds
    poll_interval=.1 #seconds
    end_time=float(request.values.get('timeout', default_timeout))+time()
    computation_id=request.values['computation_id']
    while time()<end_time:
        results = db.get_evaluated_cells(id=computation_id)
        if results is not None and len(results)>0:
            return jsonify({'output':results['output']})
        sleep(poll_interval)
    return jsonify([])

@app.route("/files/<session>/<filename>")
@get_db
def session_file(db,fs,session,filename):
    """Returns a file generated by a session from the filesystem."""
    # We can't use send_file because that will try to access the file
    # on the local filesystem (see the code to send_file).
    # So we have to do the work of send_file ourselves.
    #return send_file(fs.get_file(session,filename), attachment_filename=filename)

    mimetype=mimetypes.guess_type(filename)[0]
    if mimetype is None:
        mimetype = 'application/octet-stream'
    f=fs.get_file(session=session, filename=filename)
    if f is not None:
        return Response(f, content_type=mimetype)
    else:
        abort(404)

@app.route("/service", methods=['GET','POST'])
@get_db
def service(db,fs):
    code = request.values.get("code")
    if not isinstance(code, basestring):
        log("code was not a string: %r"%(code,))
        return ""
    log("Service called with code: %r"%code[:1000])

    default_timeout=30 #seconds
    poll_interval=.1 #seconds
    end_time=time()+default_timeout
    session = str(uuid4())
    message = {"parent_header": {},
               "header": {"msg_id": session,
                          "username": "",
                          "session": session,
                          },
                          "msg_type": "execute_request",
                          "content": {"code": code,
                                      "silent": False,
                                      "files": [],
                                      "sage_mode": True,
                                      "user_variables": [],
                                      "user_expressions": {},
                                      },
        }
    db.new_input_message(message)
    sequence = 0
    s = ""
    success=False
    done=False
    while not done and time()<end_time:
        sleep(poll_interval)
        results = db.get_messages(session, sequence=sequence)
        if results is not None and len(results)>0:
            for m in results:
                msg_type = m.get('msg_type','')
                content = m['content']
                if msg_type=="execute_reply":
                    if content['status']=="ok":
                        success=True
                    elif content['status']=="error":
                        success=False
                    done=True
                    break
                elif msg_type=="stream":
                    if content['name']=="stdout":
                        s += content['data']
                elif msg_type=="pyout":
                    s+=content['data'].get('text/plain','')
    log('Service returning: %r'%json.dumps([s,success]))
    return jsonify(output=s, success=success)

@app.route("/complete")
@get_db
def tabComplete(db,fs):
    """
    Perform tab completion using IPython
    """
    global xreq
    if xreq==None:
        xreq=IPReceiver(zmq.XREQ,db.get_ipython_port("xreq"))
    header={"msg_id":str(uuid4())}
    code=request.values["code"]
    xreq.socket.send_json({"header":header, "msg_type":"complete_request", "content": { \
                "text":"", "line":code, "block":code, "cursor_pos":request.values["pos"]}})
    return jsonify({"completions":xreq.getMessages(header,True)[0]["content"]["matches"]})

# This is disabled for now since it is also a security issue.
# We should be able to turn it on or off from the config file
# (so maybe a configurl=True/False parameter in the config file?)
#@app.route("/config")
@get_db
def config(db, fs):
    #TODO: reload this module to get the most current configuration
    import sagecell_config as c
    
    s=''
    s+='webserver=%r\n'%getattr(c, 'webserver', 'default')
    if hasattr(c, 'webserver') and hasattr(c, c.webserver+'_config'):
        webconfig = getattr(c, c.webserver+'_config')
        s+='webserver_config={\n'
        for k in [key for key in ('processes', 'listen', 'disable-logging') if key in webconfig]:
            s+='    %r: %r\n'%(k,webconfig[k])
        s+='}\n'

    s+='\ndevices=[\n'
    
    total_workers=0
    for device in db.get_devices():
        s+='    (%r: %r), #workers\n'%(str(device['account']), device['workers'])
        total_workers+=device['workers']
    s+=']\n'
    s+='# Total workers: %s\n'%total_workers

    s+='\nLOGGING=%s'%(c.LOGGING)
    s+='\n'

    try:
        git=''
        import subprocess
        # in python 2.7, we can just use the check_output command instead of Popen
        process = subprocess.Popen(['/usr/bin/env git rev-parse HEAD'], shell=True, stdout=subprocess.PIPE)
        git+='git_revision=%r\n'%process.communicate()[0].strip()
        process = subprocess.Popen(['git diff'], shell=True, stdout=subprocess.PIPE)
        # We assume that the string doesn't have any triple single quotes
        git+="git_diff=r'''\n%s\n'''"%process.communicate()[0]
        s+=git
    except E:
        # maybe we don't have git on the system
        pass

    return Response(s, content_type='text/plain')

from hashlib import sha1

_embedded_sagecell_cache = None
@app.route("/embedded_sagecell.js")
def embedded():
    global _embedded_sagecell_cache
    if _embedded_sagecell_cache is None:
        data = Response(render_template("embedded_sagecell.js"),
                        content_type='application/javascript')
        _embedded_sagecell_cache = (data, sha1(repr(data)).hexdigest())
    data,datahash = _embedded_sagecell_cache
    if request.environ.get('HTTP_IF_NONE_MATCH', None) == datahash:
        response = make_response('',304)
    else:
        response = make_response(data)
        response.headers['Content-Type'] = 'application/javascript; charset=utf-8'
        response.headers['Etag']=datahash
    return response

@app.route("/favicon.ico")
def favicon():
    return send_file("static/favicon.ico")

#purely for backwards compatibility
@app.route("/embedded_singlecell.js")
def embedded_old():
    return redirect(url_for('embedded'), 301)



if __name__ == "__main__":
    from argparse import ArgumentParser
    parser = ArgumentParser(description="The web server component of the notebook")
    parser.add_argument("--db", choices=["mongo", "sqlalchemy"], help="Database to use")
    parser.add_argument("-q", action="store_true", dest="quiet", help="Turn off most logging")

    (sysargs, args) = parser.parse_known_args()

    if sysargs.quiet:
        util.LOGGING=False

    # instead of parsing extra arguments, just import them from sagecell_config
    default_config = {'port': 8080}
    try:
        import sagecell_config
    except:
        import sagecell_config_default as sagecell_config
    config = getattr(sagecell_config, 'flaskweb_config', default_config)

    app.run(**config)
