"""
Teste de resposta térmica (aquecimento/resfriamento) em ciclos.

Cobre um cenário específico: quando o sensor de RPM da ventoinha não está
disponível via LibreHardwareMonitor (comum em notebooks com EC/firmware
fechado, ex: muitos modelos HP/Dell), este teste mede o EFEITO da
ventoinha em vez do RPM direto.

Lógica:
  - N ciclos de (carga intensa por BURST_S segundos) + (repouso por
    REST_S segundos)
  - Durante cada ciclo, loga temperatura por segundo
  - Calcula taxa de aquecimento (°C/s) durante a carga
  - Calcula taxa de resfriamento (°C/s) durante o repouso
  - Compara a CONSISTÊNCIA entre ciclos — uma ventoinha saudável produz
    curvas de resfriamento parecidas entre um ciclo e outro; uma
    ventoinha com falha intermitente produz resfriamento irregular
    (às vezes rápido, às vezes lento, sem relação com a carga aplicada)

Também tenta ler RPM de fan via WMI (Win32_Fan), que às vezes expõe
dados diferentes do LibreHardwareMonitor em alguns notebooks — sem
garantia de funcionar, mas sem custo tentar.
"""

import argparse
import csv
import platform
import statistics
import threading
import time
from pathlib import Path

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from sensors.lhm_reader import SensorReader

BURST_S = 30       # duração de cada rajada de carga
REST_S = 60        # duração de cada repouso (resfriamento)
N_CYCLES = 5        # número de ciclos carga+repouso
SENSOR_POLL_INTERVAL_S = 1.0


def cpu_burn(stop_flag: dict):
    """Carga intensa de CPU até stop_flag['stop'] virar True."""
    n = 2
    while not stop_flag["stop"]:
        n * n
        n += 1
        if n > 10_000_000:
            n = 2


def try_read_fan_rpm_wmi():
    """Tenta ler RPM de fan via WMI Win32_Fan (alternativa ao LHM)."""
    if platform.system() != "Windows":
        return None
    try:
        import wmi
        c = wmi.WMI()
        fans = c.Win32_Fan()
        if not fans:
            return None
        return [
            {"name": f.Name, "status": f.Status,
             "variable_speed": f.VariableSpeed}
            for f in fans
        ]
    except Exception:
        return None


def run_sensor_logger(reader: SensorReader, stop_event: threading.Event, log: list):
    while not stop_event.is_set():
        log.append(reader.read())
        time.sleep(SENSOR_POLL_INTERVAL_S)


def run_thermal_response_test(machine_label: str, output_dir: Path,
                               burst_s: int, rest_s: int, n_cycles: int):
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    csv_path = output_dir / f"fan_thermal_{machine_label}_{timestamp}.csv"

    reader = SensorReader()

    wmi_fans = try_read_fan_rpm_wmi()
    if wmi_fans:
        print(f"[fan_thermal] Sensores WMI Win32_Fan encontrados: {wmi_fans}")
    else:
        print("[fan_thermal] Nenhum sensor de fan via WMI (esperado em vários notebooks).")

    sensor_log = []
    stop_event = threading.Event()
    sensor_thread = threading.Thread(
        target=run_sensor_logger, args=(reader, stop_event, sensor_log)
    )
    sensor_thread.start()

    cycles_summary = []

    print(f"[fan_thermal] Iniciando {n_cycles} ciclos de {burst_s}s carga + {rest_s}s repouso...")
    print("[fan_thermal] Deixe a máquina em repouso durante o teste (sem uso ativo).\n")

    overall_start_idx = len(sensor_log)

    for cycle in range(1, n_cycles + 1):
        print(f"[fan_thermal] Ciclo {cycle}/{n_cycles} — carga ({burst_s}s)...")
        burst_start_idx = len(sensor_log)

        stop_flag = {"stop": False}
        n_threads = 4
        threads = [threading.Thread(target=cpu_burn, args=(stop_flag,))
                   for _ in range(n_threads)]
        for t in threads:
            t.start()
        time.sleep(burst_s)
        stop_flag["stop"] = True
        for t in threads:
            t.join()

        burst_end_idx = len(sensor_log)

        print(f"[fan_thermal] Ciclo {cycle}/{n_cycles} — repouso ({rest_s}s)...")
        time.sleep(rest_s)
        rest_end_idx = len(sensor_log)

        # --- calcular taxas de aquecimento/resfriamento deste ciclo ---
        burst_samples = [s for s in sensor_log[burst_start_idx:burst_end_idx]
                          if s.cpu_temp_c is not None]
        rest_samples = [s for s in sensor_log[burst_end_idx:rest_end_idx]
                         if s.cpu_temp_c is not None]

        heat_rate = None
        cool_rate = None
        temp_peak = None
        temp_before = None
        temp_after = None

        if len(burst_samples) >= 2:
            temp_before = burst_samples[0].cpu_temp_c
            temp_peak = max(s.cpu_temp_c for s in burst_samples)
            dt = burst_samples[-1].timestamp - burst_samples[0].timestamp
            if dt > 0:
                heat_rate = (burst_samples[-1].cpu_temp_c - temp_before) / dt

        if len(rest_samples) >= 2:
            temp_after = rest_samples[-1].cpu_temp_c
            dt = rest_samples[-1].timestamp - rest_samples[0].timestamp
            if dt > 0:
                cool_rate = (rest_samples[0].cpu_temp_c - temp_after) / dt

        cycles_summary.append({
            "cycle": cycle,
            "temp_before_c": temp_before,
            "temp_peak_c": temp_peak,
            "temp_after_rest_c": temp_after,
            "heat_rate_c_per_s": heat_rate,
            "cool_rate_c_per_s": cool_rate,
        })

        print(f"  -> pico: {temp_peak}°C | aquecimento: "
              f"{heat_rate:.3f}°C/s" if heat_rate else "  -> aquecimento: N/A",
              f"| resfriamento: {cool_rate:.3f}°C/s" if cool_rate else "| resfriamento: N/A")

    stop_event.set()
    sensor_thread.join()

    # --- análise de consistência entre ciclos ---
    cool_rates = [c["cool_rate_c_per_s"] for c in cycles_summary if c["cool_rate_c_per_s"] is not None]
    heat_rates = [c["heat_rate_c_per_s"] for c in cycles_summary if c["heat_rate_c_per_s"] is not None]

    print("\n--- Resumo por ciclo ---")
    for c in cycles_summary:
        print(f"Ciclo {c['cycle']}: antes={c['temp_before_c']} pico={c['temp_peak_c']} "
              f"após_repouso={c['temp_after_rest_c']} "
              f"aquecimento={c['heat_rate_c_per_s']} cool={c['cool_rate_c_per_s']}")

    print("\n--- Consistência entre ciclos (proxy de saúde da ventoinha) ---")
    if len(cool_rates) >= 2:
        cool_median = statistics.median(cool_rates)
        cool_stdev = statistics.stdev(cool_rates)
        cv = (cool_stdev / cool_median * 100) if cool_median else float("inf")
        print(f"Taxa de resfriamento — mediana: {cool_median:.3f}°C/s | "
              f"desvio padrão: {cool_stdev:.3f}°C/s | "
              f"coeficiente de variação: {cv:.1f}%")
        if cv > 30:
            print("⚠️  Alta variação entre ciclos de resfriamento — "
                  "consistente com ventoinha de comportamento irregular "
                  "(pode explicar o alerta intermitente no boot).")
        else:
            print("Resfriamento consistente entre ciclos — sem indício "
                  "forte de irregularidade neste teste.")
    else:
        print("Amostras insuficientes para avaliar consistência "
              "(verifique se os sensores de temperatura estão disponíveis).")

    # --- salvar CSV ---
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["cycle", "temp_before_c", "temp_peak_c",
                          "temp_after_rest_c", "heat_rate_c_per_s", "cool_rate_c_per_s"])
        for c in cycles_summary:
            writer.writerow([c["cycle"], c["temp_before_c"], c["temp_peak_c"],
                              c["temp_after_rest_c"], c["heat_rate_c_per_s"],
                              c["cool_rate_c_per_s"]])

    raw_csv_path = output_dir / f"fan_thermal_{machine_label}_{timestamp}_raw.csv"
    with open(raw_csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "cpu_temp_c", "cpu_clock_mhz", "cpu_power_w"])
        for s in sensor_log[overall_start_idx:]:
            writer.writerow([s.timestamp, s.cpu_temp_c, s.cpu_clock_mhz, s.cpu_power_w])

    print(f"\nResumo por ciclo salvo em: {csv_path}")
    print(f"Log bruto de sensores salvo em: {raw_csv_path}")
    return csv_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Teste de resposta térmica (proxy de saúde de ventoinha)"
    )
    parser.add_argument("--machine", type=str, required=True)
    parser.add_argument("--burst", type=int, default=BURST_S,
                         help="Duração da carga por ciclo, em segundos")
    parser.add_argument("--rest", type=int, default=REST_S,
                         help="Duração do repouso por ciclo, em segundos")
    parser.add_argument("--cycles", type=int, default=N_CYCLES,
                         help="Número de ciclos carga+repouso")
    parser.add_argument("--output", type=str, default="results")
    args = parser.parse_args()

    run_thermal_response_test(args.machine, Path(args.output),
                               args.burst, args.rest, args.cycles)
