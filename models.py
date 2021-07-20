from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, CHAR, Float, ForeignKey, func, TypeDecorator, DateTime, Boolean, create_engine, MetaData, Sequence
from sqlalchemy.orm import relationship
import os
import uuid
import datetime
import string
import random


Base = declarative_base()


def guid_generator(size=16, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class Config(Base):
    __tablename__ = 'config'
    ConfigID = Column(CHAR(32), primary_key=True, default=str(uuid.uuid4()))
    Name = Column(String(255), nullable=False, default='')
    OrganisationID = Column(CHAR(32), nullable=False, default='')
    System = Column(String(255), nullable=False, default='')
    SystemVersion = Column(String(255), nullable=False, default='')
    Serial = Column(String(255), nullable=False, default='')
    AppVersion = Column(String(255), nullable=False, default='')
    UserID = Column(CHAR(32), nullable=False, default='')
    UserName = Column(String(255), nullable=False, default='')
    UserEmail = Column(String(255), nullable=False, default='')
    PinCode = Column(Integer, nullable=False, default=0)
    ReferenceUnitA = Column(Integer, nullable=False, default=1)
    ReferenceUnitB = Column(Integer, nullable=False, default=1)
    OffsetA = Column(Integer, nullable=False, default=1)
    OffsetB = Column(Integer, nullable=False, default=1)
    RfidEnabled = Column(Boolean, nullable=False, default=True)
    ScaleAEnabled = Column(Boolean, nullable=False, default=True)
    ScaleBEnabled = Column(Boolean, nullable=False, default=False)
    CalibrateOnStartup = Column(Boolean, nullable=False, default=False)
    VarietyEnabled = Column(Boolean, nullable=False, default=False)
    AssetEnabled = Column(Boolean, nullable=False, default=False)
    GrantType = Column(String(255), nullable=False, default='urn:ietf:params:oauth:grant-type:device_code')
    ClientID = Column(String(255), nullable=False, default='pah_iot')
    Issuer = Column(String(255), nullable=False, default='https://planaheadgroup.com')
    Scope = Column(String(255), nullable=False, default='openid pahapi offline_access')
    AccessToken = Column(String, nullable=False, default='')
    RefreshToken = Column(String, nullable=False, default='')
    ExpiredToken = Column(Integer, nullable=False, default=0)
    LastAuthDateUTC = Column(Integer, nullable=False, default=0)
    LastSyncUTC = Column(Integer, nullable=False, default=0)
    CreatedDateUTC = Column(Integer, default=int(datetime.datetime.now().timestamp() * 1000))
    UpdatedDateUTC = Column(Integer, default=int(datetime.datetime.now().timestamp() * 1000), onupdate=int(datetime.datetime.now().timestamp() * 1000))
    DeletedDateUTC = Column(Integer, nullable=False, default=0)
    ServerDateUTC = Column(Integer, nullable=False, default=0)


class Employee(Base):
    __tablename__ = 'employee'
    EmployeeID = Column(CHAR(32), primary_key=True, default=str(uuid.uuid4()))
    Rfid = Column(String(10), nullable=True, default='')
    RfidCode = Column(String(30), nullable=True, default='')
    Startdate = Column(String(30), nullable=True)
    Termdate = Column(String(30), nullable=True)
    Supervisor = Column(Integer, nullable=False, default=False)
    LogType = Column(Integer, nullable=False, default=0)
    LogDateUTC = Column(Integer, nullable=False, default=0)
    CreatedDateUTC = Column(Integer, default=int(datetime.datetime.now().timestamp() * 1000))
    UpdatedDateUTC = Column(Integer, default=int(datetime.datetime.now().timestamp() * 1000))
    DeletedDateUTC = Column(Integer, nullable=False, default=0)
    ServerDateUTC = Column(Integer, nullable=False, default=0)


class Clock(Base):
    __tablename__ = 'Clock'
    TransactionID = Column(CHAR(32), primary_key=True, default=str(uuid.uuid4()))
    LogType = Column(Integer, nullable=False)
    EmployeeID = Column(CHAR(32), nullable=False)
    EmployeeRFID = Column(String(10), nullable=True, default='')
    SerialNumber = Column(String(255), nullable=False, default='')
    CreatedDateUTC = Column(Integer, default=int(datetime.datetime.now().timestamp() * 1000), onupdate=int(datetime.datetime.now().timestamp() * 1000))
    UpdatedDateUTC = Column(Integer, default=int(datetime.datetime.now().timestamp() * 1000), onupdate=int(datetime.datetime.now().timestamp() * 1000))
    DeletedDateUTC = Column(Integer, nullable=False, default=0)
    ServerDateUTC = Column(Integer, nullable=False, default=0)


dir_name = os.path.join(os.path.dirname(os.path.realpath(__file__)), "rfid_gate.db")
engine = create_engine("sqlite:///"+dir_name)
# Create tables if they don't exist
Config.__table__.create(bind=engine, checkfirst=True)
Employee.__table__.create(bind=engine, checkfirst=True)
Clock.__table__.create(bind=engine, checkfirst=True)