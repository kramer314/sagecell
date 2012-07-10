import uuid
import os
import signal
import sys
import resource
import tempfile
import shutil
from IPython.zmq.ipkernel import IPKernelApp
from IPython.config.loader import Config
from multiprocessing import Process, Pipe
import logging

class ForkingKernelManager(object):
    def __init__(self, filename, update_function=None):
        self.kernels = {}
        self.filename = filename
        self.update_function = update_function

    def fork_kernel(self, config, pipe, resource_limits, logfile):
        os.setpgrp()
        logging.basicConfig(filename=self.filename,format=str(uuid.uuid4()).split('-')[0]+': %(asctime)s %(message)s',level=logging.DEBUG)
        ka = IPKernelApp.instance(config=config)
        ka.initialize([])
        if self.update_function is not None:
            self.update_function(ka)
        for r, limit in resource_limits.iteritems():
            resource.setrlimit(getattr(resource, r), (limit, limit))
        pipe.send({"ip": ka.ip,
                   "key": ka.session.key,
                   "shell_port": ka.shell_port,
                   "stdin_port": ka.stdin_port,
                   "hb_port": ka.hb_port,
                   "iopub_port": ka.iopub_port})
        pipe.close()
        ka.start()

    def start_kernel(self, kernel_id=None, config=None, resource_limits=None, logfile = None):
        current_dir = os.getcwd()
        tmp_dir = tempfile.mkdtemp()
        os.chdir(tmp_dir)

        if kernel_id is None:
            kernel_id = str(uuid.uuid4())
        if config is None:
            config = Config()
        if resource_limits is None:
            resource_limits = {}
        p, q = Pipe()
        proc = Process(target=self.fork_kernel, args=(config, q, resource_limits, logfile))
        proc.start()
        connection = p.recv()
        p.close()

        os.chdir(current_dir)

        self.kernels[kernel_id] = {"process": proc,
                                   "connection": connection,
                                   "tmp_dir": tmp_dir,
                                   }
        return {"kernel_id": kernel_id, "connection": connection}

    def kill_kernel(self, kernel_id):
        """Kill a running kernel."""
        success = False

        if kernel_id in self.kernels:
            proc = self.kernels[kernel_id]["process"]
            try:
                success = True
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.join()
            except Exception as e:
                # On Unix, we may get an ESRCH error if the process has already
                # terminated. Ignore it.
                from errno import ESRCH
                if e.errno !=  ESRCH:
                    success = False
        shutil.rmtree(self.kernels[kernel_id]["tmp_dir"])
        if success:
            del self.kernels[kernel_id]
        return success

    def interrupt_kernel(self, kernel_id):
        """Interrupt a running kernel."""
        success = False

        if kernel_id in self.kernels:
            try:
                os.kill(self.kernels[kernel_id]["process"].pid, signal.SIGINT)
                success = True
            except:
                pass

        return success

    def restart_kernel(self, kernel_id):
        connection = self.kernels[kernel_id]["connection"]
        self.kill_kernel(kernel_id)
        return self.start_kernel(kernel_id, Config({"IPKernelApp": connection}))

if __name__ == "__main__":
    def f(a,b,c,d):
        return 1
    a = ForkingKernelManager("/dev/null", f)
    x = a.start_kernel()
    y = a.start_kernel()
    import time
    time.sleep(5)
    a.kill_kernel(x["kernel_id"])
    a.kill_kernel(y["kernel_id"])
