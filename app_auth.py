# ==> GUI FILE
import os
import json
import uuid
import asyncio
import platform
import datetime
import requests

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Config, Employee
from db_utils import DB

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
            Issuer.updateToken(Issuer)
        return func(*args, **kwargs)
    return wrapper

class Issuer():
    def __init__(self):
        pass

    async def run(self):
        s = Session()
        config = Issuer.GetConfig(self)
        if not Issuer.isAuthorized(self):
            print('not authorized')
            issuer = Issuer.discover(config.Issuer)
            done = False
            while not done:
                files = {
                    'grant_type': (None, 'client_credentials'),
                    'client_id': (None, 'client_id'),
                    'client_secret': (None, 'A8E7EA2D-285A-4908-96D4-EB249F179DBD'),
                    'scope': (None, 'pahapi pahapi.read roles'),
                }
                req = requests.post('https://planaheadgroup.com/connect/token', timeout=req_timeout, files=files)
                tokenset = json.loads(req.text, object_hook=lambda d: SimpleNamespace(**d))
                if req.status_code == 400:
                    if tokenset.error == 'authorization_pending':
                        print('End-User authorization Pending ...')
                        await asyncio.sleep(5)
                    elif tokenset.error == 'access_denied':
                        print('End-User cancelled the flow')
                        done = True
                        break
                    elif tokenset.error == 'expired_token':
                        print('The flow has expired')
                        done = True
                        break

                if req.status_code == 200:
                    print('Successful Token Response:')
                    Issuer.SetTokens(self, tokenset.access_token, tokenset.expires_in)

                    if config.OrganisationID == '':
                        Issuer.GetOrganisations(self)
                    done = True
        else:
            if config.OrganisationID == '':
                Issuer.GetOrganisations(self)

    def discover(Issuer):
        request = requests.get(Issuer + '/.well-known/openid-configuration', timeout=req_timeout)
        return json.loads(request.text, object_hook=lambda d: SimpleNamespace(**d))

    def updateToken(self):
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
            Issuer.SetTokens(self, tokenset.access_token, tokenset.expires_in)

    @checkTokenTime
    def GetOrganisations(self):
        print('GetOrganisations')
        config = Issuer.GetConfig(self)
        headers = {'Authorization': 'Bearer ' + str(config.AccessToken)}
        req = requests.get('https://api.planaheadgroup.com/organisations', timeout=req_timeout, headers=headers)
        if req.status_code == 200:
            # save tenantid (organisation id)
            organisations = json.loads(req.text)['Connections']
            if len(organisations) == 1:
                Issuer.SetOrganisation(self, organisations[0]['tenantId'], organisations[0]['name'])
        elif req.status_code == 401:
            print('req failed')
            Issuer.updateToken(self)
            Issuer.GetOrganisations(self)

    def isAuthorized(self):
        config = Issuer.GetConfig(self)
        if config.LastAuthDateUTC != 0:
            return True
        else:
            return False

    def GetConfig(self):
        s = Session()
        config = s.query(Config).first()
        if not config:
            s.add(Config(
                ConfigID=str(uuid.uuid4()),
                OrganisationID='07a4c9b2-e6f9-497f-8140-2d767a54488f',
                System = platform.system(),
                SystemVersion = platform.release(),
                Serial = Issuer.getSerial()
            ))
            s.commit()
            config = s.query(Config).first()
        return config

    def getSerial():
        # Extract serial from cpuinfo file
        cpuserial = "0000000000000000"
        try:
            f = open('/proc/cpuinfo','r')
            for line in f:
                if line[0:6]=='Serial':
                    cpuserial = line[10:26]
            f.close()
        except:
            cpuserial = "ERROR000000000"
        
        return cpuserial

    def SetTokens(self, AccessToken, ExpiredToken):
        config = s.query(Config).first()
        config.AccessToken = AccessToken
        config.ExpiredToken = ExpiredToken
        config.LastAuthDateUTC = int(datetime.datetime.now().timestamp() * 1000)
        s.commit()
        return config

    def SetOrganisation(self, OrganisationID, Name):
        config = s.query(Config).first()
        config.OrganisationID = OrganisationID
        config.Name = Name
        s.commit()
        return config
