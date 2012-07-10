# location of a sage executable
sage = "sage"

db = "sqlalchemy"
db_config = {}

fs = "sqlalchemy"
fs_config = {"key": "this-should-be-a-string", # Used to help exclude unwanted requests
             "workers": 20, # Number of filestorage worker processes
             "max_files": 10, # Max number of files allowed in a POST request
             }

if db == "sqlalchemy":
    db_config["uri"] = "sqlite:///sqlite_db.db"

if fs == "sqlalchemy":
    fs_config["uri"] = "sqlite:///sqlite_fs.db"
    # fs_config["uri"] = "sqlite://" # For an in-memory database

max_kernel_timeout = 60

computers = []

_default_config = {"host": "localhost",
                  "username": None,
                  "python": sage + " -python",
# The keys to resource_limits can be any available resources
# for the resource module. See http://docs.python.org/library/resource.html
# for more information (section 35.13.1)

# Note: RLIMIT_NPROC doesn't really work
# Note: RLIMIT_AS is more of a suggestion than a hard limit in Mac OS X
# Note: All other resource limits seem to be working, but besides RLIMIT_CPU and
# RLIMIT_AS they don't actually kill off offending processes
                  "resource_limits": {"RLIMIT_CPU": 30, # CPU time in seconds
                                      "RLIMIT_AS": 512*(2**20), #Maximum address space in bytes; this sets 512 MB
                                     },
# The log file will be in the home directory of the untrusted account
                  "log_file": "sagecell.log",
                  "max_kernels": 10,
# These set paramaters for a heartbeat channel checking whether a given kernel is alive.
# Setting first_beat lower than 1.0 may cause javascript errors.
                  "beat_interval": 0.5,
                  "first_beat": 1.0}

for i in xrange(1):
    computers.append(_default_config)
