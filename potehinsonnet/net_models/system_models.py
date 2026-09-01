from datetime import datetime


def service_info_model(
        name:str,
        status:str,
        time:datetime = datetime.now(),
type:str = "plugin"
):
    return {"type":type,
            "name":name,
            "status":status,
            "time":time}
def test():
    return None