import os
import datetime
import requests
import copy
import asyncio
import json
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine.base import Transaction
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.elements import Null
from models import Employee, Config, Clock
from types import SimpleNamespace

dir_name = os.path.join(os.path.dirname(os.path.realpath(__file__)), "rfid_gate.db")
engine = create_engine("sqlite:///"+dir_name)
Session = sessionmaker(bind=engine)
s = Session()

req_timeout = 10

def checkTokenTime(func):
    """
    decorator function that checks the token expiry before doing server calls
    """
    def wrapper(*args, **kwargs):
        config = s.query(Config).first()
        time_left = config.LastAuthDateUTC + (config.ExpiredToken * 1000) - int(datetime.datetime.now().timestamp() * 1000)
        if time_left < 10:  # give 10 seconds grace
            files = {
                'grant_type': (None, 'client_credentials'),
                'client_id': (None, 'client_id'),
                'client_secret': (None, 'A8E7EA2D-285A-4908-96D4-EB249F179DBD'),
                'scope': (None, 'pahapi pahapi.read roles'),
            }
            req = requests.post("https://planaheadgroup.com/connect/token", timeout=req_timeout, files=files)
            tokenset = json.loads(req.text, object_hook=lambda d: SimpleNamespace(**d))
            if req.status_code == 200:
                print('Successful Refresh Token Response:')
                config.AccessToken = tokenset.access_token
                config.ExpiredToken =  tokenset.expires_in
                config.LastAuthDateUTC = int(datetime.datetime.now().timestamp() * 1000)
                s.commit()
                # return config
        return func(*args, **kwargs)
    return wrapper

class DB():
    def getFilterObjects(model, query):
        arr = []
        rows = s.query(model).filter(text(query)).all()
        for row in rows:
            arr.append(copy.copy(row.__dict__))
        return arr

    def getAllObjects(model):
        arr = []
        rows = s.query(model).from_statement(text(f"SELECT * FROM {model.__table__.name}"))
        for row in rows:
            arr.append(copy.copy(row.__dict__))
        return arr

    def getFirst(model):
        row = s.query(model).first()
        # if a row exists, return it
        if row:
            return row
        # Create and return a new row for the model if it doesn't exist
        else:
            s.add(model())
            s.commit()
            return s.query(model).first()

    def updateOrg(self, OrganisationID, Name):
        config = s.query(Config).first()
        config.OrganisationID = OrganisationID
        config.Name = Name
        s.commit()
        return config

    def addClock(employee_rfid, direction):
        config = s.query(Config).first()
        employee = s.query(Employee).filter_by(RfidCode=employee_rfid).first()
        date = int(datetime.datetime.now().timestamp() * 1000)
        s.add(Clock(
            TransactionID = str(uuid.uuid4()),
            LogType = 3 if direction == 1 else 4,
            EmployeeID = employee.EmployeeID,
            EmployeeRFID = employee_rfid,
            SerialNumber = config.Serial,
            CreatedDateUTC = date,
            UpdatedDateUTC = date,
            DeletedDateUTC = 0,
            ServerDateUTC = 0
        ))
        employee.UpdatedDateUTC = date
        if direction == 1:
            employee.LogType = 3
            employee.LogDateUTC = date
        else:
            employee.LogType = 4
            employee.LogDateUTC = date
        s.commit()

    @checkTokenTime
    async def asyncAll():
        looping = True
        while looping:
            try:
                # sync device data up to server
                await asyncio.sleep(0.1)
                config = s.query(Config).first()
                temp_server_date = config.LastSyncUTC
                # sync server data down to device
                headers = {
                    'pah-tenant-id': config.OrganisationID,
                    'Authorization': 'Bearer ' + str(config.AccessToken)
                }
                req = requests.get(
                    'https://api.planaheadgroup.com/api/v1/employees',
                    timeout=req_timeout,
                    headers=headers,
                    params={'Everythingafter': str(config.LastSyncUTC)}
                )
                if req.status_code == 200:
                    data = req.json()
                    for employee in data['Employees']:
                        row = s.query(Employee).filter_by(EmployeeID=employee['EmployeeID']).first()
                        if row:
                            DB.updateModel(row, employee, Employee)
                        else:
                            s.add(Employee(
                                EmployeeID=employee['EmployeeID'],
                                Rfid=employee['Rfid'],
                                RfidCode=employee['RfidCode'],
                                Startdate=employee['Startdate'],
                                Termdate=employee['Termdate'],
                                Supervisor=employee['Supervisor'],
                                CreatedDateUTC=employee['CreatedDateUTC'],
                                UpdatedDateUTC=employee['UpdatedDateUTC'],
                                DeletedDateUTC=employee['DeletedDateUTC'],
                                ServerDateUTC=employee['ServerDateUTC'],
                            ))
                        if employee['ServerDateUTC'] > temp_server_date:
                            temp_server_date = employee['ServerDateUTC']
                        s.commit()
                        await asyncio.sleep(0.1)
                # Fetch all clocks from server
                headers = {
                    'pah-tenant-id': config.OrganisationID,
                    'Authorization': 'Bearer ' + str(config.AccessToken)
                }
                req = requests.get(
                    'https://api.planaheadgroup.com/api/v1/logs',
                    timeout=req_timeout,
                    headers=headers,
                    params={'Everythingafter': str(config.LastSyncUTC)}
                )
                
                if req.status_code == 200:
                    data = req.json()
                    for clock in data['Logs']:
                        row = s.query(Clock).filter_by(TransactionID=clock['TransactionID']).first()
                        if row:
                            DB.updateModel(row, clock, Clock)
                        else:
                            s.add(Clock(
                                TransactionID=clock['TransactionID'],
                                LogType=clock['LogType'],
                                EmployeeID=clock['People'][0]['PersonID'] if clock['People'] else '',
                                EmployeeRFID=clock['People'][0]['PersonRFID'] if clock['People'] else '',
                                SerialNumber='',
                                CreatedDateUTC=clock['CreatedDateUTC'],
                                UpdatedDateUTC=clock['UpdatedDateUTC'],
                                DeletedDateUTC=clock['DeletedDateUTC'],
                                ServerDateUTC=clock['ServerDateUTC'],
                            ))
                        if clock['ServerDateUTC'] > temp_server_date:
                            temp_server_date = clock['ServerDateUTC']
                        s.commit()
                        await asyncio.sleep(0.1)
                
                config.LastSyncUTC = temp_server_date
                s.commit()

                clocks = s.query(Clock).filter(Clock.ServerDateUTC == 0).all()
                date = int(datetime.datetime.now().timestamp() * 1000)
                headers = {
                    'pah-tenant-id': config.OrganisationID,
                    'Authorization': 'Bearer ' + str(config.AccessToken)
                }
                for clock in clocks:
                    temp_dict = DB.row2dict(clock)
                    req = requests.post(
                        'https://api.planaheadgroup.com/api/v1/clock',
                        headers=headers,
                        timeout=req_timeout,
                        json=[temp_dict]
                    )
                    
                    if req.status_code == 200:
                        clock.ServerDateUTC = date
                        clock.UpdatedDateUTC = date
                        s.commit()
                        print('upload clock success')
                    else:
                        print('upload clock failed')
                        print(req.text)
                
                s.commit()
                print('syncall finished')
            except Exception as e:
                print('offline: ' + str(e))
                pass
            await asyncio.sleep(60)
    
    def updateModel(row, new, model):
        columns = model.__table__.columns
        for column in columns:
            try:
                if str(column.type)[:4] == 'CHAR':
                    setattr(row, column.name, new[column.name])
                if str(column.type)[:7] == 'VARCHAR':
                    setattr(row, column.name, new[column.name])
                if str(column.type)[:5] == 'FLOAT':
                    setattr(row, column.name, new[column.name])
                if str(column.type)[:7] == 'INTEGER':
                    setattr(row, column.name, new[column.name])
                if str(column.type)[:8] == 'DATETIME':
                    setattr(row, column.name, new[column.name])
                if str(column.type)[:7] == 'BOOLEAN':
                    setattr(row, column.name, new[column.name])
            except:
                pass

    def row2dict(row):
        d = {}
        for column in row.__table__.columns:
            d[column.name] = str(getattr(row, column.name))

        return d