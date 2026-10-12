from datetime import datetime
from pydantic import BaseModel, Field

class ServiceHealthMessage(BaseModel):
    type: str = "plugin"
    name: str
    status: str
    time: datetime = Field(default_factory=datetime.now)

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
    time: datetime = Field(default_factory=datetime.now)
    status: str

class ServiceRegistrationResponse(Service):
    time: datetime = Field(default_factory=datetime.now)
    success: bool = True
