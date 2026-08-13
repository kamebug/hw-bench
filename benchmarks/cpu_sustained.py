"""
Benchmark de CPU sob carga sustentada.

Cobre os pontos:
  7 - CPU sustentado (tomada vs. bateria, deve ser rodado 2x manualmente)
  8 - Throttling térmico sob carga prolongada

Metodologia:
  - Warm-up: descarta as primeiras WARMUP_ITERATIONS execuções
  - Carga fixa e repetível (cálculo de primos) rodando em loop pela
    duração total definida
  - Log de tempo por iteração + snapshot de sensores em thread paralela
  - Ao final: mediana, P95, P99, desvio padrão, e detecção de throttling
    (queda de clock > THROTTLE_THRESHOLD entre início e fim)
"""

import argparse
import csv
import statistics
import threading
import time
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from sensors.lhm_reader import SensorReader

WARMUP_ITERATIONS = 3
THROTTLE_THRESHOLD = 0.15  # 15% de queda de clock = throttling detectado
SENSOR_POLL_INTERVAL_S = 1.0


def cpu_work(n: int = 200_000) -> int:
    """Carga de CPU fixa e repetível: contagem de primos até n (single-thread)."""
    count = 0
    for num in range(2, n):
        is_prime = True
        for i in range(2, int(num ** 0.5) + 1):
            if num % i == 0:
                is_prime = False
                break
        if is_prime:
            count += 1
    return count


def run_sensor_logger(reader: SensorReader, stop_event: threading.Event, log: list):
    while not stop_event.is_set():
        log.append(reader.read())
        time.sleep(SENSOR_POLL_INTERVAL_S)


def run_benchmark(duration_s: int, machine_label: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = output_dir / f"cpu_sustained_{machine_label}_{timestamp}.csv"

    reader = SensorReader()
    sensor_log = []
    stop_event = threading.Event()
    sensor_thread = threading.Thread(
        target=run_sensor_logger, args=(reader, stop_event, sensor_log)
    )
    sensor_thread.start()

    print(f"[cpu_sustained] Warm-up ({WARMUP_ITERATIONS} iterações)...")
    for _ in range(WARMUP_ITERATIONS):
        cpu_work()

    print(f"[cpu_sustained] Iniciando carga sustentada por {duration_s}s...")
    iteration_times = []
    start = time.perf_counter()
    end_target = start + duration_s

    while time.perf_counter() < end_target:
        t0 = time.perf_counter()
        cpu_work()
        t1 = time.perf_counter()
        iteration_times.append(t1 - t0)

    stop_event.set()
    sensor_thread.join()

    # --- Estatísticas ---
    median = statistics.median(iteration_times)
    stdev = statistics.stdev(iteration_times) if len(iteration_times) > 1 else 0
    sorted_times = sorted(iteration_times)
    p95 = sorted_times[int(len(sorted_times) * 0.95)]
    p99 = sorted_times[int(len(sorted_times) * 0.99)]

    throttle_detected = False
    if sensor_log and sensor_log[0].cpu_clock_mhz and sensor_log[-1].cpu_clock_mhz:
        clock_start = sensor_log[0].cpu_clock_mhz
        clock_end = sensor_log[-1].cpu_clock_mhz
        drop = (clock_start - clock_end) / clock_start
        throttle_detected = drop > THROTTLE_THRESHOLD

    print("\n--- Resultado ---")
    print(f"Iterações completas: {len(iteration_times)}")
    print(f"Mediana: {median*1000:.1f} ms | P95: {p95*1000:.1f} ms | P99: {p99*1000:.1f} ms")
    print(f"Desvio padrão: {stdev*1000:.1f} ms")
    print(f"Throttling detectado: {'SIM' if throttle_detected else 'não'}")

    # --- Salvar CSV ---
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iteration", "time_s", "timestamp",
                          "cpu_clock_mhz", "cpu_temp_c", "cpu_power_w"])
        for i, t in enumerate(iteration_times):
            sensor = sensor_log[i] if i < len(sensor_log) else None
            writer.writerow([
                i, t,
                sensor.timestamp if sensor else "",
                sensor.cpu_clock_mhz if sensor else "",
                sensor.cpu_temp_c if sensor else "",
                sensor.cpu_power_w if sensor else "",
            ])

    print(f"\nResultados salvos em: {csv_path}")
    return csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark de CPU sustentado")
    parser.add_argument("--duration", type=int, default=600,
                         help="Duração do teste em segundos (padrão: 600 = 10 min)")
    parser.add_argument("--machine", type=str, required=True,
                         help="Rótulo da máquina/cenário (ex: 'notebook-tomada')")
    parser.add_argument("--output", type=str, default="results",
                         help="Diretório de saída dos CSVs")
    args = parser.parse_args()

    run_benchmark(args.duration, args.machine, Path(args.output))
