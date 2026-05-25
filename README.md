# TP5 — Simulación de un Sistema Real
## Centro de Procesamiento de Pedidos de un E-commerce

Trabajo Práctico N.º 5 de la materia **Simulación**  
UTN — Facultad Regional Buenos Aires  
Ingeniería en Sistemas de Información

El proyecto modela y simula el funcionamiento de un centro de distribución
de e-commerce utilizando una metodología de simulación discreta evento-a-evento,
con el objetivo de determinar configuraciones óptimas de operarios para
distintos períodos del año.

---

# Integrantes

- Leonel Adrián Cantero
- Rocío Belén Copa
- Elías Mouesca
- Sebastián Ariel Vicente

---

# Estructura del repositorio

```text
TP5-SIMULACION/
│
├── data/
│
├── docs/
│   ├── analisis_previo.pdf
│   ├── paper.pdf
│   ├── presentacion.pdf
│   └── diagrama_flujo.md
│
├── resultados/
│   └── informe_final.pdf
│
├── src/
│   ├── analisis_y_fdps.py
│   ├── simulacion.py
│   └── evaluacion_sla.py
│
├── README.md
└── .gitignore
```

---

# Modelo resumido

- Simulación discreta evento-a-evento.
- Dos líneas de procesamiento:
  - CA (prioridad Alta)
  - CN (prioridad Normal)
- Disciplina FIFO.
- Política de prioridad no apropiativa.
- Evaluación de configuraciones mediante SLA.

---

# Contenido del proyecto

## Documentación

- **`docs/analisis_previo.pdf`**  
  Modelo conceptual, clasificación de variables, TEI y TEF.

- **`docs/diagrama_flujo.md`**  
  Diagrama de flujo del modelo y subrutinas.

- **`docs/paper.pdf`**  
  Informe académico final con metodología y desarrollo del modelo.

- **`docs/presentacion.pdf`**  
  Presentación utilizada para la exposición oral.

---

## Resultados

- **`resultados/informe_final.pdf`**  
  Resultados obtenidos, interpretación y conclusiones del estudio.

---

## Scripts

- **`src/analisis_y_fdps.py`**  
  Procesamiento del dataset y ajuste de distribuciones de probabilidad.

- **`src/simulacion.py`**  
  Motor principal de simulación evento-a-evento.

- **`src/evaluacion_sla.py`**  
  Evaluación de configuraciones y búsqueda de configuraciones óptimas.

---

## Datasets utilizados

- **`data/olist_orders_dataset.csv`**
- **`data/olist_order_items_dataset.csv`**

El modelo utiliza datos históricos del dataset público de Olist
para construir las distribuciones de arribos y tiempos de atención.

---

# Flujo de trabajo

```text
Datasets
   ↓
Análisis y ajuste de FDPs
   ↓
Motor de simulación
   ↓
Evaluación SLA
   ↓
Resultados y conclusiones
```

---

# Criterio SLA

Una configuración se considera aceptable si cumple simultáneamente:

- PPSA ≤ 3 días
- PPSN ≤ 5 días
- PTOA ≤ 35%
- PTON ≤ 35%

La configuración óptima es la de menor cantidad total de operarios
que satisface todos los criterios.

---

# Cómo ejecutar el proyecto

## Requerimientos

Python 3.10+ y las siguientes librerías:

```text
pandas
numpy
matplotlib
scipy
fitter
```

Instalación:

```bash
pip install pandas numpy matplotlib scipy fitter
```

---

## 1) Ajustar distribuciones

```bash
python src/analisis_y_fdps.py
```

Obtiene las distribuciones de probabilidad utilizadas por el modelo.

---

## 2) Ejecutar una simulación individual

```bash
python src/simulacion.py \
  --na 80 \
  --nn 160 \
  --tf 100000 \
  --periodo ene-feb \
  --seed 42
```

### Parámetros

| Flag | Descripción |
|------|-------------|
| `--na` | Operarios línea Alta |
| `--nn` | Operarios línea Normal |
| `--tf` | Tiempo final de simulación |
| `--periodo` | `ene-feb`, `jun-jul`, `nov-dic` |
| `--seed` | Semilla aleatoria |

---

## 3) Evaluar configuraciones (SLA)

```bash
python src/evaluacion_sla.py
```

Ejecuta múltiples configuraciones y determina cuáles cumplen el SLA.

---

# Configuración óptima recomendada

| Período | NA | NN | Total |
|---------|----|----|-------|
| Enero - Febrero | 80 | 160 | 240 |
| Junio - Julio | 125 | 250 | 375 |
| Noviembre - Diciembre | 240 | 480 | 720 |

Los detalles completos del análisis y la interpretación de resultados
se encuentran en `resultados/informe_final.pdf`.