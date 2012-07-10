import fs

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.types import Binary
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from StringIO import StringIO

class FileStore(fs.FileStore):
    """
    A filestore in a SQLAlchemy database.
    
    :arg str fs_file: the SQLAlchemy URI for a database file
    """
    def __init__(self, fs_file):
        engine = create_engine(fs_file)
        self.SQLSession = scoped_session(sessionmaker(bind=engine))
        Base.metadata.create_all(engine)
        self.new_context()

    def new_file(self, session, filename, **kwargs):
        """
        See :meth:`FileStore.new_file`
        """
        self.delete_files(session, filename)
        print "FS Creating %s/%s"%(session, filename)
        return DBFileWriter(self, session, filename)

    def delete_files(self, session=None, filename=None, **kwargs):
        """
        See :meth:`FileStore.new_file`
        """
        q = self.dbsession.query(StoredFile)
        if session is not None:
            q = q.filter_by(session=session)
        if filename is not None:
            q = q.filter_by(filename=filename)
        q.delete()
        self.dbsession.commit()

    def get_file(self, session, filename, **kwargs):
        """
        See :meth:`FileStore.get_file`
        """
        f = None
        db_entry =  self.dbsession.query(StoredFile.contents) \
            .filter_by(session=session, filename=filename).first()
        try:
            f = StringIO(db_entry.contents)
        except:
            pass
        return f

    def create_file(self, file_handle, session, filename, **kwargs):
        """
        See :meth:`FileStore.create_file`
        """
        f = StoredFile(session=session, filename=filename)
        if type(file_handle) is DBFileWriter:
            contents = file_handle.getvalue()
        else:
            contents = file_handle.read()
        f.contents = contents
        self.dbsession.add(f)
        self.dbsession.commit()

    def copy_file(self, file_handle, session, filename, **kwargs):
        """
        See :meth:`FileStore.copy_file`
        """
        self.dbsession.add(StoredFile(session=session,
                filename=filename, contents=file_handle.read()))
        self.dbsession.commit()

    def new_context(self):
        """
        See :meth:`FileStore.new_context`
        """
        self.dbsession = self.SQLSession()

    def new_context_copy(self):
        """
        See :meth:`FileStore.new_context_copy`
        """
        new = type(self)()
        new.SQLSession = self.SQLSession
        new.new_context()
        return new

Base = declarative_base()
    
class StoredFile(Base):
    """A file stored in the database"""
    __tablename__ = 'filestore'
    n = Column(Integer, primary_key=True)
    session = Column(String)
    filename = Column(String)
    contents = Column(Binary)

class DBFileWriter(StringIO, object):
    """
    A file-like object that writes its contents to the database when it is
    closed.
    
    :arg FileStoreSQLAlchemy filestore: the filestore object to write to
    :arg str session: the ID of the session that is the source of this file
    :arg str filename: the name of the file
    """
    def __init__(self, filestore, session, filename):
        self.filestore = filestore
        self.session = session
        self.filename = filename
        super(type(self), self).__init__()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()
    def close(self):
        self.filestore.create_file(self, self.session, self.filename)
        super(type(self), self).close()
