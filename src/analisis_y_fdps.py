# -*- coding: utf-8 -*-
"""
Análisis de datos y ajuste de las distribuciones de probabilidad (FDPs)
para alimentar la simulación.

A partir del dataset Olist, calcula:
  - El intervalo entre arribos de pedidos (IA), por período del año.
  - El tiempo de atención interno del centro de distribución (TA), por período
    y por prioridad (Alta / Normal).

Sobre estos datos ajusta 9 FDPs con la librería Fitter, listas para enchufar
en simulacion.py.

Definición de TA usada:
  TA = order_delivered_carrier_date - order_approved_at
  (procesamiento interno en el centro de distribución, sin incluir el tránsito
   del courier).

Pasos:
  1 - Carga de datos
  2 - Preparación de datos (totales por orden, merge, filtro delivered)
  3 - Filtro 2017 + percentiles
  4 - Filtro p95 order_total
  5 - Cálculo y filtro de IA (intervalo entre arribos)
  6 - Muestras temporales por período
  7 - Cálculo y filtro de TA (tiempo de atención interno)
  8 - Segmentación por período y prioridad
  9 - Ajuste de las 6 FDPs de TA con Fitter
"""

import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from fitter import Fitter

# =========================
# Control de pasos
# =========================
PASO_MAXIMO = 9  # ahora llegamos hasta el paso 9 (FDPs)


def check_step(paso: int, nombre: str) -> None:
    print(f"\n--- Paso {paso} completado: {nombre} ---")
    if paso >= PASO_MAXIMO:
        print(f"\nSimulación detenida en el paso {paso} ({nombre}).")
        sys.exit(0)


# =========================
# Paso 1: Carga de datos
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ordenes = pd.read_csv(os.path.join(BASE_DIR, "olist_orders_dataset.csv"))
items = pd.read_csv(os.path.join(BASE_DIR, "olist_order_items_dataset.csv"))

print(ordenes.head(5))
print(items.head())

check_step(1, "Carga de datos")

# =========================
# Paso 2: Preparación de datos
# =========================
totales_orden = (
    items
    .groupby("order_id")["price"]
    .sum()
    .reset_index()
    .rename(columns={"price": "order_total"})
)

ordenes = ordenes.merge(totales_orden, on="order_id", how="inner")
ordenes = ordenes[ordenes["order_status"] == "delivered"]
ordenes["order_purchase_timestamp"] = pd.to_datetime(ordenes["order_purchase_timestamp"])
ordenes["order_purchase_date"] = pd.to_datetime(ordenes["order_purchase_timestamp"]).dt.normalize()

check_step(2, "Preparación de datos")

# =========================
# Paso 3: Filtro 2017 + percentiles
# =========================
ordenes_2017 = ordenes[ordenes["order_purchase_date"].dt.year == 2017]

print("Shape dataset 2017:", ordenes_2017.shape)
percentiles = ordenes_2017["order_total"].quantile([0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99])
print(percentiles)

check_step(3, "Filtro 2017 + percentiles")

# =========================
# Paso 4: Filtro p95 order_total
# =========================
p95 = ordenes_2017["order_total"].quantile(0.95)
ordenes_2017_filtrado = ordenes_2017[ordenes_2017["order_total"] <= p95]
print("Shape dataset filtrado:", ordenes_2017_filtrado.shape)

check_step(4, "Filtro p95 order_total")

# =========================
# Paso 5: Cálculo y filtro de IA
# =========================
columnas_fecha = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date"
]

for col in columnas_fecha:
    ordenes_2017_filtrado[col] = pd.to_datetime(ordenes_2017_filtrado[col], errors="coerce")

ordenes_2017_filtrado = (
    ordenes_2017_filtrado
    .sort_values("order_purchase_timestamp")
    .reset_index(drop=True)
)

ordenes_2017_filtrado["IA_min"] = (
    ordenes_2017_filtrado["order_purchase_timestamp"]
    .diff()
    .dt.total_seconds() / 60
)

umbral_ia = ordenes_2017_filtrado["IA_min"].quantile(0.95)
ordenes_ia = ordenes_2017_filtrado[ordenes_2017_filtrado["IA_min"] <= umbral_ia]

check_step(5, "Cálculo y filtro de IA")

# =========================
# Paso 6: Muestras temporales (IA)
# =========================
muestra_q1 = ordenes_ia[ordenes_ia["order_purchase_timestamp"].dt.month.isin([1, 2])]
muestra_q2 = ordenes_ia[ordenes_ia["order_purchase_timestamp"].dt.month.isin([6, 7])]
muestra_q4 = ordenes_ia[ordenes_ia["order_purchase_timestamp"].dt.month.isin([11, 12])]

print("Enero-Febrero:", muestra_q1.shape)
print("Junio-Julio:", muestra_q2.shape)
print("Noviembre-Diciembre:", muestra_q4.shape)

check_step(6, "Muestras temporales IA")

# =========================
# Paso 7: Cálculo y filtro de TA (tiempo de atención interno)
# =========================
# Definimos el tiempo de atención como el procesamiento interno en el centro de
# distribución, excluyendo el tránsito del courier al cliente:
#
#   TA_interno = order_delivered_carrier_date - order_approved_at
#
# Esto representa el trabajo real del operario en el centro, sin contaminar
# las distribuciones con tiempos de logística externa.

ordenes_ia["TA_horas"] = (
    ordenes_ia["order_delivered_carrier_date"] - ordenes_ia["order_approved_at"]
).dt.total_seconds() / 3600

ordenes_ia.loc[ordenes_ia["TA_horas"] < 0, "TA_horas"] = np.nan

print("\nDistribución de TA_INTERNO (horas):")
print(ordenes_ia["TA_horas"].describe().round(2))

p95_ta = ordenes_ia["TA_horas"].quantile(0.95)
print(f"\nUmbral p95 TA_interno: {p95_ta:.2f} horas")

ordenes_ta_filtrado = ordenes_ia[ordenes_ia["TA_horas"] <= p95_ta].copy()
print("Shape dataset TA filtrado:", ordenes_ta_filtrado.shape)

check_step(7, "Cálculo y filtro TA_interno")

# =========================
# Paso 8: Segmentación por período y prioridad
# =========================
muestra_q1 = ordenes_ta_filtrado[ordenes_ta_filtrado["order_purchase_timestamp"].dt.month.isin([1, 2])]
muestra_q2 = ordenes_ta_filtrado[ordenes_ta_filtrado["order_purchase_timestamp"].dt.month.isin([6, 7])]
muestra_q4 = ordenes_ta_filtrado[ordenes_ta_filtrado["order_purchase_timestamp"].dt.month.isin([11, 12])]

muestra_q1_normal = muestra_q1[muestra_q1["order_total"] < 100]
muestra_q1_alta   = muestra_q1[muestra_q1["order_total"] >= 100]

muestra_q2_normal = muestra_q2[muestra_q2["order_total"] < 100]
muestra_q2_alta   = muestra_q2[muestra_q2["order_total"] >= 100]

muestra_q4_normal = muestra_q4[muestra_q4["order_total"] < 100]
muestra_q4_alta   = muestra_q4[muestra_q4["order_total"] >= 100]

print("Enero-Febrero   | Normal:", muestra_q1_normal.shape, "| Alta:", muestra_q1_alta.shape)
print("Junio-Julio     | Normal:", muestra_q2_normal.shape, "| Alta:", muestra_q2_alta.shape)
print("Noviembre-Dic   | Normal:", muestra_q4_normal.shape, "| Alta:", muestra_q4_alta.shape)

check_step(8, "Segmentación por período y prioridad")

# =========================
# Paso 9: Ajuste de FDPs TA con Fitter
# =========================
# Ajustamos las 6 FDPs (3 períodos × 2 prioridades) sobre TA_INTERNO.
# Las FDPs de IA no se vuelven a ajustar — los datos de arribos no cambiaron.

print("\n" + "=" * 70)
print("AJUSTE DE FDPs (TA_INTERNO)")
print("=" * 70)
print("Esto puede tardar varios minutos...\n")


def ajustar_y_reportar(nombre, datos):
    """Ajusta Fitter sobre una muestra y reporta la mejor distribución."""
    print(f"  → Ajustando: {nombre}  (n={len(datos)})")
    f = Fitter(datos.dropna().values)
    f.fit()
    mejor = f.get_best(method="sumsquare_error")
    nombre_dist = list(mejor.keys())[0]
    params = mejor[nombre_dist]
    print(f"     mejor: {nombre_dist} → {params}")
    return nombre_dist, params


resultados_fdp = {}

resultados_fdp["TEA_ene-feb"] = ajustar_y_reportar("TEA ene-feb (Alta)",   muestra_q1_alta["TA_horas"])
resultados_fdp["TEN_ene-feb"] = ajustar_y_reportar("TEN ene-feb (Normal)", muestra_q1_normal["TA_horas"])
resultados_fdp["TEA_jun-jul"] = ajustar_y_reportar("TEA jun-jul (Alta)",   muestra_q2_alta["TA_horas"])
resultados_fdp["TEN_jun-jul"] = ajustar_y_reportar("TEN jun-jul (Normal)", muestra_q2_normal["TA_horas"])
resultados_fdp["TEA_nov-dic"] = ajustar_y_reportar("TEA nov-dic (Alta)",   muestra_q4_alta["TA_horas"])
resultados_fdp["TEN_nov-dic"] = ajustar_y_reportar("TEN nov-dic (Normal)", muestra_q4_normal["TA_horas"])


# =========================
# Salida formateada para simulacion.py
# =========================
print("\n\n" + "=" * 70)
print("RESULTADOS LISTOS PARA SIMULACION.PY")
print("=" * 70)

print("\nFDP_TEA = {")
for periodo in ["ene-feb", "jun-jul", "nov-dic"]:
    dist, params = resultados_fdp[f"TEA_{periodo}"]
    params_fmt = ", ".join(f'"{k}": {v}' for k, v in params.items())
    print(f'    "{periodo}": (stats.{dist}, {{ {params_fmt} }}),')
print("}")

print("\nFDP_TEN = {")
for periodo in ["ene-feb", "jun-jul", "nov-dic"]:
    dist, params = resultados_fdp[f"TEN_{periodo}"]
    params_fmt = ", ".join(f'"{k}": {v}' for k, v in params.items())
    print(f'    "{periodo}": (stats.{dist}, {{ {params_fmt} }}),')
print("}")

print()
check_step(9, "Ajuste de FDPs con Fitter")
