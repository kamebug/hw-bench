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
        import os
        if not os.path.exists(LHM_DLL_PATH):
            print(f"[sensors] LibreHardwareMonitorLib.dll não encontrada em: {LHM_DLL_PATH}")
            print("[sensors] Sensores de clock/temperatura/power não estarão disponíveis.")
            print("[sensors] Para habilitar: baixe o LibreHardwareMonitor em")
            print("[sensors]   https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases")
            print("[sensors] instale o PawnIO (oferecido ao abrir o .exe como administrador),")
            print("[sensors] e rode este script também em um terminal como administrador.")
            print("[sensors] Detalhes completos: ver README.md deste repositório.")
            return None
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
            print("[sensors] Rodando sem leitura de sensores. Ver README.md para instruções de instalação.")
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
                hw_type = str(hw.HardwareType).lower()
                for sensor in hw.Sensors:
                    stype = str(sensor.SensorType)
                    value = sensor.Value

                    if value is None:
                        continue

                    is_cpu = "cpu" in hw_type
                    is_gpu = "gpu" in hw_type

                    # Para clock e power, pega o primeiro sensor válido
                    # (evita sobrescrever com sensores de núcleos individuais
                    # quando já existe um valor "Core Average"/pacote)
                    if stype == "Clock" and is_cpu and snap.cpu_clock_mhz is None:
                        snap.cpu_clock_mhz = value
                    elif stype == "Temperature" and is_cpu and snap.cpu_temp_c is None:
                        snap.cpu_temp_c = value
                    elif stype == "Power" and is_cpu and snap.cpu_power_w is None:
                        snap.cpu_power_w = value
                    elif stype == "Clock" and is_gpu and snap.gpu_clock_mhz is None:
                        snap.gpu_clock_mhz = value
                    elif stype == "Temperature" and is_gpu and snap.gpu_temp_c is None:
                        snap.gpu_temp_c = value
        except Exception as e:
            print(f"[sensors] Erro ao ler sensores: {e}")

        return snap


if __name__ == "__main__":
    reader = SensorReader()
    for _ in range(5):
        print(reader.read())
        time.sleep(1)
