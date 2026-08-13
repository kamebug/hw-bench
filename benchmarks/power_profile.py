"""
Comparação de perfil de energia (notebook): tomada vs. bateria.

Cobre o ponto:
  9 - Power limit (PL1/PL2) e comportamento de clock sob diferentes
      fontes de energia

Este módulo NÃO roda a carga em si — ele é um wrapper que:
  1. Detecta se está na tomada ou na bateria (psutil)
  2. Roda o benchmark de CPU sustentado (cpu_sustained.py) rotulando
     o resultado automaticamente com o estado de energia
  3. Avisa se o estado mudou no meio do teste (invalida o resultado)

Uso recomendado: rodar 2x manualmente — uma vez com o notebook na
tomada, outra na bateria — e comparar os CSVs gerados.
"""

import argparse
import sys
import time
from pathlib import Path

import psutil

sys.path.append(str(Path(__file__).resolve().parent.parent))
from benchmarks.cpu_sustained import run_benchmark as run_cpu_sustained


def get_power_state() -> str:
    battery = psutil.sensors_battery()
    if battery is None:
        return "desktop-sem-bateria"
    return "tomada" if battery.power_plugged else "bateria"


def run_with_power_check(duration_s: int, machine_label: str, output_dir: Path):
    state_start = get_power_state()
    print(f"[power_profile] Estado de energia no início: {state_start}")

    full_label = f"{machine_label}-{state_start}"
    csv_path = run_cpu_sustained(duration_s, full_label, output_dir)

    state_end = get_power_state()
    if state_end != state_start:
        print(f"\n⚠️  AVISO: estado de energia mudou durante o teste "
              f"({state_start} -> {state_end}). Resultado pode não ser confiável.")

    print(f"[power_profile] Concluído. Resultado: {csv_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Benchmark de CPU sustentado com rótulo automático de energia"
    )
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--machine", type=str, required=True,
                         help="Nome base da máquina (o estado de energia é anexado automaticamente)")
    parser.add_argument("--output", type=str, default="results")
    args = parser.parse_args()

    run_with_power_check(args.duration, args.machine, Path(args.output))
