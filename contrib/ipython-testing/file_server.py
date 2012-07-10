
import tornado
import tornado.web

import tornado.gen

import misc
import sys

import requests

import multiprocessing

import mimetypes

config = misc.Config()

fs = misc.init_fs(config)

def add_files(files, session):
    retval = {"session": session}
    failures = []
    for file_list in files.values():
        for f in file_list:
            fs.new_context()
            try:
                with fs.new_file(session=session, filename=f.filename) as fs_entry:
                    fs_entry.write(f.body)
            except:
                failures.append(f.filename)
    retval["failures"] = failures
    return retval

_workers = multiprocessing.Pool(20)

class GetFile(tornado.web.RequestHandler):
    def get(self, session, filename):
        args = self.request.arguments

        mimetype = mimetypes.guess_type(filename)[0]
        if mimetype is None:
            mimetype = "application/octet-stream"

        fs = self.application.fs

        f = fs.get_file(session = session, filename = filename)

        if f is not None:
            self.write(f.read())
            f.close()
            self.set_header("Content-Type", mimetype)
            self.finish()
        else:
            self.send_error(status_code = 404)

class SubmitFile(tornado.web.RequestHandler):
    @tornado.web.asynchronous
    def post(self):
        args = self.request.arguments

        session = args.get("session")
        if session is not None:
            session = "".join(session)

        auth_key = args.get("key")
        if auth_key is not None:
            auth_key = "".join(auth_key)

        server_auth_key = self.application.fs_config.get("key")

        files = self.request.files
        num_files = len(files.values())
        max_files = self.application.fs_config.get("max_files")

        if auth_key == server_auth_key and num_files <= max_files and session is not None:
            print "Started uploading files for reqeust %s"%(session)
            req = _workers.apply_async(add_files, (files, session,),
                                       callback= self.async_callback(self.on_complete))
        else:
            self.send_error(status_code = 400)

    def on_complete(self, response):
        print "Done uploading files for request %s"%(response.get("session"))
        self.write(response)
        try:
            self.finish()
        except IOError: # If the request is already closed
            pass

class SageCellFileServer(tornado.web.Application):
    def __init__(self):
        handlers = [(r"/submit", SubmitFile),
                    (r"/files/(?P<session>[^\/]+)/(?P<filename>[^\/]+)", GetFile)]

        self.config = misc.Config()

        self.fs = misc.init_fs(self.config)

        self.fs_config = self.config.get_config("fs_config")

        super(SageCellFileServer, self).__init__(handlers)

        self.listen(self.config.get_config("fs_port"))

if __name__ == "__main__":
    application = SageCellFileServer()
    tornado.ioloop.IOLoop.instance().start()
