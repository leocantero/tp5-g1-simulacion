# -*- coding: utf-8 -*-
"""
Simulación evento-a-evento del sistema de procesamiento de pedidos.

Implementación del modelo descripto en docs/diagrama_flujo.md.

Modelo:
  - 2 líneas de procesamiento: CA (Alta) y CN (Normal).
  - CA atiende solo Alta.
  - CN atiende Normal, con preferencia por Alta si hay cola.
  - Política no apropiativa: no se interrumpen pedidos en curso.
  - Cuando un pedido Alta es absorbido por CN, su tiempo de atención
    es TEN y se contabiliza dentro de las métricas de la línea CN.

Uso (CLI):
    python src/simulacion.py --na 2 --nn 3 --tf 100000 --periodo nov-dic
    python src/simulacion.py --help

Unidades:
  - IA en minutos.
  - TEA / TEN en horas.
  - Internamente toda la simulación se ejecuta en minutos.
"""

import argparse
import math
import random
from collections import deque

import numpy as np
import scipy.stats as stats


# ============================================================
# Constantes
# ============================================================

HV = math.inf       # "High Value" — marca de servidor ocioso (∞)
PA = 0.37           # Probabilidad de prioridad Alta (37 % del análisis histórico)


# ============================================================
# FDPs ajustadas con Fitter
# ============================================================
# Cada entrada es (distribución_scipy, parámetros).
# Las distribuciones tienen `.rvs(**params)` para sampleo.
#
# IA está en minutos.
# TEA / TEN están en horas → al samplearlas las multiplicamos por 60.

FDP_IA = {
    "ene-feb": (stats.ncx2, {
        "df": 0.7604291794469409,
        "nc": 3.518888356394447,
        "loc": -6.613324951251212e-28,
        "scale": 3.0178260644424277,
    }),
    "jun-jul": (stats.beta, {
        "a": 0.7632600385330038,
        "b": 4.143411889679016,
        "loc": -4.921542372038384e-31,
        "scale": 55.051123296334374,
    }),
    "nov-dic": (stats.weibull_min, {
        "c": 0.760100620038912,
        "loc": -2.866788783209454e-28,
        "scale": 4.5240085261297445,
    }),
}

# TEA = tiempo de atención de la línea Alta (CA) → ajustadas sobre TA_INTERNO
#       (sin tiempo de courier), pedidos con prioridad Alta.
FDP_TEA = {
    "ene-feb": (stats.fatiguelife, {
        "c": 0.8173444924612989,
        "loc": -7.347939202359484,
        "scale": 43.2479242380293,
    }),
    "jun-jul": (stats.exponnorm, {
        "K": 9.255506107567733,
        "loc": 6.134989034764647,
        "scale": 5.348539557467658,
    }),
    "nov-dic": (stats.johnsonsb, {
        "a": 0.8102812586409457,
        "b": 0.7553987920301383,
        "loc": 4.657143721630327,
        "scale": 202.09768602691355,
    }),
}

# TEN = tiempo de atención de la línea Normal (CN) → ajustadas sobre TA_INTERNO
#       (sin tiempo de courier), pedidos con prioridad Normal.
FDP_TEN = {
    "ene-feb": (stats.truncpareto, {
        # Nota: parámetros numéricamente extremos pero el muestreo es consistente
        # con la distribución empírica (mean ~51h, median ~39h).
        "b": 71574301.32936329,
        "c": 1.0000000448950088,
        "loc": -4294967295.7447224,
        "scale": 4294967296.0,
    }),
    "jun-jul": (stats.exponnorm, {
        "K": 8.114367333150753,
        "loc": 7.373745534642079,
        "scale": 5.9547487921762325,
    }),
    "nov-dic": (stats.genhyperbolic, {
        "p": 1.4075785416656272,
        "a": 0.0016021006145983362,
        "b": 0.0015418028598118945,
        "loc": 6.645645144652001,
        "scale": 0.0025017674548440177,
    }),
}


# ============================================================
# Subrutinas de variables aleatorias
# ============================================================
# R, IA, TEA, TEN del diagrama. Las gen_X aplican la FDP del período
# y descartan valores no positivos (algunas distribuciones ajustadas
# pueden generar valores negativos en su cola izquierda por el loc).

def _sample_positive(dist, params):
    """Samplea hasta obtener un valor estrictamente positivo."""
    while True:
        v = float(dist.rvs(**params))
        if v > 0:
            return v


def gen_R():
    """Subrutina R: número aleatorio uniforme U(0,1)."""
    return random.random()


def gen_IA(periodo):
    """Intervalo entre arribos del período (en minutos)."""
    dist, params = FDP_IA[periodo]
    return _sample_positive(dist, params)


def gen_TEA(periodo):
    """Tiempo de atención CA (línea Alta) del período (en minutos)."""
    dist, params = FDP_TEA[periodo]
    return _sample_positive(dist, params) * 60   # horas → minutos


def gen_TEN(periodo):
    """Tiempo de atención CN (línea Normal) del período (en minutos)."""
    dist, params = FDP_TEN[periodo]
    return _sample_positive(dist, params) * 60   # horas → minutos


# ============================================================
# Núcleo de la simulación
# ============================================================

def simular(NA, NN, TF, periodo, semilla=42):
    """
    Ejecuta una corrida con la configuración dada.

    Parámetros
    ----------
    NA : int     — cantidad de operarios CA (línea Alta)
    NN : int     — cantidad de operarios CN (línea Normal)
    TF : float   — tiempo final de simulación (minutos)
    periodo : str — 'ene-feb' | 'jun-jul' | 'nov-dic'
    semilla : int — semilla aleatoria

    Retorna un dict con todas las métricas de salida.
    """
    # Reproducibilidad: fijar ambas fuentes de aleatoriedad
    random.seed(semilla)
    np.random.seed(semilla)

    # ────────── ESTADO INICIAL (CI del diagrama) ──────────
    T = 0.0
    NSa = 0
    NSn = 0

    # TEF — Tabla de Eventos Futuros
    TPSA = [HV] * NA            # próxima salida de cada operario CA
    TPSN = [HV] * NN            # próxima salida de cada operario CN
    TPLL = gen_IA(periodo)      # primera llegada (se genera en CI)

    # Colas FIFO — guardan el tiempo de arribo (T_arribo) de cada pedido en espera
    CQA = deque()               # cola línea Alta
    CQN = deque()               # cola línea Normal

    # Inicio del tramo ocioso actual de cada operario
    ITOA = [0.0] * NA
    ITON = [0.0] * NN

    # ────────── ACUMULADORES ──────────
    Nt = 0
    NtA = 0
    NtN = 0
    STLL = 0.0
    STLLA = 0.0
    STLLN = 0.0
    STSA = 0.0
    STSN = 0.0
    STAA = 0.0
    STNN = 0.0
    STECA = 0.0
    STECN = 0.0
    STOA = [0.0] * NA
    STON = [0.0] * NN

    # ────────── LOOP PRINCIPAL ──────────
    while True:

        # Próximo evento: árbol de comparación del diagrama
        i_star = min(range(NA), key=lambda i: TPSA[i])
        j_star = min(range(NN), key=lambda j: TPSN[j])
        TPSA_MIN = TPSA[i_star]
        TPSN_MIN = TPSN[j_star]

        if TPSA_MIN <= TPSN_MIN:
            if TPLL <= TPSA_MIN:
                evento, T = "LLEGADA", TPLL
            else:
                evento, T = "SALIDA_A", TPSA_MIN
        else:
            if TPLL <= TPSN_MIN:
                evento, T = "LLEGADA", TPLL
            else:
                evento, T = "SALIDA_N", TPSN_MIN

        # ────────── EVENTO: LLEGADA ──────────
        if evento == "LLEGADA":
            Nt += 1
            STLL += T
            TPLL = T + gen_IA(periodo)   # programar siguiente llegada

            if gen_R() <= PA:
                # ===== LLEGADA ALTA =====
                if NSa < NA:
                    # CA libre → asignar a CA con TEA
                    i = next(k for k in range(NA) if TPSA[k] == HV)
                    NSa += 1
                    TEA = gen_TEA(periodo)
                    TPSA[i] = T + TEA
                    NtA += 1
                    STLLA += T
                    # STECA += 0   (no esperó en cola)
                    STAA += TEA
                    STOA[i] += T - ITOA[i]
                elif NSn < NN:
                    # CA full + CN libre → CN absorbe el Alta con TEN
                    j = next(k for k in range(NN) if TPSN[k] == HV)
                    NSn += 1
                    TEN = gen_TEN(periodo)
                    TPSN[j] = T + TEN
                    NtN += 1
                    STLLN += T
                    # STECN += 0
                    STNN += TEN
                    STON[j] += T - ITON[j]
                else:
                    # Ambas líneas full → cola Alta
                    NSa += 1
                    CQA.append(T)
            else:
                # ===== LLEGADA NORMAL =====
                if NSn < NN:
                    # CN libre → asignar
                    j = next(k for k in range(NN) if TPSN[k] == HV)
                    NSn += 1
                    TEN = gen_TEN(periodo)
                    TPSN[j] = T + TEN
                    NtN += 1
                    STLLN += T
                    # STECN += 0
                    STNN += TEN
                    STON[j] += T - ITON[j]
                else:
                    # CN full → cola Normal
                    NSn += 1
                    CQN.append(T)

        # ────────── EVENTO: SALIDA ALTA ──────────
        elif evento == "SALIDA_A":
            NSa -= 1
            STSA += T
            if NSa >= NA:
                # Queda cola Alta → CA[i_star] toma el siguiente
                Tarr = CQA.popleft()
                TEA = gen_TEA(periodo)
                TPSA[i_star] = T + TEA
                NtA += 1
                STLLA += Tarr
                STECA += T - Tarr
                STAA += TEA
            else:
                # CA[i_star] queda ocioso
                TPSA[i_star] = HV
                ITOA[i_star] = T

        # ────────── EVENTO: SALIDA NORMAL ──────────
        else:  # SALIDA_N
            NSn -= 1
            STSN += T

            if NSa > NA:
                # Cola Alta no vacía → transferir Alta a CN[j_star] con TEN
                NSa -= 1
                NSn += 1
                Tarr = CQA.popleft()
                TEN = gen_TEN(periodo)
                TPSN[j_star] = T + TEN
                NtN += 1
                STLLN += Tarr
                STECN += T - Tarr   # espera del Alta, contabilizada en línea CN
                STNN += TEN

            elif NSn >= NN:
                # Cola Normal no vacía → CN[j_star] toma siguiente Normal
                Tarr = CQN.popleft()
                TEN = gen_TEN(periodo)
                TPSN[j_star] = T + TEN
                NtN += 1
                STLLN += Tarr
                STECN += T - Tarr
                STNN += TEN

            else:
                # CN[j_star] queda ocioso
                TPSN[j_star] = HV
                ITON[j_star] = T

        # ────────── CONTROL T <= TF y VACIAMIENTO ──────────
        if T > TF:
            if NSa == 0 and NSn == 0:
                break               # sistema vacío → fin
            else:
                TPLL = HV           # cortar llegadas, drenar colas

    # ────────── CIERRE: idle final de operarios todavía ociosos ──────────
    for i in range(NA):
        if TPSA[i] == HV:
            STOA[i] += T - ITOA[i]
    for j in range(NN):
        if TPSN[j] == HV:
            STON[j] += T - ITON[j]

    T_final = T

    # ────────── SUBRUTINA RESULTADOS ──────────
    PPSA = (STSA - STLLA) / NtA if NtA > 0 else 0.0
    PPSN = (STSN - STLLN) / NtN if NtN > 0 else 0.0
    PPS = (STSA + STSN - STLL) / Nt if Nt > 0 else 0.0

    PECA = STECA / NtA if NtA > 0 else 0.0
    PECN = STECN / NtN if NtN > 0 else 0.0

    PTOA_i = [STOA[i] / T_final for i in range(NA)]
    PTON_j = [STON[j] / T_final for j in range(NN)]
    PTOA = sum(PTOA_i) / NA
    PTON = sum(PTON_j) / NN

    return {
        "config": {
            "NA": NA, "NN": NN, "TF": TF,
            "periodo": periodo, "T_final": T_final,
        },
        "Nt": Nt, "NtA": NtA, "NtN": NtN,
        "PPS": PPS, "PPSA": PPSA, "PPSN": PPSN,
        "PECA": PECA, "PECN": PECN,
        "PTOA": PTOA, "PTON": PTON,
        "PTOA_i": PTOA_i, "PTON_j": PTON_j,
    }


def imprimir_resultados(res):
    """Imprime los resultados de una corrida en formato legible."""
    cfg = res["config"]
    print(f"\n{'=' * 64}")
    print(f"Configuración: NA={cfg['NA']}  NN={cfg['NN']}  "
          f"período={cfg['periodo']}")
    print(f"TF={cfg['TF']:.0f} min   T_final={cfg['T_final']:.1f} min")
    print(f"Pedidos: Nt={res['Nt']}  NtA={res['NtA']}  NtN={res['NtN']}")
    print(f"{'-' * 64}")
    print(f"Permanencia en sistema (minutos):")
    print(f"  PPS  = {res['PPS']:>12.2f}")
    print(f"  PPSA = {res['PPSA']:>12.2f}   (línea CA)")
    print(f"  PPSN = {res['PPSN']:>12.2f}   (línea CN)")
    print()
    print(f"Espera en cola (minutos):")
    print(f"  PECA = {res['PECA']:>12.2f}   (línea CA)")
    print(f"  PECN = {res['PECN']:>12.2f}   (línea CN)")
    print()
    print(f"Tiempo ocioso:")
    print(f"  PTOA = {res['PTOA'] * 100:>6.2f}%   (promedio línea CA)")
    for i, p in enumerate(res["PTOA_i"]):
        print(f"    PTOA[{i}] = {p * 100:.2f}%")
    print(f"  PTON = {res['PTON'] * 100:>6.2f}%   (promedio línea CN)")
    for j, p in enumerate(res["PTON_j"]):
        print(f"    PTON[{j}] = {p * 100:.2f}%")
    print(f"{'=' * 64}")


# ============================================================
# CLI
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulación de procesamiento de pedidos con priorización.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--na", type=int, default=1,
                        help="Cantidad de operarios CA (línea Alta)")
    parser.add_argument("--nn", type=int, default=1,
                        help="Cantidad de operarios CN (línea Normal)")
    parser.add_argument("--tf", type=float, default=100_000.0,
                        help="Tiempo final en minutos")
    parser.add_argument(
        "--periodo",
        choices=["ene-feb", "jun-jul", "nov-dic"],
        default="nov-dic",
        help="Período del año a simular",
    )
    parser.add_argument("--seed", type=int, default=42,
                        help="Semilla aleatoria")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    resultados = simular(
        NA=args.na,
        NN=args.nn,
        TF=args.tf,
        periodo=args.periodo,
        semilla=args.seed,
    )
    imprimir_resultados(resultados)
