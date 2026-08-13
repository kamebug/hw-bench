# hw-bench

Ferramenta própria de benchmark para comparar desempenho de hardware (notebook vs desktop, e futuramente tablet/smartphone), focada em cargas reais e não só em pontuações sintéticas.

## Motivação

Softwares de benchmark prontos (Cinebench, 3DMark, etc.) dão uma pontuação genérica, mas não capturam:
- Throttling térmico sob carga sustentada
- Diferença de comportamento na tomada vs. bateria (notebook)
- Gargalo específico da *sua* tarefa real (compilação, processamento de dados, etc.)

Este projeto mede isso diretamente, com metodologia de warm-up, múltiplas repetições, mediana/percentis e logging de clock/temperatura em paralelo.

## Estrutura

```
hw-bench/
├── benchmarks/
│   ├── cpu_sustained.py      # CPU sob carga sustentada (5-10 min) + throttling
│   ├── memory_bench.py       # Bandwidth de RAM + detecção single/dual channel
│   ├── disk_bench.py         # Throughput sequencial e IOPS aleatório
│   └── power_profile.py      # Comparação tomada vs. bateria, power limit
├── sensors/
│   └── lhm_reader.py         # Wrapper para leitura de clock/temp/power (LibreHardwareMonitor)
├── results/                  # CSVs gerados por execução (por máquina/data)
├── plots/
│   └── plot_results.py       # Gera gráficos comparativos entre execuções/máquinas
├── requirements.txt
└── .gitignore
```

## Requisitos

- Python 3.11+
- Windows: [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) rodando (para leitura de sensores via `pythonnet`)
- `pip install -r requirements.txt`

## Uso básico

```bash
# Rodar benchmark de CPU sustentado (10 min, com log de sensores)
python benchmarks/cpu_sustained.py --duration 600 --machine "notebook-tomada"

# Rodar o mesmo no desktop
python benchmarks/cpu_sustained.py --duration 600 --machine "desktop"

# Gerar gráfico comparativo
python plots/plot_results.py --input results/
```

## Metodologia

Cada benchmark segue o padrão:
1. **Warm-up** — descarta as primeiras execuções
2. **N repetições** — mínimo 10-30 para tarefas curtas
3. **Mediana + percentis (P95/P99)** — não usa média simples
4. **Logging paralelo de sensores** — clock, temperatura, power draw, amostrados a cada segundo
5. **Saída em CSV** — para comparação posterior entre máquinas

## Status

🚧 Em desenvolvimento — estrutura inicial, módulos sendo implementados incrementalmente.

## Máquinas testadas

| Nome | CPU | RAM | Armazenamento | Notas |
|---|---|---|---|---|
| _(preencher)_ | | | | |
