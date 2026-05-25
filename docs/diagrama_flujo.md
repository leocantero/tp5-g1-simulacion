# Diagrama de Flujo del Modelo de Simulación

Documenta la lógica evento-a-evento implementada en `simulacion.py`.

---

## ⚠️ Convención del modelo (incluida como disclaimer en el TP)

Todas las métricas por prioridad (`PPSA`, `PPSN`, `PECA`, `PECN`) se computan **por línea de atención**, no por prioridad original del pedido. Es decir:

- **PPSA / PECA** miden el desempeño de la **línea CA** (pedidos atendidos por operarios Alta).
- **PPSN / PECN** miden el desempeño de la **línea CN** (pedidos atendidos por operarios Normal, **incluyendo los pedidos Alta transferidos por preferencia de cola**).

Esto se debe a que, cuando un pedido Alta es absorbido por un operario CN, su tiempo de atención corresponde al de la línea Normal (TEN), y a partir de ese momento se contabiliza dentro de las métricas de la línea Normal. Esta convención mantiene el modelo internamente consistente y refleja el rendimiento real de cada línea de procesamiento.

---

## Convenciones del modelo

- **NSa** = pedidos Alta en cola Alta + pedidos Alta siendo atendidos por **CA**
- **NSn** = pedidos en cola Normal + pedidos siendo atendidos por **CN** (de cualquier origen)
- Si un Alta es atendido por CN, **deja de contarse en NSa y pasa a NSn**, y se le aplica **TEN**.
- Las colas (CQA, CQN) son FIFO y guardan el **tiempo de arribo** de cada pedido para poder calcular tiempo de espera al asignarse a un operario.

---

## Diagrama principal

```mermaid
flowchart TD

    CI["CI — Condiciones Iniciales
    T = 0  |  NSa = 0  |  NSn = 0
    TPSA[i] = HV  para i = 1..NA
    TPSN[j] = HV  para j = 1..NN
    ITOA[i] = 0   para i = 1..NA
    ITON[j] = 0   para j = 1..NN
    CQA = ∅  |  CQN = ∅  (colas FIFO)
    Acumuladores = 0"]

    CI --> IA_INIT[["IA"]]
    IA_INIT --> SET_TPLL["TPLL = IA"]
    SET_TPLL --> LOOP(("1"))

    LOOP --> MIN["TPSA_MIN = min TPSA[i]  →  i*
    TPSN_MIN = min TPSN[j]  →  j*"]

    MIN --> D1{"TPSA_MIN <= TPSN_MIN ?"}

    D1 -->|SÍ| D2{"TPLL <= TPSA_MIN ?"}
    D1 -->|NO| D3{"TPLL <= TPSN_MIN ?"}

    D2 -->|SÍ| LL1
    D3 -->|SÍ| LL1
    D2 -->|NO| SA1
    D3 -->|NO| SN1

    %% ─────────────────────────────
    %% LLEGADA
    %% ─────────────────────────────

    LL1["T = TPLL
    Nt = Nt + 1
    STLL = STLL + T"]
    LL1 --> IA_CALL[["IA"]]
    IA_CALL --> SET_IA["TPLL = T + IA"]
    SET_IA --> R_CALL[["R"]]
    R_CALL --> RD{"R <= 0.37 ?"}

    %% --- Rama Alta ---
    RD -->|"SÍ — Alta"| LA1{"NSa < NA ?
    (CA libre)"}

    LA1 -->|"SÍ — CA libre"| LA2["NSa = NSa + 1"]
    LA2 --> TEA_CA[["TEA"]]
    TEA_CA --> LA3["Buscar i : TPSA[i] = HV
    TPSA[i] = T + TEA
    NtA = NtA + 1
    STLLA = STLLA + T
    STECA = STECA + 0
    STAA = STAA + TEA
    STOA[i] = STOA[i] + T - ITOA[i]"]

    LA1 -->|NO| LA4{"NSn < NN ?
    (CN libre, ayuda Alta)"}

    LA4 -->|"SÍ — CN libre"| LA5["NSn = NSn + 1
    (Alta → contado como Normal)"]
    LA5 --> TEN_CN_A[["TEN"]]
    TEN_CN_A --> LA6["Buscar j : TPSN[j] = HV
    TPSN[j] = T + TEN
    NtN = NtN + 1
    STLLN = STLLN + T
    STECN = STECN + 0
    STNN = STNN + TEN
    STON[j] = STON[j] + T - ITON[j]"]

    LA4 -->|"NO — cola Alta"| LA7["NSa = NSa + 1
    Push T a CQA"]

    %% --- Rama Normal ---
    RD -->|"NO — Normal"| LN1{"NSn < NN ?
    (CN libre)"}

    LN1 -->|"SÍ — CN libre"| LN2["NSn = NSn + 1"]
    LN2 --> TEN_CN_N[["TEN"]]
    TEN_CN_N --> LN3["Buscar j : TPSN[j] = HV
    TPSN[j] = T + TEN
    NtN = NtN + 1
    STLLN = STLLN + T
    STECN = STECN + 0
    STNN = STNN + TEN
    STON[j] = STON[j] + T - ITON[j]"]

    LN1 -->|"NO — cola Normal"| LN4["NSn = NSn + 1
    Push T a CQN"]

    %% ─────────────────────────────
    %% SALIDA ALTA (CA i*)
    %% ─────────────────────────────

    SA1["T = TPSA_MIN
    NSa = NSa - 1
    STSA = STSA + T"]
    SA1 --> SA2{"NSa >= NA ?
    (más Alta en cola)"}
    SA2 -->|"SÍ — toma siguiente"| TEA_SA[["TEA"]]
    TEA_SA --> SA3["Tarr = pop CQA  (FIFO)
    TPSA[i*] = T + TEA
    NtA = NtA + 1
    STLLA = STLLA + Tarr
    STECA = STECA + (T - Tarr)
    STAA = STAA + TEA"]
    SA2 -->|"NO — CA i* ocioso"| SA4["TPSA[i*] = HV
    ITOA[i*] = T"]

    %% ─────────────────────────────
    %% SALIDA NORMAL (CN j*)
    %% ─────────────────────────────

    SN1["T = TPSN_MIN
    NSn = NSn - 1
    STSN = STSN + T"]
    SN1 --> SN2{"NSa > NA ?
    (cola Alta)"}

    SN2 -->|"SÍ — transferir Alta a CN"| SN3["NSa = NSa - 1
    NSn = NSn + 1
    (transferencia: Alta → Normal)"]
    SN3 --> TEN_SN_A[["TEN"]]
    TEN_SN_A --> SN4["Tarr = pop CQA  (FIFO)
    TPSN[j*] = T + TEN
    NtN = NtN + 1
    STLLN = STLLN + Tarr
    STECN = STECN + (T - Tarr)
    STNN = STNN + TEN"]

    SN2 -->|NO| SN5{"NSn >= NN ?
    (cola Normal)"}
    SN5 -->|"SÍ — toma siguiente Normal"| TEN_SN_N[["TEN"]]
    TEN_SN_N --> SN6["Tarr = pop CQN  (FIFO)
    TPSN[j*] = T + TEN
    NtN = NtN + 1
    STLLN = STLLN + Tarr
    STECN = STECN + (T - Tarr)
    STNN = STNN + TEN"]
    SN5 -->|"NO — CN j* ocioso"| SN7["TPSN[j*] = HV
    ITON[j*] = T"]

    %% ─────────────────────────────
    %% CONTROL T <= TF
    %% ─────────────────────────────

    LA3 --> TF
    LA6 --> TF
    LA7 --> TF
    LN3 --> TF
    LN4 --> TF
    SA3 --> TF
    SA4 --> TF
    SN4 --> TF
    SN6 --> TF
    SN7 --> TF

    TF{"T <= TF ?"}
    TF -->|SÍ| LOOP

    %% ─────────────────────────────
    %% VACIAMIENTO
    %% ─────────────────────────────

    TF -->|NO| VAC1{"NSa = 0
    AND NSn = 0 ?"}
    VAC1 -->|"SÍ — sistema vacío"| RES_CALL[["Resultados"]]
    RES_CALL --> FIN([FIN])
    VAC1 -->|"NO — aún hay pedidos"| VAC2["TPLL = HV"]
    VAC2 --> LOOP
```

---

## Subrutina: R — Número aleatorio uniforme

```mermaid
flowchart TD
    R_INI([Inicio: R]) --> R1["Generar U ~ Uniforme(0, 1)"]
    R1 --> R_FIN([Retorna R])
```

## Subrutina: IA — Intervalo entre arribos

```mermaid
flowchart TD
    IA_INI([Inicio: IA]) --> IA_R[["R"]]
    IA_R --> IA1["Aplicar transformada inversa F⁻¹_IA(R)
    según período: Q1 / Q2 / Q4"]
    IA1 --> IA_FIN([Retorna IA])
```

## Subrutina: TEA — Tiempo de atención CA (línea Alta)

```mermaid
flowchart TD
    TEA_INI([Inicio: TEA]) --> TEA_R[["R"]]
    TEA_R --> TEA1["Aplicar transformada inversa F⁻¹_TEA(R)
    según período: Q1 / Q2 / Q4"]
    TEA1 --> TEA_FIN([Retorna TEA])
```

## Subrutina: TEN — Tiempo de atención CN (línea Normal)

> Se usa **siempre que CN atienda un pedido**, sea de origen Alta o Normal.

```mermaid
flowchart TD
    TEN_INI([Inicio: TEN]) --> TEN_R[["R"]]
    TEN_R --> TEN1["Aplicar transformada inversa F⁻¹_TEN(R)
    según período: Q1 / Q2 / Q4"]
    TEN1 --> TEN_FIN([Retorna TEN])
```

---

## Subrutina: Resultados

```mermaid
flowchart TD
    RES_INI([Inicio: Resultados]) --> RES1["Permanencia en sistema:
    PPSA = (STSA - STLLA) / NtA
    PPSN = (STSN - STLLN) / NtN
    PPS  = (STSA + STSN - STLL) / Nt"]

    RES1 --> RES2["Espera en cola:
    PECA = STECA / NtA
    PECN = STECN / NtN"]

    RES2 --> RES3["Tiempo ocioso por operario:
    PTOA[i] = STOA[i] / TF
    PTON[j] = STON[j] / TF"]

    RES3 --> RES4["Tiempo ocioso promedio por línea:
    PTOA = (1/NA) · Σ STOA[i] / TF
    PTON = (1/NN) · Σ STON[j] / TF"]

    RES4 --> RES_FIN([Retorna Resultados])
```

---

## Glosario de variables

### Entradas exógenas

| Variable | Tipo | Descripción |
|----------|------|-------------|
| **IA** | Dato | Intervalo entre arribos |
| **TEA** | Dato | Tiempo de atención de un operario **CA** |
| **TEN** | Dato | Tiempo de atención de un operario **CN** (sea pedido Alta o Normal) |
| **R** | Dato | Número aleatorio uniforme U(0,1) |

### Variables de control

| Variable | Descripción |
|----------|-------------|
| **NA** | Cantidad de operarios CA |
| **NN** | Cantidad de operarios CN |
| **TF** | Tiempo final de la simulación |

### Estado

| Variable | Descripción |
|----------|-------------|
| **T** | Reloj de la simulación |
| **NSa** | Pedidos Alta en cola Alta + atendidos en CA |
| **NSn** | Pedidos en cola Normal + atendidos en CN (cualquier origen) |
| **CQA** | Cola FIFO de tiempos de arribo de pedidos Alta esperando |
| **CQN** | Cola FIFO de tiempos de arribo de pedidos Normal esperando |

### TEF

| Variable | Descripción |
|----------|-------------|
| **TPLL** | Tiempo de la próxima llegada |
| **TPSA[i]** | Próxima salida del CA i |
| **TPSN[j]** | Próxima salida del CN j |
| **TPSA_MIN / i\*** | Mínimo de TPSA[i] e índice ganador |
| **TPSN_MIN / j\*** | Mínimo de TPSN[j] e índice ganador |
| **HV** | Valor muy alto (∞) — servidor ocioso |

### Acumuladores

| Variable | Descripción |
|----------|-------------|
| **Nt** | Total de pedidos llegados al sistema |
| **NtA** | Pedidos atendidos por la **línea CA** (incrementa al asignar a un CA) |
| **NtN** | Pedidos atendidos por la **línea CN** (incrementa al asignar a un CN, incluye Altas transferidos) |
| **STLL** | Suma de tiempos de llegada (todos los pedidos) |
| **STLLA** | Suma de tiempos de llegada de pedidos atendidos por CA |
| **STLLN** | Suma de tiempos de llegada de pedidos atendidos por CN |
| **STSA / STSN** | Suma de tiempos de salida en línea CA / CN |
| **STAA / STNN** | Suma de tiempos de atención CA / CN |
| **STECA / STECN** | Suma de tiempos de espera en cola para pedidos servidos por CA / CN |
| **STOA[i] / STON[j]** | Suma de tiempo ocioso por operario |
| **ITOA[i] / ITON[j]** | Inicio del último tramo ocioso por operario |

> Nota: por construcción, `Nt = NtA + NtN` y `STLL = STLLA + STLLN` al finalizar la simulación.

### Resultados

| Variable | Descripción |
|----------|-------------|
| **PPSA / PPSN / PPS** | Promedio de permanencia en el sistema (línea CA / línea CN / total) |
| **PECA / PECN** | Promedio de espera en cola (línea CA / línea CN) |
| **PTOA[i] / PTON[j]** | % de tiempo ocioso por operario |
| **PTOA / PTON** | % de tiempo ocioso promedio por línea |

