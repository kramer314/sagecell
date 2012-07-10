
class FileStore(object):
    """
    An object that abstracts a filesystem.  This is the base class for filestores.
    """
    def __init__(self):
        raise NotImplementedError

    def new_file(self, **kwargs):
        """
        Return a file handle for a new write-only file with the
        given properties. If the file already exists, it will 
        overwritten.

        :arg \*\*kwargs: the properties of the new file (one should be
            ``filename="[filename]"``)
        :returns: an open file handle for the new file
        :rtype: file handle
        """
        raise NotImplementedError

    def delete_files(self, **kwargs):
        """
        Delete every file in the filestore whose properties match
        the keyword arguments.

        :arg \*\*kwargs: all files whose MongoDB properties match these
             will be deleted
        """
        raise NotImplementedError

    def get_file(self, **kwargs):
        """
        Return a read-only file handle for a given file
        with the properties given by the keyword arguments.
        If the file does not exist, return ``None``.

        :arg \*\*kwargs: the properties of the desired file
        :returns: the opened file, or ``None`` if no file exists
        :rtype: file handle
        """
        raise NotImplementedError

    def create_file(self, file_handle, **kwargs):
        """
        Copy an existing file into the filestore.

        :arg file file_handle: a file handle open for reading
        :arg \*\*kwargs: labels for the new file (one shoud be
            ``filename="[filename]"``)
        """
        raise NotImplementedError

    def copy_file(self, file_handle, **kwargs):
        """Copy a file from the filestore into another file.

        :arg file file_handle: a file handle open for writing
        :arg \*\*kwargs: labels to identify the file to copy
        """
        raise NotImplementedError

    def create_secret(self, session):
        """
        Generate a new :mod:`hmac` object and associate it
        with the session. Used only with "untrusted" database
        adaptors. (See :ref:`trusted`.)

        :arg str session: the ID of the new session
        """
        raise NotImplementedError

    def new_context(self):
        """
        Reconnect to the filestore. This function should be
        called before the first filestore access in each new process.
        """

    def new_context_copy(self):
        """
        Create a copy of this object for use in a single thread.

        :returns: a new filestore object
        :rtype: FileStore
        """
