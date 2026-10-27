from datetime import datetime
from pydantic import BaseModel, Field

from potehinsonnet.net_models.panel_ui import PanelPageInfo

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
    # Страницы плагина в веб-панели
    panel_pages: list[PanelPageInfo] = Field(default_factory=list)

class ServiceRegistrationRequest(Service):
    time: datetime = Field(default_factory=datetime.now)
    status: str

class ServiceRegistrationResponse(Service):
    time: datetime = Field(default_factory=datetime.now)
    success: bool = True
