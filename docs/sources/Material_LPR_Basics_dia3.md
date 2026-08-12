# ADMINISTRACIÓN DE STOCK
*Star Cooperation — Material LPR Basics, día 3*

## Índice
1. Básicos — pág. 3
2. KPI's — pág. 7
3. Calculación de Stock — pág. 19
4. Clasificación de Repuestos — pág. 25

---

## 1. Manejo de Stock — Básicos

### Las tareas principales

**① Planificación de Stock**
- Correcta pieza
- Correcta cantidad
- Correctas condiciones
- Correcto lugar
- Correcto precio
- Correcta atención

**② Manejo de Pedido**
- Controlling (Cuando – Que – Donde – Cuantas)

**③ Manejo de Almacén**
- Administración
- Mantenimiento
- Principios: organizado, limpio, transparente

### El conflicto del objetivo

Existe una tensión permanente entre dos extremos:

| Extremo | Riesgo | Problemas resultantes |
|---|---|---|
| **Disponibilidad** (mucho stock) | Stock Excesivo | Más capital necesario · Capital excesivo / gastos de compromiso · Creación de obsoleto |
| **Capital** (poco stock) | Cobertura Corta | Disponibilidad baja · Ventas perdidas · Soporte deficiente de taller · Competencia baja |

> El gráfico muestra dos curvas (Administración y Capitalización) que se cruzan; su suma da el "Costo Total", que tiene un punto mínimo = **Costo Balanceado**, el punto óptimo entre disponibilidad y capital inmovilizado.

### Ejemplo financiero

**Inventory Holding Cost (Costos de Almacenamiento)** — estándar industrial: **>20% anual**, compuesto por:
- Pérdida de valor de piezas dañadas y perdidas
- Seguro
- Espacio de almacenamiento
- Empleados
- Gastos de cobertura corta
- Gastos de capital

**Ejemplo comparativo:**

| | Localidad A | Localidad B |
|---|---|---|
| Stock con movimiento | 500,000 USD | 500,000 USD |
| Obsolescencia | 250,000 USD | 500,000 USD |
| **Stock total** | **750,000 USD** | **1,000,000 USD** |
| Gasto anual (20%) | 150,000 USD | 200,000 USD |
| Otros beneficios (50%) | 125,000 USD (liquidez +250,000 USD) | — |
| **Variación** | **-175,000 USD** | **200,000 USD** |

---

## 2. Key Performance Indicator (KPI)

### CAPITAL (1) — Stock Total
El costo total (APP*/DDP**) de toda mercancía disponible.

\* APP: Average Purchase Price / precio promedio de compra
\*\* DDP: Delivery Duty Paid / entregado al almacén final

| # | Descripción | Precio ($) | Stock Actual -1 | Stock Actual ($) | Stock Prom.-12 ($) | Ventas -12 -1 | Ingresos Año -12 ($) | Última Venta |
|---|---|---|---|---|---|---|---|---|
| 1 | Tire | 80 | 4 | 320 | 300 | 10 | 800 | 05/05/2018 |
| 2 | Brake Pads | 70 | 5 | 350 | 450 | 20 | 1,400 | 21/07/2018 |
| 3 | Filter | 10 | 10 | 100 | 130 | 100 | 1,000 | 30/07/2018 |
| 4 | Liquid | 5 | 15 | 75 | 50 | 200 | 1,000 | 30/07/2018 |
| 5 | Pump | 150 | 2 | 300 | 150 | 1 | 150 | 17/03/2018 |
| 6 | Screw | 5 | 50 | 250 | 80 | 150 | 750 | 14/04/2018 |
| 7 | Fender | 200 | 1 | 200 | 100 | 1 | 200 | 08/12/2017 |
| 8 | Clip | 1 | 30 | 30 | 40 | 180 | 180 | 24/07/2018 |
| 9 | Bulb | 5 | 5 | 25 | 30 | 25 | 125 | 07/03/2018 |
| 10 | Module | 500 | 1 | 500 | 500 | 0 | 0 | 27/02/2016 |
| **Total** | | | | **2,150** | 1,830 | | 5,605 | |

### CAPITAL (2) — Rotación de Stock
Indica cuántas veces un stock (promedio) se vende dentro de un periodo de 12 meses.

**Fórmula:** Rotación = Ingresos Año-12 / Stock Promedio-12 → **5,605 / 1,830 = 3.1**

| # | Descripción | Stock Turn Ratio (x) |
|---|---|---|
| 1 | Tire | 2.7 |
| 2 | Brake Pads | 3.1 |
| 3 | Filter | 7.7 |
| 4 | Liquid | 20.0 |
| 5 | Pump | 1.0 |
| 6 | Screw | 9.4 |
| 7 | Fender | 2.0 |
| 8 | Clip | 4.5 |
| 9 | Bulb | 4.2 |
| 10 | Module | --- |
| **Promedio total** | | **3.1** |

### CAPITAL (3) — Cobertura
Promedio de tiempo que la mercancía está disponible hasta ser vendida por completo.

**Fórmula:** Cobertura (días) = 365 / Stock Turn Ratio → **365 / 3.1 = 119 días**

| # | Descripción | Stock Turn Ratio (x) | Coverage Supply (días) |
|---|---|---|---|
| 1 | Tire | 2.7 | 137 |
| 2 | Brake Pads | 3.1 | 117 |
| 3 | Filter | 7.7 | 47 |
| 4 | Liquid | 20.0 | 18 |
| 5 | Pump | 1.0 | 365 |
| 6 | Screw | 9.4 | 39 |
| 7 | Fender | 2.0 | 183 |
| 8 | Clip | 4.5 | 81 |
| 9 | Bulb | 4.2 | 88 |
| 10 | Module | --- | --- |
| **Total** | | **3.1** | **119** |

### CAPITAL (4) — Stock Obsoleto
Obsolescencia = mercancía sin movimientos/ventas por un periodo definido (**>12 meses**).

Ejemplo en la tabla: pieza #10 "Module" — Stock actual 500, Ventas-12 = 0 → clasificado como obsoleto.

### ESPECIAL
| Tipo | Definición | Nota |
|---|---|---|
| **Stock Nuevo** | Mercancía recibida dentro de un periodo definido por primera vez | ⚠ Sin historial disponible |
| **Stock Especial** | Mercancía con características especiales (campaña, reemplazos, codificados, etc.) | ⚠ Atención permanente |
| **Stock Inactivo** | Mercancía registrada en IMS/DMS sin disponibilidad física ni movimiento por un periodo definido | ⚠ No compra de stock |

### LOGÍSTICA (1) — Stock de Seguridad
Cantidad de mercancía adicional a la demanda para cubrir picos de venta y retrasos de pedidos.
Ejemplo: periodo de seguridad = **1 mes**.

| # | Descripción | Ventas Proyectadas (3 meses) | Security Stock Period (1 mes) |
|---|---|---|---|
| 1 | Tire | 3 | 1 |
| 2 | Brake Pads | 5 | 2 |
| 3 | Filter | 25 | 8 |
| 4 | Liquid | 50 | 17 |
| 5 | Pump | 1 | 0 |
| 6 | Screw | 38 | 13 |
| 7 | Fender | 1 | 0 |
| 8 | Clip | 45 | 15 |
| 9 | Bulb | 7 | 2 |
| 10 | Module | 0 | 0 |

### LOGÍSTICA (2) — Periodo de Stock
Cantidad de mercancía calculada para cubrir la demanda del mercado por un periodo sin reposiciones. **No incluye** el stock de seguridad.
Ejemplo: **3 meses**.

### LOGÍSTICA (3) — Stock Máximo
= Periodo de Stock + Stock de Seguridad.
Ejemplo: 3 meses + 1 mes = **120 días** (cálculo lineal, redondeado hacia arriba o normal según convención).

| # | Descripción | Demanda Proy. (3m) | Stock Seguridad (1m) | Stock Máximo |
|---|---|---|---|---|
| 1 | Tire | 3 | 1 | 4 |
| 2 | Brake Pads | 5 | 2 | 7 |
| 3 | Filter | 25 | 8 | 33 |
| 4 | Liquid | 50 | 17 | 67 |
| 5 | Pump | 1 | 0 | 1 |
| 6 | Screw | 38 | 13 | 51 |
| 7 | Fender | 1 | 0 | 1 |
| 8 | Clip | 45 | 15 | 60 |
| 9 | Bulb | 7 | 2 | 9 |
| 10 | Module | 0 | 0 | 0 |

### LOGÍSTICA / CAPITAL (4) — Stock Excesivo
Mercancía disponible que excede la cantidad calculada relacionada a la demanda proyectada.

**Fórmula:** Excess Stock = Stock Actual − (Demanda Proyectada + Stock Seguridad)

Ejemplo Tire: 5 − (3 + 1) = **1 unidad de exceso** → 1 × $80 = **$80**

| # | Descripción | Stock Actual | Excess Stock (unid.) | Excess Stock ($) |
|---|---|---|---|---|
| 1 | Tire | 5 | 1 | 80 |
| 2 | Brake Pads | 5 | 0 | 0 |
| 3 | Filter | 10 | 0 | 0 |
| 4 | Liquid | 15 | 0 | 0 |
| 5 | Pump | 2 | 1 | 150 |
| 6 | Screw | 50 | 0 | 0 |
| 7 | Fender | 1 | 0 | 0 |
| 8 | Clip | 30 | 0 | 0 |
| 9 | Bulb | 5 | 0 | 0 |
| 10 | Module | 1 | 1 | 500 |
| **Total** | | 2,230 (vs prom. 1,830) | | **730** |

### RESUMEN LOGÍSTICA — cómo se compone el Punto de Pedido

```
Tiempo de Pedido      = periodo entre colocar un pedido y recibirlo en almacén final
Periodo de Stock      = periodo operativo sin reposición (entre 2 llegadas de pedidos)
Stock de Seguridad    = periodo adicional para cubrir picos de venta y retrasos

Stock Máximo (Planning Target) = Periodo de Stock + Stock de Seguridad
Punto de Pedido                = Planning Target + Tiempo de Pedido
```

### Gráfico Logístico (descripción)
El gráfico muestra el nivel de stock disponible en el eje Y y el tiempo en el eje X, con líneas horizontales de referencia (de abajo hacia arriba): **Stock de Seguridad → Punto de Pedido → Stock Máximo → Planning Target**. La curva de stock baja por consumo hasta tocar el "Punto de Pedido", momento en el que se activa un nuevo pedido (proceso de "Stocking"); tras el "Tiempo de Pedido" el stock sube de nuevo hasta el "Stock Máximo", repitiendo el ciclo.

---

## 3. Cálculo de Stock

### Cálculo de Stock (1.1) — Planning Target
**Fórmula:** (Ventas mensuales / 30 días) × días del periodo

Ejemplo — Ventas mensuales: 20 unidades

| Componente | Días | Cálculo | Resultado |
|---|---|---|---|
| Tiempo de Pedido | 10 | 20/30 × 10 | ≈ 7 |
| Periodo de Stock | 30 | 20/30 × 30 | 20 |
| Stock de Seguridad | 15 | 20/30 × 15 | 10 |
| **Planning Target** | **55** | | **37** |

### Cálculo de Stock (1.2) — Cantidad de Pedido
**Fórmula:** Cantidad de Pedido = Planning Target − Stock Disponible − Stock en Tránsito

Ejemplo: Planning Target 37 − Stock disponible 15 − Stock en tránsito 10 = **Cantidad de Pedido = 12**

### Cálculo de Stock (2.1) — Planning Target (segundo ejemplo)
Ventas mensuales: 12 unidades

| Componente | Días | Cálculo | Resultado |
|---|---|---|---|
| Tiempo de Pedido | 11 | 12/30 × 11 | 4 |
| Periodo de Stock | 44 | 12/30 × 44 | 18 |
| Stock de Seguridad | 22 | 12/30 × 22 | 9 |
| **Planning Target** | **77** | | **31** |

### Cálculo de Stock (2.2) — Cantidad de Pedido (segundo ejemplo)
Planning Target 31 − Stock disponible 9 − Stock en tránsito 20 = **Cantidad de Pedido = 2**

### Ejercicio de cálculo (pág. 24)
Cuatro casos con datos de Tiempo de Pedido, Periodo de Stock, Stock de Seguridad, Stock Actual, Stock en Tránsito, y ventas mensuales de los últimos 6 meses (M-6 a M-1). Se pide calcular: Periodo de Stock, Stock de Seguridad, Tiempo de Pedido, Stock Máximo, Planning Target, Punto de Pedido, Cantidad de Pedido (Total), Cobertura Corta, Pedido de Stock, Pedido de Courier.

| Caso | Tiempo Pedido (d) | Periodo Stock (d) | Stock Seguridad (d) | Stock Actual | Stock Tránsito | Ventas M-6..M-1 |
|---|---|---|---|---|---|---|
| Azul | 25 | 60 | 15 | 1 | 0 | 0,1,2,0,1,1 |
| Rojo | 35 | 45 | 15 | 7 | 20 | 12,17,23,26,28,23 |
| Amarillo | 7 | 30 | 20 | 0 | 0 | 3,4,2,6,6,2 |
| Verde | 90 | 60 | 30 | 3 | 5 | 4,4,2,2,5,4 |

---

## 4. Clasificación de Repuestos

### El ciclo de vida de un repuesto
Curva de campana (cantidad de ventas vs. tiempo) con las siguientes fases, en orden:
1. **Pieza entra a IMS/DMS**
2. **Sección Nueva** (hasta "Fin del periodo nuevo")
3. **Sección Regular** (incluye el "Consumo más alto", el pico de la curva)
4. **Sección Pre-Obsoleto** (empieza el "Periodo de pre-obsoleto")
5. **Sección Obsoleto** (empieza el "Periodo inactivo")

Se marca una franja de "Non stocking" en la base del gráfico, y dos etiquetas conceptuales: "Disponibilidad!" en la fase temprana/regular, y "Prevención de Obsolescencia!" hacia el final de la fase regular.

### Variantes de los ciclos de vida
Seis patrones distintos de curva de ventas en el tiempo:
- **Ciclo Regular**: curva de campana suave y simétrica
- **Ciclo de Pre-Obsolescencia extendida**: campana con una cola larga y ondulada hacia la derecha
- **Ciclo Variable**: múltiples picos irregulares seguidos
- **Ventas Individuales**: pocas ventas puntuales espaciadas en el tiempo
- **Ciclo Temporal**: dos picos de campana separados (estacionalidad)
- **Venta Única**: una sola venta puntual

### La base de la clasificación
Combina dos ejes:
- **Clasificación de cantidad** (eje vertical, Ventas-Picks/Periodo): de "Actividad Baja" a "Actividad Alta"
- **Clasificación de ciclo** (eje horizontal, Ciclo de Vida/tiempo): Pieza entra → Fin del periodo nuevo (6 meses) → Consumo más alto → Periodo de pre-obsoleto → Periodo inactivo (<12 meses) → Periodo de obsolescencia (>12 meses, >24 meses)

### Estructura de las clasificaciones (código de letras)
Sobre la misma curva de campana se superponen las categorías:
- **Stock Nuevo** (0–6 meses): códigos NX, NY, NZ
- **Stock Regular**: códigos S1 a S8 (de mayor a menor movimiento, ubicados de arriba/pico hacia abajo/cola)
- **Periodo de Pre-Obsoleto** (>12 meses): código OP
- **Periodo de Obsolescencia / Chatarra** (>24 meses): código OR

### Tabla completa de clasificación

**S — STOCK (regular)**
| Código | Ventas/año |
|---|---|
| S1 | > 250 |
| S2 | 121–250 |
| S3 | 61–120 |
| S4 | 31–60 |
| S5 | 15–30 |
| S6 | 7–14 |
| S7 | 4–6 |
| S8 | 1–3 |

→ S1–S4: movimiento alto · S5–S6: movimiento medio · S7–S8: movimiento bajo

**O — Obsoleto**
| Código | Definición |
|---|---|
| OS | Sustitución antiguo (referencia anterior) |
| ON | >6 meses en stock / nunca vendido |
| OP | Sin ventas >12 meses |
| OR | Sin ventas >24 meses |

**N — New & Special**
| Código | Definición |
|---|---|
| X | >15 ventas / primeros 6 meses |
| Y | 4–15 ventas / primeros 6 meses |
| Z | 0–3 ventas / primeros 6 meses |
| M | Campaña |
| O | Non-stock |

**I — Obsoleto**
| Código | Definición |
|---|---|
| I | >12 meses sin ventas / sin stock |

### Segmento "S" — preguntas de gestión
- **Movimiento alto (S1-S4)**: ¿Tengo suficiente stock para cubrir picos de demanda? ¿La referencia sigue vigente o hay sustitución? ¿El proveedor tiene disponibilidad suficiente?
- **Movimiento medio/bajo (S5-S8)**: ¿Cuánto cuesta la pieza? ¿Es necesaria para mantener el vehículo movilizado? ¿Es una pieza de servicio/reputación esperada por el cliente? ¿Tengo espacio suficiente en almacén?

### Segmento "O" — preguntas de gestión
- **OS**: ¿Se vende la referencia antigua antes que la nueva (FIFO)? ¿Está bien preparada la localidad en almacén para practicar FIFO?
- **ON**: ¿Cómo asegurar entrega inmediata de pedidos individuales tras la llegada? ¿Qué se necesita realmente para el stock inicial de un modelo/sistema nuevo?
- **OP (mercado activo) / OR (mercado pasivo)**: ¿Qué repuestos tengo en stock (segmentos)? ¿Existe todavía mercado? ¿Dónde están los clientes potenciales y cómo contactarlos? ¿Cómo ofrecer estos repuestos atractivamente?

### Segmento "N" — preguntas de gestión
- **M (campaña)**: ¿Se puede citar al cliente para instalación tras la llegada proyectada de piezas costosas? ¿Está el repuesto asignado a una campaña técnica de fábrica? ¿Hay que informar activamente a clientes sobre campañas activas (recall)? ¿Se puede usar el repuesto para reparaciones regulares al margen de la campaña?
- **X/Y/Z (stock nuevo, sin historial)**: ¿Con qué base se decide pedir stock (pedido de cliente, modelo nuevo, evaluación técnica, uso interno)? ¿Cómo evitar tener el repuesto tiempo excesivo en almacén?
- **O (non-stock, tratamiento individual)**: ¿Hay demanda individual para estos repuestos? ¿Hay tiempos de pedido distintos (proveedor local, repuestos peligrosos)? ¿Hay periodos de stock distintos (ropa, accesorios)? ¿Hay otra causa razonable para excluirlos del stock regular?
