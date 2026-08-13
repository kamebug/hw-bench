"""
Benchmark de memória (RAM).

Cobre o ponto:
  11 - Configuração real de RAM (single/dual channel) + bandwidth efetivo

Metodologia:
  - Alocação de bloco grande e leitura/escrita sequencial (mede bandwidth)
  - Acesso aleatório (mede latência efetiva)
  - Detecção de canal via WMI (Windows) — número de módulos populados
    não confirma dual-channel sozinho, mas combinado com bandwidth medido
    dá um indício forte (bandwidth ~2x sugere dual-channel ativo)
"""

import argparse
import platform
import statistics
import time
from pathlib import Path

import numpy as np

WARMUP_ITERATIONS = 2
BLOCK_SIZE_MB = 512
RANDOM_ACCESS_SAMPLES = 1_000_000


def sequential_bandwidth_test(block_size_mb: int = BLOCK_SIZE_MB) -> float:
    """Retorna bandwidth medido em MB/s para escrita+leitura sequencial."""
    n_elements = (block_size_mb * 1024 * 1024) // 8  # float64 = 8 bytes
    arr = np.zeros(n_elements, dtype=np.float64)

    t0 = time.perf_counter()
    arr[:] = 1.0  # escrita sequencial
    t1 = time.perf_counter()
    _ = arr.sum()  # leitura sequencial forçada
    t2 = time.perf_counter()

    write_time = t1 - t0
    read_time = t2 - t1
    total_mb = block_size_mb
    write_bw = total_mb / write_time if write_time > 0 else 0
    read_bw = total_mb / read_time if read_time > 0 else 0

    return (write_bw + read_bw) / 2


def random_access_latency_test(samples: int = RANDOM_ACCESS_SAMPLES) -> float:
    """Retorna tempo médio (ns) por acesso aleatório em array grande."""
    n_elements = 50_000_000  # array grande o suficiente pra não caber em cache
    arr = np.random.rand(n_elements).astype(np.float64)
    indices = np.random.randint(0, n_elements, size=samples)

    t0 = time.perf_counter()
    total = 0.0
    for idx in indices:
        total += arr[idx]
    t1 = time.perf_counter()

    return ((t1 - t0) / samples) * 1e9  # ns por acesso


def detect_memory_config_windows() -> dict:
    """Tenta detectar número de módulos e canais via WMI. Retorna dict cru."""
    try:
        import wmi
        c = wmi.WMI()
        modules = c.Win32_PhysicalMemory()
        return {
            "modules_populated": len(modules),
            "capacities_mb": [int(m.Capacity) // (1024 * 1024) for m in modules],
            "speeds_mhz": [m.Speed for m in modules],
        }
    except Exception as e:
        return {"error": str(e)}


def run_benchmark(machine_label: str, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[memory_bench] Warm-up...")
    for _ in range(WARMUP_ITERATIONS):
        sequential_bandwidth_test()

    print("[memory_bench] Medindo bandwidth sequencial (5 execuções)...")
    bandwidths = [sequential_bandwidth_test() for _ in range(5)]
    median_bw = statistics.median(bandwidths)

    print("[memory_bench] Medindo latência de acesso aleatório...")
    latency_ns = random_access_latency_test()

    config = {}
    if platform.system() == "Windows":
        config = detect_memory_config_windows()
    else:
        # TODO: implementar leitura via `dmidecode --type 17` (requer sudo)
        config = {"note": "detecção de canal não implementada para Linux ainda"}

    print("\n--- Resultado ---")
    print(f"Bandwidth mediano (seq. R+W): {median_bw:.1f} MB/s")
    print(f"Latência de acesso aleatório: {latency_ns:.1f} ns")
    print(f"Config detectada: {config}")

    # Heurística simples: bandwidth muito abaixo do esperado para o tipo de
    # RAM declarado é indício de single-channel. Comparação real deve ser
    # feita manualmente entre as duas máquinas testadas.

    result_path = output_dir / f"memory_{machine_label}_{int(time.time())}.txt"
    with open(result_path, "w") as f:
        f.write(f"machine={machine_label}\n")
        f.write(f"bandwidth_mb_s_median={median_bw:.1f}\n")
        f.write(f"random_access_latency_ns={latency_ns:.1f}\n")
        f.write(f"config={config}\n")

    print(f"\nResultados salvos em: {result_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark de memória (RAM)")
    parser.add_argument("--machine", type=str, required=True)
    parser.add_argument("--output", type=str, default="results")
    args = parser.parse_args()

    run_benchmark(args.machine, Path(args.output))
