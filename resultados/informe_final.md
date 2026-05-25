# Informe Final — Dimensionamiento del Centro de Procesamiento de Pedidos

## 1. Resumen ejecutivo

Se simuló mediante un modelo evento-a-evento un sistema de procesamiento de pedidos con dos líneas (Alta y Normal) sobre datos históricos del dataset Olist (2017). El objetivo fue determinar la **cantidad mínima de operarios** para los tres períodos representativos del año (enero-febrero, junio-julio, noviembre-diciembre) que cumpla simultáneamente:

- **Promedio de Permanencia en el Sistema - Alta (PPSA)** ≤ 3 días
- **Promedio de Permanencia en el Sistema - Normal (PPSN)** ≤ 5 días
- **Porcentaje de Tiempo Ocioso - Alta (PTOA)** ≤ 35 %
- **Porcentaje de Tiempo Ocioso - Normal (PTON)** ≤ 35 %

**Recomendación operativa final:**

| Período | Operarios Alta (CA) | Operarios Normal (CN) | Total |
|---------|---------------------|------------------------|-------|
| Enero - Febrero | 80 | 160 | 240 |
| Junio - Julio | 125 | 250 | 375 |
| Noviembre - Diciembre | 240 | 480 | 720 |

La estrategia de staffing combina **plantel base permanente (junio-julio) + vacaciones rotativas en verano + refuerzo temporal en pico de fin de año**.

---

## 2. Contexto del problema

El centro de distribución de un e-commerce procesa pedidos con dos niveles de prioridad asignados según el monto:

- **Normal:** 0 ≤ valor < $100 — 63 % de las llegadas.
- **Alta:** 100 ≤ valor ≤ $400 — 37 % de las llegadas.

Existen dos líneas de procesamiento:

- **Línea Alta (CA):** atiende exclusivamente pedidos Alta.
- **Línea Normal (CN):** atiende pedidos Normal, pero si hay pedidos Alta esperando en cola, los atiende con preferencia.

La prioridad es **no apropiativa** — un pedido en atención no se interrumpe aunque llegue uno de mayor prioridad.

---

## 3. Modelo de simulación

Modelo evento-a-evento con tres tipos de eventos:

1. **Llegada** — ingresa un pedido. Se sortea su prioridad (37 % Alta / 63 % Normal).
2. **Salida Alta (de CA)** — un operario CA termina la atención.
3. **Salida Normal (de CN)** — un operario CN termina la atención (sea pedido originalmente Alta o Normal).

**Convención del modelo:** las métricas por prioridad (`PPSA`, `PPSN`, `PECA`, `PECN`) se computan **por línea de atención**, no por prioridad original. Un Alta absorbido por la línea Normal aporta a las métricas de Normal. Esto refleja el rendimiento operativo de cada línea.

El diagrama de flujo completo se encuentra en `diagrama_flujo_v2.md`. La implementación está en `simulacion.py`.

---

## 4. Distribuciones ajustadas

Se ajustaron 9 FDPs (Funciones de Densidad de Probabilidad) con la librería **Fitter** sobre datos históricos filtrados (año 2017, percentil 95 para evitar outliers):

- 3 FDPs de **Intervalo entre Arribos (IA)** — una por período.
- 3 FDPs de **Tiempo de Atención línea Alta (TEA)** — una por período.
- 3 FDPs de **Tiempo de Atención línea Normal (TEN)** — una por período.

### Definición de TA utilizada

El tiempo de atención se calcula como el procesamiento interno en el centro de distribución, excluyendo el tránsito del courier al cliente:

```
TA = order_delivered_carrier_date - order_approved_at
```

Esto representa el trabajo real del operario en el centro (~71 horas en promedio), sin contaminar las distribuciones con tiempos de logística externa.

### Criterio de selección de la FDP

Para cada combinación período/prioridad, Fitter probó ~80 distribuciones de `scipy.stats` y se eligió la de **menor Suma de Errores Cuadráticos (SSE)** entre el histograma empírico y la curva teórica. Las distribuciones resultantes son: `fatiguelife`, `exponnorm`, `johnsonsb`, `truncpareto`, `genhyperbolic` (ver `simulacion.py` para parámetros exactos).

Ajuste de FDPs: `analisis_y_fdps.py`.

---

## 5. Criterio de optimalidad (SLA)

Una configuración `(NA, NN)` se considera **aceptable** si cumple simultáneamente los cuatro criterios. El **óptimo por período** es la configuración aceptable con **menor cantidad total de operarios** (`NA + NN`).

| Criterio | Umbral | Justificación |
|----------|--------|---------------|
| PPSA ≤ 3 días | Promesa de entrega para Alta prioridad | Cliente que paga monto alto espera servicio rápido |
| PPSN ≤ 5 días | Promesa de entrega Normal | Estándar e-commerce |
| PTOA ≤ 35 % | Rentabilidad línea Alta | Operario debe estar ocupado al menos 65 % |
| PTON ≤ 35 % | Rentabilidad línea Normal | Mismo principio |

Nota: no se incluye un umbral para `PEC` (Promedio de Espera en Cola) porque queda implícitamente acotado por `PPS ≤ X días`. Una espera de cola excesiva haría que la permanencia total supere el umbral.

---

## 6. Metodología de evaluación

- **Tiempo Final (TF):** 88.000 minutos ≈ **61 días** = duración real de cada período de 2 meses. Esto asegura que cada simulación representa la operación completa del período evaluado.
- **Semillas:** 3 semillas distintas por configuración (42, 123, 456) para obtener media y desvío estándar.
- **Grid de configuraciones:** 5 configs por período cubriendo desde "claramente saturado" hasta "cómodamente estable", para identificar el mínimo aceptable.

Script de evaluación: `evaluacion_sla.py`.

---

## 7. Resultados

### Enero - Febrero (baja demanda)

| NA | NN | PPSA [d] | PPSN [d] | PTOA [%] | PTON [%] | Cumple SLA |
|----|----|---------:|---------:|---------:|---------:|------------|
| 70 | 140 | 2.12 ± 0.03 | 9.04 ± 0.93 | 27.0 ± 1.7 | 7.8 ± 1.0 | ❌ (PPSN > 5) |
| 75 | 150 | 2.10 ± 0.03 | 5.53 ± 0.25 | 21.0 ± 1.1 | 9.0 ± 0.6 | ❌ (PPSN > 5) |
| **80** | **160** | **2.11 ± 0.04** | **3.01 ± 0.68** | **19.2 ± 3.8** | **13.9 ± 6.3** | **✅ ÓPTIMO** |
| 85 | 170 | 2.09 ± 0.02 | 2.27 ± 0.06 | 18.3 ± 0.4 | 16.7 ± 1.4 | ✅ |
| 90 | 180 | 2.10 ± 0.03 | 2.20 ± 0.03 | 23.2 ± 1.8 | 26.0 ± 2.2 | ✅ |

### Junio - Julio (demanda media)

| NA | NN | PPSA [d] | PPSN [d] | PTOA [%] | PTON [%] | Cumple SLA |
|----|----|---------:|---------:|---------:|---------:|------------|
| 115 | 230 | 2.31 ± 0.01 | 8.19 ± 0.85 | 28.4 ± 3.6 | 13.0 ± 2.6 | ❌ (PPSN > 5) |
| **125** | **250** | **2.30 ± 0.04** | **4.28 ± 0.12** | **23.6 ± 2.3** | **16.0 ± 2.7** | **✅ ÓPTIMO** |
| 135 | 270 | 2.32 ± 0.06 | 2.65 ± 0.30 | 23.8 ± 3.8 | 23.0 ± 3.5 | ✅ |
| 145 | 290 | 2.30 ± 0.03 | 2.31 ± 0.02 | 22.5 ± 0.6 | 28.2 ± 0.9 | ✅ |
| 155 | 310 | 2.30 ± 0.03 | 2.31 ± 0.02 | 25.4 ± 1.2 | 33.8 ± 0.6 | ✅ |

### Noviembre - Diciembre (alta demanda)

| NA | NN | PPSA [d] | PPSN [d] | PTOA [%] | PTON [%] | Cumple SLA |
|----|----|---------:|---------:|---------:|---------:|------------|
| 220 | 440 | 2.79 ± 0.01 | 7.05 ± 0.30 | 25.5 ± 0.7 | 13.4 ± 1.3 | ❌ (PPSN > 5) |
| 230 | 460 | 2.80 ± 0.01 | 5.57 ± 0.34 | 23.7 ± 5.1 | 15.8 ± 4.4 | ❌ (PPSN > 5) |
| **240** | **480** | **2.79 ± 0.02** | **3.68 ± 0.15** | **19.5 ± 0.9** | **16.3 ± 0.7** | **✅ ÓPTIMO** |
| 250 | 500 | 2.80 ± 0.02 | 2.80 ± 0.14 | 18.3 ± 1.1 | 18.4 ± 1.4 | ✅ |
| 260 | 520 | 2.79 ± 0.02 | 2.65 ± 0.00 | 19.2 ± 1.0 | 24.6 ± 0.3 | ✅ |

---

## 8. Estrategia operativa propuesta

Mantener un plantel fijo equivalente al período pico (nov-dic, 720 operarios) implicaría tener ~70 % de ociosidad durante ene-feb. Esto **violaría el criterio de rentabilidad** (PTO > 35 %) y sería financieramente inviable.

La estrategia propuesta es **plantel base permanente + flexibilidad estacional**:

### 8.1 Plantel base permanente

Dimensionar al nivel de **junio-julio** (período de demanda media):

- **125 operarios línea Alta (CA)**
- **250 operarios línea Normal (CN)**
- **Total: 375 operarios permanentes**

### 8.2 Estrategia por período

**Enero - Febrero (vacaciones):**

- Demanda baja por estacionalidad.
- Plantel necesario: **240 operarios** (80 CA + 160 CN).
- Esto representa **64 %** del plantel base de jun-jul.
- Implica que **~36 % del personal puede tomar vacaciones simultáneamente** sin comprometer el servicio (no la mitad, como podría intuirse).
- Implementación: vacaciones rotativas escalonadas, manteniendo siempre 64 % del plantel activo.

**Junio - Julio (operación normal):**

- Plantel base completo trabajando: 125 CA + 250 CN = 375 operarios.
- Sin necesidad de personal adicional.

**Noviembre - Diciembre (pico de demanda):**

- Plantel necesario: **720 operarios** (240 CA + 480 CN).
- Refuerzo requerido sobre el plantel base: **+115 CA y +230 CN = +345 operarios** (casi duplicar el plantel base).
- Opciones para cubrir el gap:
  - **Operarios temporales** contratados por los 2 meses del pico.
  - **Horas extras** del plantel permanente (limitado por fatiga humana).
  - **Combinación recomendada:** hire 250 temporarios + repartir 95 operarios-mes equivalentes en horas extras del plantel base.

### 8.3 Cuadro síntesis

| Período | Demanda | Op. permanentes | + Vacaciones / Extras | Total efectivo |
|---------|---------|----------------:|---------------------:|---------------:|
| Ene - Feb | Baja | 375 | −135 (vacaciones rotativas, 36 %) | 240 |
| Jun - Jul | Media | 375 | 0 | 375 |
| Nov - Dic | Alta | 375 | +345 temporales / extras | 720 |

### 8.4 Ahorro estimado

Comparación de "operario-meses" anuales bajo distintos esquemas:

| Esquema | Operario-meses | Costo relativo |
|---------|---------------:|---------------:|
| Plantel fijo al pico (720 todo el año) | 8640 | 100 % |
| Plantel base + flexibilidad | 4500 base + 690 temps = **5190** | **60 %** |

La estrategia propuesta implica **~40 % de ahorro** en costo de operarios respecto a sobre-dimensionar al pico todo el año.

---

## 9. Hallazgos relevantes

### 9.1 Relación NN / NA ≈ 2 constante

En los tres óptimos, la proporción operarios Normal vs Alta se mantiene cerca de **2:1**. Esto responde a:

- La mezcla de llegadas (63 % Normal vs 37 % Alta → 1.7:1).
- Tiempos de atención similares entre líneas (TEA ≈ TEN, ~50–70 horas).
- Es una proporción estructural del problema, independiente del volumen total.

### 9.2 La estacionalidad es severa

| Período | Operarios totales | Relativo a base (jun-jul) |
|---------|------------------:|--------------------------:|
| Ene - Feb | 240 | 64 % |
| Jun - Jul | 375 | 100 % |
| Nov - Dic | 720 | 192 % |

El pico de fin de año exige **casi 3 veces** el plantel del verano. Esto justifica una política de RR.HH. flexible y no un plantel fijo.

### 9.3 La línea Normal es el cuello de botella

En todos los casos saturados, el criterio que falla es **PPSN > 5 días**, mientras que **PPSA se mantiene ≤ 3 días** gracias a la preferencia de cola. La métrica `PPSN` es el principal indicador a vigilar operativamente — la línea Normal absorbe la presión y protege a los Alta.

### 9.4 PPSA estable, PPSN sensible al staffing

Observación importante en las tablas:

- `PPSA` casi no varía con la configuración (2.10-2.82 días).
- `PPSN` varía dramáticamente (de 2.20 hasta 9 días cuando el sistema satura).

Esto confirma que **dimensionar bien CN es lo crítico** — un error en NA es mucho más recuperable que un error en NN.

### 9.5 PTOA y PTON convergen

En los óptimos, ambos rondan 15-25 %, muy por debajo del umbral de 35 %. Esto da **holgura** para absorber variabilidad operativa (ausentismo, picos no modelados). En la implementación real podría reducirse aún más el plantel si se acepta operar más cerca del límite.

---

## 10. Limitaciones y consideraciones

### 10.1 Sobre los datos

- El **Tiempo de Atención TA_interno** medido como `delivered_carrier - approved` incluye no solo trabajo del operario, sino esperas internas (lotes para courier, agrupamiento de pedidos, programación de turnos). El TA real "hands-on" del operario es presumiblemente menor.
- Los resultados son **representativos del orden de magnitud** del plantel necesario, no del número exacto.

### 10.2 Sobre la convención de métricas

Las métricas por prioridad (PPSA, PPSN, PECA, PECN) son **por línea de atención**, no por prioridad original del pedido. Un Alta absorbido por CN aporta a las métricas Normal. Documentado en `diagrama_flujo_v2.md`.

### 10.3 Sobre el criterio SLA

Los umbrales (PPSA ≤ 3, PPSN ≤ 5, PTO ≤ 35 %) son una **decisión de negocio**, no del modelo. Si se modifican, los óptimos pueden ser muy distintos:

- SLA más exigente (ej. PPSN ≤ 3) → más operarios necesarios.
- SLA más relajado (ej. PPSN ≤ 7) → puede haber configs más pequeñas que cumplan.

### 10.4 Margen de seguridad

Los óptimos representan el **mínimo justo**. Para una implementación real, conviene sumar un **5 % – 10 % adicional** para absorber:

- Ausentismo no planificado.
- Eventos puntuales (Black Friday, Cyber Monday dentro de nov-dic).
- Curva de aprendizaje de personal temporario.

### 10.5 Otras condiciones no modeladas

El modelo asume operación 24/7 continua. No contempla:

- Turnos diferenciados (mañana/tarde/noche).
- Tiempo de aprendizaje de personal temporario.
- Variaciones intra-período (efecto Black Friday, fines de semana, etc.).
- Fatiga del operario en horas extras.

Estos factores requerirían refinamientos adicionales.

---

## 11. Glosario de variables

### Entradas exógenas (datos)

- **IA** *(Intervalo entre Arribos)* — tiempo entre dos llegadas consecutivas.
- **TEA** *(Tiempo de Atención de la línea Alta)* — duración del servicio de un operario CA.
- **TEN** *(Tiempo de Atención de la línea Normal)* — duración del servicio de un operario CN.

### Variables de control

- **NA** — cantidad de operarios de la línea Alta (CA).
- **NN** — cantidad de operarios de la línea Normal (CN).
- **TF** *(Tiempo Final)* — tiempo total simulado.

### Variables de estado

- **NSa** — pedidos en la línea Alta (cola Alta + atención CA).
- **NSn** — pedidos en la línea Normal (cola Normal + atención CN, de cualquier origen).

### Métricas de salida

- **Nt** — total de pedidos llegados al sistema.
- **NtA** — pedidos atendidos por la línea Alta.
- **NtN** — pedidos atendidos por la línea Normal (incluye Altas absorbidos).
- **PPS** *(Promedio de Permanencia en el Sistema)* — tiempo promedio total que un pedido permanece en el sistema (desde llegada hasta salida).
- **PPSA** *(Promedio de Permanencia en el Sistema - línea Alta)* — promedio para pedidos atendidos por CA.
- **PPSN** *(Promedio de Permanencia en el Sistema - línea Normal)* — promedio para pedidos atendidos por CN.
- **PECA** *(Promedio de Espera en Cola - línea Alta)* — tiempo promedio en cola antes de ser atendido por CA.
- **PECN** *(Promedio de Espera en Cola - línea Normal)* — tiempo promedio en cola antes de ser atendido por CN.
- **PTOA** *(Porcentaje de Tiempo Ocioso - línea Alta, promedio)* — % de ociosidad promedio entre todos los operarios CA.
- **PTON** *(Porcentaje de Tiempo Ocioso - línea Normal, promedio)* — % de ociosidad promedio entre todos los operarios CN.
- **PTOA[i]** — % de tiempo ocioso del operario i de la línea Alta.
- **PTON[j]** — % de tiempo ocioso del operario j de la línea Normal.
