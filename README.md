# TP4 — Simulación del Centro de Procesamiento de Pedidos

Este proyecto contiene el modelo de simulación evento-a-evento y el análisis de
dimensionamiento de operarios para el centro de distribución de un e-commerce
con dos niveles de prioridad de atención.

---

## Contenido del proyecto

### Documentos

- **`Análisis Previo.pdf`** — Enunciado y contexto del problema (variables exógenas/endógenas, TEI, TEF, reglas operativas).
- **`diagrama_flujo.md`** — Diagrama de flujo del modelo (Mermaid), subrutinas, convención del modelo y glosario de variables.
- **`informe_final.md`** — Informe completo con metodología, resultados, recomendación de plantel y estrategia operativa.

### Scripts

- **`analisis_y_fdps.py`** — Análisis del dataset y ajuste de las 9 distribuciones de probabilidad (FDPs).
- **`simulacion.py`** — Implementación del modelo evento-a-evento. Ejecutable por línea de comandos.
- **`evaluacion_sla.py`** — Sweep de configuraciones y evaluación contra el criterio SLA.

### Datasets utilizados

- **`olist_orders_dataset.csv`** — Tabla de órdenes con timestamps de compra, aprobación, entrega al courier y entrega al cliente.
- **`olist_order_items_dataset.csv`** — Ítems por orden, usado para calcular el monto total y clasificar prioridad (Alta / Normal).

> Nota: el dataset completo Olist contiene más tablas (clientes, sellers, productos, etc.) pero el modelo solo utiliza estas dos.

---

## Flujo de uso

```
┌─────────────────────────┐
│   Datasets Olist        │
│   - orders              │
│   - order_items         │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   analisis_y_fdps.py    │  → Imprime las 9 FDPs (IA × 3 + TEA × 3 + TEN × 3)
└────────────┬────────────┘
             │  (los parámetros ya están copiados en simulacion.py)
             ▼
┌─────────────────────────┐
│   simulacion.py         │  → Corre 1 simulación con CLI
│   (motor evento-a-      │     python simulacion.py --na 80 --nn 160 ...
│    evento)              │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   evaluacion_sla.py     │  → Sweep de configs, encuentra óptimos por período
│   (orquestador)         │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   informe_final.md      │  → Conclusiones y recomendación operativa
└─────────────────────────┘
```

---

## Cómo correr

### Requerimientos

Python 3.10+ con las siguientes librerías:

```
pandas
numpy
matplotlib
scipy
fitter
```

Instalación (en un virtualenv):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy matplotlib scipy fitter
```

### 1) Ajustar las FDPs sobre los datos

```bash
python analisis_y_fdps.py
```

Salida: por cada período (ene-feb / jun-jul / nov-dic) y prioridad (Alta / Normal),
imprime la mejor distribución ajustada y sus parámetros. Estos parámetros ya están
copiados en `simulacion.py` (constantes `FDP_IA`, `FDP_TEA`, `FDP_TEN`).

> Tiempo aproximado de ejecución: 5-10 minutos (Fitter prueba ~80 distribuciones por muestra).

### 2) Correr una simulación individual

```bash
python simulacion.py --na 80 --nn 160 --tf 88000 --periodo ene-feb --seed 42
```

Parámetros:

| Flag | Descripción | Default |
|------|-------------|---------|
| `--na` | Operarios línea Alta | 1 |
| `--nn` | Operarios línea Normal | 1 |
| `--tf` | Tiempo final (minutos) | 100000 |
| `--periodo` | `ene-feb` / `jun-jul` / `nov-dic` | `nov-dic` |
| `--seed` | Semilla aleatoria | 42 |

### 3) Evaluar el barrido de configuraciones (SLA)

```bash
python evaluacion_sla.py
```

Corre las configuraciones definidas en el script para los 3 períodos, con 3 semillas
cada una, y reporta cuáles cumplen el SLA y cuál es el óptimo por período.

> Tiempo aproximado: 30-60 minutos.

---

## Configuración óptima recomendada

| Período | Operarios Alta (NA) | Operarios Normal (NN) | Total |
|---------|---------------------|------------------------|-------|
| Enero - Febrero | 80 | 160 | 240 |
| Junio - Julio | 125 | 250 | 375 |
| Noviembre - Diciembre | 240 | 480 | 720 |

Detalles, justificación y estrategia operativa en `informe_final.md`.
