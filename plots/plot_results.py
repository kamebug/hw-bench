"""
Gera gráficos comparativos a partir dos CSVs em results/.

Foco principal: tempo por iteração ao longo do tempo (cpu_sustained),
para visualizar degradação/throttling entre diferentes máquinas ou
estados de energia.
"""

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


def load_cpu_sustained_csv(path: Path):
    iterations, times, clocks, temps = [], [], [], []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            iterations.append(int(row["iteration"]))
            times.append(float(row["time_s"]))
            clocks.append(float(row["cpu_clock_mhz"]) if row["cpu_clock_mhz"] else None)
            temps.append(float(row["cpu_temp_c"]) if row["cpu_temp_c"] else None)
    return iterations, times, clocks, temps


def plot_comparison(csv_paths: list[Path], output_path: Path):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=False)

    has_clock_data = False
    for path in csv_paths:
        iterations, times, clocks, temps = load_cpu_sustained_csv(path)
        label = path.stem.replace("cpu_sustained_", "")

        ax1.plot(iterations, [t * 1000 for t in times], label=label, alpha=0.8)

        if any(c is not None for c in clocks):
            ax2.plot(iterations, clocks, label=label, alpha=0.8)
            has_clock_data = True

    ax1.set_xlabel("Iteração")
    ax1.set_ylabel("Tempo por iteração (ms)")
    ax1.set_title("Tempo por iteração ao longo da carga sustentada")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    if has_clock_data:
        ax2.set_xlabel("Amostra de sensor (~1/s)")
        ax2.set_ylabel("Clock CPU (MHz)")
        ax2.set_title("Clock da CPU ao longo do teste")
        ax2.legend()
        ax2.grid(True, alpha=0.3)
    else:
        ax2.text(0.5, 0.5, "Sem dados de sensor (LibreHardwareMonitor não configurado)",
                  ha="center", va="center", transform=ax2.transAxes, color="gray")
        ax2.set_xticks([])
        ax2.set_yticks([])

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Gráfico salvo em: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera gráficos comparativos de resultados")
    parser.add_argument("--input", type=str, default="results",
                         help="Diretório com os CSVs de cpu_sustained")
    parser.add_argument("--output", type=str, default="results/comparison.png")
    args = parser.parse_args()

    input_dir = Path(args.input)
    csv_files = sorted(input_dir.glob("cpu_sustained_*.csv"))

    if not csv_files:
        print(f"Nenhum CSV de cpu_sustained encontrado em {input_dir}")
    else:
        plot_comparison(csv_files, Path(args.output))
