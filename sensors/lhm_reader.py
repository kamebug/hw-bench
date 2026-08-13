"""
Wrapper para leitura de sensores de hardware (clock, temperatura, power draw).

No Windows, usa LibreHardwareMonitor via pythonnet (precisa do LHM rodando
como serviço ou da DLL referenciada localmente).

TODO: apontar LHM_DLL_PATH para o caminho real do
LibreHardwareMonitorLib.dll após baixar o LibreHardwareMonitor.
"""

import platform
import time
from dataclasses import dataclass, asdict
from typing import Optional


LHM_DLL_PATH = r"C:\Tools\LibreHardwareMonitor\LibreHardwareMonitorLib.dll"


@dataclass
class SensorSnapshot:
    timestamp: float
    cpu_clock_mhz: Optional[float] = None
    cpu_temp_c: Optional[float] = None
    cpu_power_w: Optional[float] = None
    gpu_clock_mhz: Optional[float] = None
    gpu_temp_c: Optional[float] = None

    def to_dict(self):
        return asdict(self)


class SensorReader:
    """
    Interface única de leitura de sensores. Detecta a plataforma e usa
    o backend disponível. Se nenhum backend estiver configurado, retorna
    snapshots vazios (permite rodar o benchmark sem sensores).
    """

    def __init__(self):
        self.backend = None
        if platform.system() == "Windows":
            self.backend = self._init_windows_backend()
        else:
            self.backend = self._init_linux_backend()

    def _init_windows_backend(self):
        try:
            import clr  # pythonnet
            clr.AddReference(LHM_DLL_PATH)
            from LibreHardwareMonitor import Hardware

            computer = Hardware.Computer()
            computer.IsCpuEnabled = True
            computer.IsGpuEnabled = True
            computer.Open()
            return computer
        except Exception as e:
            print(f"[sensors] LibreHardwareMonitor indisponível: {e}")
            print("[sensors] Rodando sem leitura de sensores.")
            return None

    def _init_linux_backend(self):
        # TODO: implementar leitura via /sys/class/thermal e psutil (freq)
        # ou via `sensors -j` (lm-sensors) parseando JSON.
        return None

    def read(self) -> SensorSnapshot:
        snap = SensorSnapshot(timestamp=time.time())

        if self.backend is None:
            return snap

        try:
            for hw in self.backend.Hardware:
                hw.Update()
                for sensor in hw.Sensors:
                    name = str(sensor.Name)
                    stype = str(sensor.SensorType)
                    value = sensor.Value

                    if stype == "Clock" and "CPU" in str(hw.HardwareType):
                        snap.cpu_clock_mhz = value
                    elif stype == "Temperature" and "CPU" in str(hw.HardwareType):
                        snap.cpu_temp_c = value
                    elif stype == "Power" and "CPU" in str(hw.HardwareType):
                        snap.cpu_power_w = value
                    elif stype == "Clock" and "Gpu" in str(hw.HardwareType):
                        snap.gpu_clock_mhz = value
                    elif stype == "Temperature" and "Gpu" in str(hw.HardwareType):
                        snap.gpu_temp_c = value
        except Exception as e:
            print(f"[sensors] Erro ao ler sensores: {e}")

        return snap


if __name__ == "__main__":
    reader = SensorReader()
    for _ in range(5):
        print(reader.read())
        time.sleep(1)
