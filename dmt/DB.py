#!/usr/bin/python3

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
import sqlalchemy
from sqlalchemy.orm import relationship, backref
import sqlalchemy.ext.declarative

Base = sqlalchemy.ext.declarative.declarative_base()

class MirrorCheckResult(Base):
    __tablename__          = 'mirrorcheckresult'
    id                     = Column(Integer, primary_key=True)

    site                   = Column(String, nullable=False, unique=True)
    last_test              = Column(DateTime, nullable=False)
    last_noerror           = Column(DateTime)

    trace_master_timestamp = Column(DateTime)
    error                  = Column(String)
    warning                = Column(String)

    tracefilelist = relationship("TraceFileList", uselist=False, back_populates="mirrorcheckresult", cascade="all, delete-orphan", passive_deletes=True)

class GlobalInfo(Base):
    __tablename__          = 'globalinfo'
    id                     = Column(Integer, primary_key=True)
    last_test              = Column(DateTime, nullable=False)

class TraceFileList(Base):
    """A list of tracefiles found in project/traces for each mirror"""
    __tablename__          = 'tracefilelist'
    id                     = Column(Integer, primary_key=True)
    mirrorcheckresult_id   = Column(Integer, ForeignKey('mirrorcheckresult.id', ondelete='CASCADE'), nullable=False, unique=True)
    mirrorcheckresult      = relationship("MirrorCheckResult", back_populates="tracefilelist")

    last_test              = Column(DateTime, nullable=False)
    traces                 = Column(String, nullable=False)
    traces_last_change     = Column(DateTime, nullable=False)

class MirrorDB():
    def __init__(self, dburl):
        self.engine = sqlalchemy.create_engine(dburl)
        Base.metadata.bind = self.engine
        self.sessionMaker = sqlalchemy.orm.sessionmaker(bind=self.engine)

    def session(self):
        return self.sessionMaker()

    @staticmethod
    def update_or_create(session, model, updates, **kwargs):
        r = session.query(model).filter_by(**kwargs)
        cnt = r.update(updates)
        if cnt == 0:
            attributes = dict((k, v) for k, v in kwargs.items())
            attributes.update(updates)
            instance = model(**attributes)
            session.add(instance)
