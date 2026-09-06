# Requisitos de producto: laboratorio de aprendizaje de Elasticsearch

Actualizado el 2026-09-06. Audiencia: el dueño del proyecto y quien revise una
demostración local. Es un proyecto personal de aprendizaje, no un trabajo académico ni
un sistema en producción.

## Los dos productos del repo

El objetivo de aprendizaje son las dos caras de Elasticsearch. Cada una tiene su
producto:

| Producto | Cara del motor | Estado |
|---|---|---|
| **Curaduría de terminología clínica** | Búsqueda: analyzers, relevancia, autocompletado | **Entregado y verificado** |
| **Laboratorio de eventos sintéticos** | Analítica: agregaciones, histogramas, benchmarks | Diseñado, sin implementar |

El primero se construyó el 2026-09-06 y está documentado en
[curation-api.md](curation-api.md) y [curation-ui.md](curation-ui.md). Sus requisitos
están en la sección siguiente.

El segundo mantiene su diseño y sus criterios de aceptación (R1 a R9, más abajo) sin
implementar. Su contrato de generador existe como tests; el módulo `events.py` nunca se
escribió.

## Producto 1: curaduría de terminología clínica

### Problema y resultado

Un curador de terminología necesita encontrar un concepto clínico entre miles usando
las palabras que realmente escribe: sin tildes, con abreviaturas, con errores de tipeo,
o con un sinónimo que no figura en el nombre oficial. Después necesita decidir sobre él
y que esa decisión quede registrada.

Eso requiere las dos mitades: un almacén relacional que guarde la decisión editorial, y
un motor de búsqueda que la haga encontrable. Y requiere resolver qué pasa cuando los
dos dejan de coincidir.

### Requisitos y evidencia

| ID | Requisito | Evidencia |
|---|---|---|
| C1 | Modelar conceptos con nombre completamente especificado, etiqueta semántica y sinónimos | `app/models.py`; 20 conceptos en `seed/concepts.json` |
| C2 | Exponer CRUD con validación, conflictos y no encontrados explícitos | `409` en ID duplicado, `422` en payload inválido, `404` en inexistente; 5 tests |
| C3 | Buscar tolerando tildes faltantes, errores de tipeo y sinónimos | `test_search_ignores_missing_accents`, `test_search_tolerates_a_typo`, `test_search_matches_a_synonym_not_present_in_the_fsn` |
| C4 | Los filtros acotan sin alterar la relevancia | `test_filters_do_not_change_the_score` compara puntajes con y sin filtro |
| C5 | Exponer facetas con conteos del resultado completo | `test_facets_count_the_whole_result_set` |
| C6 | Autocompletar por prefijo de la última palabra | `test_suggest_matches_a_prefix_of_the_last_word` |
| C7 | Hacer inspeccionable el análisis de texto | `GET /search/analyze`; `test_analyzers_treat_the_same_text_differently` |
| C8 | Detectar y reparar desincronización entre los dos almacenes | `test_reconcile_detects_drift_and_reindex_repairs_it` borra un documento por detrás de la API y verifica la reparación |
| C9 | Interfaz de curaduría con búsqueda, filtros y cambio de estado | `ui/`; verificada en navegador a 1440px y 390px |

Verificación al 2026-09-06: **33 tests en verde** en unos 48 segundos, contra
Elasticsearch 9.5.3 real. Detalle en
[presentation-verification.md](presentation-verification.md).

### Contrato de conciliación

Para toda ejecución, el conteo relacional y el indexado deben coincidir cuando no queda
nada marcado como pendiente:

`conceptos_en_base == documentos_en_indice` cuando `pending_index == 0`

`GET /admin/reconcile` devuelve los tres números y un `in_sync` booleano. La franja
superior de la UI los muestra permanentemente. Un desacuerdo es la señal, no un detalle.

### Fuera de alcance de este producto

Autenticación de la API, migraciones con Alembic, indexación asincrónica por worker,
edición de descripciones desde la UI, paginación de resultados, y PostgreSQL.
Están listados con su motivo en [curation-api.md](curation-api.md) y
[curation-ui.md](curation-ui.md).

El fixture de conceptos es un subconjunto ilustrativo en castellano. **No es una
distribución de SNOMED CT**, que requiere licencia de SNOMED International para
redistribuirse.

---

## Producto 2: laboratorio de eventos sintéticos

Todo lo que sigue es **diseño sin implementar**.

## Problema y resultado esperado

Una instalación de Elasticsearch por sí sola no muestra cómo la actividad cruda se
convierte en información útil. El laboratorio va a proveer un camino reproducible desde
eventos sintéticos de tienda online hasta documentos validados, consultas de búsqueda,
métricas conciliadas y un dashboard. El dueño debería poder explicar cada paso y demostrar
tanto el éxito como el fallo.

## Evidencia y estado de entrega

| Capacidad | Estado | Evidencia o trabajo pendiente |
|---|---|---|
| Elasticsearch y Kibana locales autenticados | Verificado el 2026-09-06 | [Registro de acceso](access-and-verification.md); `docker compose ps` y los tests de integración confirmaron el estado en runtime |
| Configuración de contenedores y volúmenes persistentes | Configurado | [compose.yaml](../compose.yaml), [decisión de despliegue](local-stack.md) |
| Generador de eventos reproducible | Tests de contrato redactados; implementación pendiente | [test_events.py](../tests/test_events.py) importa el `events.py` que hoy falta |
| Validación, ingesta por lotes y conciliación | Propuesto | Implementar y verificar de punta a punta |
| Ejemplos de búsqueda y ejecutor de benchmarks | Propuesto | Implementar experimentos repetibles |
| Dashboard operativo de Kibana y saved objects | Propuesto | Los archivos inspeccionados no evidencian ningún dashboard terminado |

La página de login existente es infraestructura, no el dashboard analítico. Cualquier
maqueta de presentación debe etiquetar sus datos como sintéticos y su estado de conexión;
no satisface los criterios de dashboard operativo de más abajo.

El [dashboard de presentación offline](../dashboard/index.html) es un demostrador aparte
con datos de muestra sintéticos y sin conexión a un backend. Ilustra las métricas previstas;
no es una exportación de saved objects de Kibana ni el resultado de una ingesta.

Nota de estado corregida: una versión anterior de este documento decía que el daemon de
Docker no estaba disponible. Eso era cierto en el momento de aquella inspección. El
2026-09-06 el stack se verificó corriendo (`Up (healthy)` en Elasticsearch y Kibana) y
los tests de integración pasaron contra él.

## Usuarios y recorrido de la demostración

El dueño genera un dataset determinista, inspecciona varios registros, lo carga, revisa un
informe de conciliación, ejecuta ejemplos de búsqueda y abre el dashboard.
Un revisor sigue los diagramas de arquitectura, cambia un filtro temporal, compara un
gráfico con su agregación de origen y observa cómo una carga repetida conserva los conteos.

## Requisitos y criterios de aceptación

| ID | Requisito | Evidencia de aceptación |
|---|---|---|
| R1 | Generar eventos `search`, `view`, `purchase` y `error` con IDs estables | La misma semilla, configuración, versión de esquema y cantidad producen registros idénticos y serializables a JSON; los IDs son únicos dentro del dataset; los tests existentes del generador pasan |
| R2 | Validar campos comunes y específicos de cada evento antes de indexar | Los registros válidos pasan; campos faltantes, timestamps o tipos inválidos, tipos de evento desconocidos y valores monetarios inválidos se rechazan indicando el ID del evento o su posición de origen y el motivo |
| R3 | Usar mappings explícitos e IDs de documento estables | Los IDs y categorías soportan filtros exactos, la prosa soporta búsqueda de texto, los timestamps soportan filtrado temporal y los valores monetarios tienen una precisión documentada; los errores de mapping son observables |
| R4 | Cargar lotes acotados y manejar fallos parciales | Se inspecciona cada item del bulk; los fallos reintentables reciben reintentos acotados; los fallos permanentes se reportan; una carga fallida o agotada no puede reportarse como completamente exitosa |
| R5 | Preservar idempotencia y conciliar conteos | Repetir un dataset idéntico contra el mismo destino deja sin cambios su conteo de documentos únicos y sus totales; los IDs duplicados en conflicto con contenido distinto se rechazan explícitamente |
| R6 | Verificar resultados de forma independiente | Un fixture determinista pequeño provee conteos por tipo de evento y suma de montos de compra calculados de forma independiente; los conteos indexados y las consultas coinciden una vez establecida la visibilidad de búsqueda |
| R7 | Demostrar conceptos de búsqueda e indexación | Los ejemplos guardados muestran búsqueda full-text, filtros exactos, salida del analizador, un histograma temporal y una agregación agrupada; la demostración explica refresh versus acknowledgement |
| R8 | Proveer un dashboard operativo | Los saved objects de Kibana y una data view sobre `@timestamp` se pueden recrear; todos los paneles respetan los filtros documentados; los valores de los paneles del fixture coinciden con R6; los estados vacío y sin coincidencias son claros |
| R9 | Medir el rendimiento de forma reproducible | Ejecutar 10.000 y 100.000 eventos; intentar 1.000.000 solo si los recursos lo permiten. Registrar configuración, versiones, hardware, repeticiones, warm-up, duración de la indexación, documentos/segundo exitosos, fallos, almacenamiento y p50/p95 de consultas |

R9 establece una línea base, no un objetivo de throughput prometido. La generación queda
excluida del cronometraje de la indexación. Registrá el límite de visibilidad por separado
para que el tiempo de refresh no cambie en silencio el significado del throughput de
indexación. Mantené fijos el dataset y la configuración al comparar tamaños de lote.

### Contrato de conciliación

Para una ejecución completada, cada registro de entrada tiene un único resultado terminal:

`input = validation_rejected + duplicate_skipped + indexed_success + indexing_failed`

`indexed_success` cuenta registros únicos aceptados cuya escritura final fue confirmada,
no intentos HTTP. `duplicate_skipped` cuenta los IDs idénticos adicionales en la entrada;
el contenido en conflicto se rechaza durante la validación. Las escrituras reintentadas no
inflan estos conteos. Una ejecución interrumpida se marca como incompleta e identifica los
registros sin resolver, en lugar de afirmar que la ecuación prueba el éxito.

Sobre un índice de prueba dedicado y vacío, el conteo final buscable debe ser igual a
`indexed_success`. En una repetición contra el mismo índice, las escrituras exitosas pueden
reemplazar documentos existentes; por lo tanto, reportá el conteo final de únicos por
separado de las escrituras exitosas. La identidad del dataset y el índice destino se
registran junto con los resultados.

## Requisitos del dashboard

Todas las métricas usan el mismo intervalo temporal seleccionado y los filtros activos.
El manifiesto del dataset registra su extensión temporal para que la demostración no abra
sobre una ventana temporal por defecto vacía. Los valores monetarios usan una única moneda
sintética declarada por dataset; monedas distintas nunca deben sumarse sin una conversión
explícita.

| Panel o KPI | Definición |
|---|---|
| Total de eventos | Conteo de documentos de evento indexados |
| Eventos de compra | Conteo donde `event_type = purchase`; no es un conteo de pedidos |
| Monto sintético de compras | Suma de `amount` en los eventos de compra; actividad simulada, no ingresos contabilizados |
| Eventos de error y proporción | Conteo de errores y `100 × conteo de errores / total de eventos`; con denominador cero muestra N/A |
| Ratio de eventos compra/vista | `100 × conteo de eventos de compra / conteo de eventos de vista`; con cero vistas muestra N/A. No es una tasa de conversión y puede superar el 100% |
| Actividad a lo largo del tiempo | Histograma de conteo de eventos, dividido por tipo de evento |
| Productos populares | Conteos de eventos de vista por `product_id`; etiquetar el ranking como vistas |
| Desglose de errores | Conteos de eventos de error por severidad y código de error |
| Términos de búsqueda | Conteos de eventos de búsqueda por valor exacto de la query, si hay un campo keyword mapeado |

La interfaz analítica prevista es Kibana. Un sitio web de presentación aparte puede
definirse con su propio alcance; no es necesario para el primer pipeline operativo.
La demostración debe identificar si un elemento visual es una maqueta o el resultado de una
consulta en vivo.

## Alcance y restricciones

Incluido: generación y validación en Python, ingesta local por lotes, mappings explícitos,
ejemplos de búsqueda, visualización en Kibana, conciliación y benchmarks controlados.
Usar un nodo local de Elasticsearch; el índice de eventos propuesto arranca con un shard
primario y cero réplicas. El despliegue existente fija Elasticsearch y Kibana en 9.5.3.
La compatibilidad de las dependencias de la aplicación todavía debe verificarse antes de
fijarlas.

Excluido de la primera etapa: datos reales de clientes, storefront o checkout, contabilidad
de pedidos de negocio, Kafka, Spark, machine learning, despliegue en la nube, acceso
público, disponibilidad de producción y afirmaciones de rendimiento multinodo. Un dataset
local de alto volumen demuestra mecanismos; no establece capacidad de producción.

## Etapas de entrega

1. **Base (verificada históricamente):** servicios locales autenticados e instrucciones de acceso.
2. **Contrato de datos:** generador, validación, fixtures deterministas y mapping explícito.
3. **Ingesta confiable:** lotes acotados, reintentos, informe de rechazos y conciliación.
4. **Presentación:** búsquedas guardadas, dashboard operativo de Kibana e instrucciones de demo reproducibles.
5. **Experimentos:** benchmarks repetidos; más adelante, ejercicios multinodo con alcance propio.

Cada etapa de implementación exige evidencia test-first y verificación independiente.
Este PRD y sus diagramas documentan el diseño; no implementan estas etapas.

## Riesgos y decisiones pendientes

- Eventos independientes y aleatorios no establecen un embudo de usuario; evitá afirmaciones de conversión.
- Reutilizar IDs entre datasets distintos puede sobrescribir registros: definí la identidad
  del dataset e incluí su namespace en los IDs estables, o aislá los datasets por índice.
- La precisión monetaria debe resolverse antes del generador y del mapping: preferí
  unidades menores enteras con conversión explícita para mostrar, y alineá los tests
  numéricos existentes.
- Restringí las credenciales futuras de ingesta a las operaciones necesarias sobre el
  índice; el login de administrador actual es para el acceso local inicial.
- El despliegue HTTP existente está enlazado a loopback. El acceso remoto o los cambios de
  autenticación requieren un diseño y una gobernanza aparte, no un cambio solo de
  documentación.
- La máquina y los contenedores comparten memoria y disco finitos; frená el escalado de
  volumen cuando la presión de recursos invalide el experimento y reportá la limitación.
- La implementación debe fijar el nombre del índice de eventos, la versión del esquema, la
  hora de inicio fija de generación, la moneda sintética, los límites de reintentos y la
  ubicación de exportación de los objetos de Kibana.

Ver los [diagramas de arquitectura y flujo](architecture.md) para los límites de
despliegue, la secuencia de ingesta propuesta y el modelo conceptual de eventos.
