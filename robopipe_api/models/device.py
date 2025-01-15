from pydantic import BaseModel


class Device(BaseModel):
    dev: str
    circuit: str
