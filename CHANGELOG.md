# Changelog

Todas as mudanças notáveis deste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/).

## [Unreleased]

### Added
- Estrutura inicial do repositório: `benchmarks/`, `sensors/`, `results/`, `plots/`
- Esqueleto de `cpu_sustained.py` (carga sustentada + throttling)
- Esqueleto de `memory_bench.py` (bandwidth + detecção single/dual channel)
- Esqueleto de `disk_bench.py` (throughput sequencial + IOPS)
- Esqueleto de `power_profile.py` (tomada vs. bateria, power limit)
- Esqueleto de `sensors/lhm_reader.py` (wrapper LibreHardwareMonitor)
- Esqueleto de `plots/plot_results.py` (gráficos comparativos)
- README com metodologia e instruções de uso
