import depthai as dai

import dataclasses


@dataclasses.dataclass
class CameraStats:
    @dataclasses.dataclass
    class ChipTemperature:
        average: float
        css: float
        dss: float
        mss: float
        upa: float

        @classmethod
        def from_chip_temperature(cls, chip_temperature: dai.ChipTemperature):
            return cls(
                chip_temperature.average,
                chip_temperature.css,
                chip_temperature.dss,
                chip_temperature.mss,
                chip_temperature.upa,
            )

    @dataclasses.dataclass
    class MemoryInfo:
        total: int
        used: int
        remaining: int

        @classmethod
        def from_memory_info(cls, memory_info: dai.MemoryInfo):
            return cls(memory_info.total, memory_info.used, memory_info.remaining)

    chip_temperature: ChipTemperature
    cmx_memory_usage: MemoryInfo
    ddr_memory_usage: MemoryInfo

    @classmethod
    def from_device(cls, device: dai.Device):
        return cls(
            cls.ChipTemperature.from_chip_temperature(device.getChipTemperature()),
            cls.MemoryInfo.from_memory_info(device.getCmxMemoryUsage()),
            cls.MemoryInfo.from_memory_info(device.getDdrMemoryUsage()),
        )
