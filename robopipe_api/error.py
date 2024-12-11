class CameraNotFoundException(Exception):
    pass


class CameraShutDownException(Exception):
    pass


class SensorNotFoundException(Exception):
    pass


class ModbusSlaveError(Exception):
    pass


class ENoCacheRegister(ModbusSlaveError):
    pass


class DeviceNotFound(Exception):
    pass
