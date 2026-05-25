# -*- coding: utf-8 -*-
"""
Evaluación de configuraciones bajo el criterio de SLA definido por el TP.

Criterios:
  - PPSA  <= 3 días (permanencia promedio Alta)
  - PPSN  <= 5 días (permanencia promedio Normal)
  - PTOA  <= 35 %  (ociosidad línea Alta — rentabilidad)
  - PTON  <= 35 %  (ociosidad línea Normal — rentabilidad)

Una configuración (NA, NN) se considera ACEPTABLE si cumple los 4 simultáneamente.
La óptima es la de MENOR cantidad total (NA + NN) que sea aceptable.

TF = 88.000 minutos ≈ 61 días = ~2 meses reales (largo de un período del año).
"""

import statistics
from src.simulacion import simular


# Criterios de aceptación (SLA)
SLA = {
    "PPSA_max_dias": 3.0,
    "PPSN_max_dias": 5.0,
    "PTOA_max": 0.35,
    "PTON_max": 0.35,
}

# Grid de configuraciones a evaluar por período.
# Se barre desde "saturado" hasta "cómodo" para encontrar el mínimo aceptable.
GRID = {
    "ene-feb": [(70, 140), (75, 150), (80, 160), (85, 170), (90, 180)],
    "jun-jul": [(115, 230), (125, 250), (135, 270), (145, 290), (155, 310)],
    "nov-dic": [(220, 440), (230, 460), (240, 480), (250, 500), (260, 520)],
}

SEEDS = [42, 123, 456]
TF = 88_000.0  # ~61 días simulados


def stats_de(corridas, metrica):
    vals = [c[metrica] for c in corridas]
    return statistics.mean(vals), (statistics.stdev(vals) if len(vals) > 1 else 0.0)


def cumple_sla(ppsa_d, ppsn_d, ptoa, pton):
    """Devuelve dict con cada criterio y un booleano global."""
    chequeos = {
        "PPSA": ppsa_d <= SLA["PPSA_max_dias"],
        "PPSN": ppsn_d <= SLA["PPSN_max_dias"],
        "PTOA": ptoa <= SLA["PTOA_max"],
        "PTON": pton <= SLA["PTON_max"],
    }
    return chequeos, all(chequeos.values())


def fmt_dias(media_min, desv_min):
    return f"{media_min / 1440:.2f}±{desv_min / 1440:.2f}"


def fmt_pct(media, desv):
    return f"{media * 100:.1f}±{desv * 100:.1f}"


print(f"""
SLA usado:
  PPSA <= {SLA['PPSA_max_dias']} días
  PPSN <= {SLA['PPSN_max_dias']} días
  PTOA <= {SLA['PTOA_max'] * 100:.0f} %
  PTON <= {SLA['PTON_max'] * 100:.0f} %

TF = {TF:.0f} min  ({TF / 1440:.1f} días simulados por corrida)
Semillas: {SEEDS}
""")

print(f"{'Período':<8} {'NA':>4} {'NN':>4} | "
      f"{'PPSA [d]':>13} {'PPSN [d]':>13} | "
      f"{'PTOA [%]':>11} {'PTON [%]':>11} | "
      f"{'cumple SLA?':<20}")
print("-" * 105)

# Tracking del óptimo por período
optimos = {}

for periodo, configs in GRID.items():
    aceptables_periodo = []
    for na, nn in configs:
        print(f"... {periodo} NA={na} NN={nn}", end="\r", flush=True)
        corridas = [simular(na, nn, TF, periodo, semilla=s) for s in SEEDS]

        ppsa_m, ppsa_s = stats_de(corridas, "PPSA")
        ppsn_m, ppsn_s = stats_de(corridas, "PPSN")
        ptoa_m, ptoa_s = stats_de(corridas, "PTOA")
        pton_m, pton_s = stats_de(corridas, "PTON")

        ppsa_d = ppsa_m / 1440
        ppsn_d = ppsn_m / 1440
        chequeos, ok = cumple_sla(ppsa_d, ppsn_d, ptoa_m, pton_m)

        marca = "✅ ACEPTABLE" if ok else "❌"
        falla = "" if ok else " falla: " + ",".join(k for k, v in chequeos.items() if not v)

        print(
            f"{periodo:<8} {na:>4} {nn:>4} | "
            f"{fmt_dias(ppsa_m, ppsa_s):>13} {fmt_dias(ppsn_m, ppsn_s):>13} | "
            f"{fmt_pct(ptoa_m, ptoa_s):>11} {fmt_pct(pton_m, pton_s):>11} | "
            f"{marca}{falla}"
        )

        if ok:
            aceptables_periodo.append((na, nn, ptoa_m, pton_m, ppsn_d))

    # El óptimo del período es el aceptable con menor (NA + NN)
    if aceptables_periodo:
        optimo = min(aceptables_periodo, key=lambda x: x[0] + x[1])
        optimos[periodo] = optimo
    print("-" * 105)


# Resumen final
print("\n" + "=" * 60)
print("ÓPTIMOS POR PERÍODO BAJO EL SLA DEFINIDO")
print("=" * 60)
for periodo, (na, nn, ptoa, pton, ppsn_d) in optimos.items():
    print(f"  {periodo:<10}  →  (NA={na}, NN={nn})  total={na + nn}  "
          f"PTOA={ptoa * 100:.1f}%  PTON={pton * 100:.1f}%  PPSN={ppsn_d:.2f}d")
