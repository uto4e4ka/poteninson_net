from datetime import datetime
from pydantic import BaseModel

class ServiceHealthMessage(BaseModel):
    type: str = "plugin"
    name: str
    status: str
    time: datetime = datetime.now()

class Service(BaseModel):
    type: str = "plugin"
    name: str
    label:str
    description:str =""
    author:str
    version:str
    icon: str =""
    site:str =""

class ServiceRegistrationRequest(Service):
    time: datetime = datetime.now()
    status: str

class ServiceRegistrationResponse(Service):
    time: datetime = datetime.now()
    success: bool = True
