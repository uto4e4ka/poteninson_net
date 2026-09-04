from datetime import datetime
from pydantic import BaseModel

class ServiceHealthMessage(BaseModel):
    type: str = "plugin"
    name: str
    status: str
    time: datetime = datetime.now()

