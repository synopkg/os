#!/usr/bin/python3

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
import sqlalchemy
from sqlalchemy.orm import relationship, backref
import sqlalchemy.ext.declarative

Base = sqlalchemy.ext.declarative.declarative_base()

class Origin(Base):
    """Origin of site information, i.e. the place from which we learned that
       a site exists.  E.g. "Mirrors.masterlist"
       """
    __tablename__           = 'origin'
    id                      = Column(Integer, primary_key=True)

    label                   = Column(String, nullable=False, unique=True)

class Site(Base):
    """Site offering the debian archive.
    """
    __tablename__           = 'site'
    id                      = Column(Integer, primary_key=True)

    origin_id               = Column(Integer, ForeignKey('origin.id', ondelete='CASCADE'), nullable=False)
    origin                  = relationship("Origin", backref=backref("sites", passive_deletes=True))

    name                    = Column(String, nullable=False, unique=True)
    http_path               = Column(String, nullable=False)
    http_override_host      = Column(String)
    http_override_port      = Column(Integer)

class Checkrun(Base):
    """Instance of a mirror check run
    """
    __tablename__           = 'checkrun'
    id                      = Column(Integer, primary_key=True)

    timestamp               = Column(DateTime(timezone=True))


class Mastertrace(Base):
    """Age of the master tracefile
    """
    __tablename__           = 'mastertrace'
    __plural__              = __tablename__ + 's'
    id                      = Column(Integer, primary_key=True)

    site_id                 = Column(Integer, ForeignKey("site.id", ondelete='CASCADE'), nullable=False)
    checkrun_id             = Column(Integer, ForeignKey("checkrun.id", ondelete='CASCADE'), nullable=False)
    site                    = relationship("Site", backref=backref(__plural__, passive_deletes=True))
    checkrun                = relationship("Checkrun", backref=backref(__plural__, passive_deletes=True))

    trace_timestamp         = Column(DateTime(timezone=True))
    error                   = Column(String)


class Sitetrace(Base):
    """site tracefile
    """
    __tablename__           = 'sitetrace'
    __plural__              = __tablename__ + 's'
    id                      = Column(Integer, primary_key=True)

    site_id                 = Column(Integer, ForeignKey("site.id", ondelete='CASCADE'), nullable=False)
    checkrun_id             = Column(Integer, ForeignKey("checkrun.id", ondelete='CASCADE'), nullable=False)
    site                    = relationship("Site", backref=backref(__plural__, passive_deletes=True))
    checkrun                = relationship("Checkrun", backref=backref(__plural__, passive_deletes=True))

    full                    = Column(String)
    trace_timestamp         = Column(DateTime(timezone=True))
    error                   = Column(String)


class Traceset(Base):
    """List of tracefiles found in project/traces
    """
    __tablename__           = 'traceset'
    __plural__              = __tablename__ + 's'
    id                      = Column(Integer, primary_key=True)

    site_id                 = Column(Integer, ForeignKey("site.id", ondelete='CASCADE'), nullable=False)
    checkrun_id             = Column(Integer, ForeignKey("checkrun.id", ondelete='CASCADE'), nullable=False)
    site                    = relationship("Site", backref=backref(__plural__, passive_deletes=True))
    checkrun                = relationship("Checkrun", backref=backref(__plural__, passive_deletes=True))

    traceset                = Column(String)
    error                   = Column(String)

class MirrorDB():
    DBURL='postgresql:///mirror-status'
    def __init__(self, dburl=DBURL):
        self.engine = sqlalchemy.create_engine(dburl)
        Base.metadata.bind = self.engine
        self.sessionMaker = sqlalchemy.orm.sessionmaker(bind=self.engine)

    def session(self):
        return self.sessionMaker()

def update_or_create(session, model, updates, **kwargs):
    r = session.query(model).filter_by(**kwargs)
    if len(updates) == 0:
        need_insert = r.first() is None
    else:
        need_insert = r.update(updates) == 0
    if need_insert:
        attributes = dict((k, v) for k, v in kwargs.items())
        attributes.update(updates)
        instance = model(**attributes)
        session.add(instance)
