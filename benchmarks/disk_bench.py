"""
Benchmark de armazenamento (SSD/HDD/eMMC).

Cobre:
  - Throughput sequencial (leitura e escrita, MB/s)
  - IOPS em acesso aleatório (operações pequenas por segundo)

Metodologia:
  - Escreve/lê um arquivo de teste no diretório alvo (deve ser o disco
    que você quer medir — cuidado ao apontar --target)
  - Warm-up descartado
  - Múltiplas repetições, mediana reportada

NOTA: para medição mais rigorosa (fila de I/O, latência de device),
considere usar `fio` diretamente — este script cobre o suficiente para
comparação prática notebook vs desktop sem dependências externas.
"""

import argparse
import os
import statistics
import time
from pathlib import Path

WARMUP_RUNS = 1
SEQ_FILE_SIZE_MB = 256
RANDOM_BLOCK_SIZE_KB = 4
RANDOM_BLOCK_COUNT = 5000


def sequential_write_read(target_dir: Path, size_mb: int = SEQ_FILE_SIZE_MB):
    test_file = target_dir / "hwbench_seq_test.bin"
    data = os.urandom(1024 * 1024)  # 1MB de dados aleatórios (evita compressão)

    t0 = time.perf_counter()
    with open(test_file, "wb") as f:
        for _ in range(size_mb):
            f.write(data)
        f.flush()
        os.fsync(f.fileno())
    t1 = time.perf_counter()

    # Limpar cache do SO não é trivial sem privilégios elevados;
    # resultado de leitura pode estar otimista se o arquivo ainda
    # estiver em cache. Documentar essa limitação nos resultados.
    with open(test_file, "rb") as f:
        while f.read(1024 * 1024):
            pass
    t2 = time.perf_counter()

    test_file.unlink()

    write_time = t1 - t0
    read_time = t2 - t1
    write_mbps = size_mb / write_time if write_time > 0 else 0
    read_mbps = size_mb / read_time if read_time > 0 else 0

    return write_mbps, read_mbps


def random_iops(target_dir: Path, block_kb: int = RANDOM_BLOCK_SIZE_KB,
                 count: int = RANDOM_BLOCK_COUNT):
    test_file = target_dir / "hwbench_random_test.bin"
    block = os.urandom(block_kb * 1024)

    t0 = time.perf_counter()
    with open(test_file, "wb") as f:
        for _ in range(count):
            f.write(block)
        f.flush()
        os.fsync(f.fileno())
    t1 = time.perf_counter()

    test_file.unlink()

    elapsed = t1 - t0
    iops = count / elapsed if elapsed > 0 else 0
    return iops


def run_benchmark(machine_label: str, target_dir: Path, output_dir: Path):
    target_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[disk_bench] Alvo do teste: {target_dir.resolve()}")
    print("[disk_bench] Warm-up...")
    for _ in range(WARMUP_RUNS):
        sequential_write_read(target_dir)

    print("[disk_bench] Medindo throughput sequencial (3 execuções)...")
    writes, reads = [], []
    for _ in range(3):
        w, r = sequential_write_read(target_dir)
        writes.append(w)
        reads.append(r)

    print("[disk_bench] Medindo IOPS aleatório (blocos de 4KB)...")
    iops_results = [random_iops(target_dir) for _ in range(3)]

    median_write = statistics.median(writes)
    median_read = statistics.median(reads)
    median_iops = statistics.median(iops_results)

    print("\n--- Resultado ---")
    print(f"Escrita sequencial: {median_write:.1f} MB/s")
    print(f"Leitura sequencial: {median_read:.1f} MB/s (pode estar otimista por cache do SO)")
    print(f"IOPS aleatório (4KB): {median_iops:.0f}")

    result_path = output_dir / f"disk_{machine_label}_{int(time.time())}.txt"
    with open(result_path, "w") as f:
        f.write(f"machine={machine_label}\n")
        f.write(f"target_dir={target_dir.resolve()}\n")
        f.write(f"seq_write_mb_s={median_write:.1f}\n")
        f.write(f"seq_read_mb_s={median_read:.1f}\n")
        f.write(f"random_iops_4k={median_iops:.0f}\n")

    print(f"\nResultados salvos em: {result_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark de disco")
    parser.add_argument("--machine", type=str, required=True)
    parser.add_argument("--target", type=str, default=".",
                         help="Diretório no disco a ser testado")
    parser.add_argument("--output", type=str, default="results")
    args = parser.parse_args()

    run_benchmark(args.machine, Path(args.target), Path(args.output))
