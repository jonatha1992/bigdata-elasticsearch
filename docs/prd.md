# Requisitos de producto: curaduría de terminología clínica

Actualizado el 2026-09-06. Audiencia: el dueño del proyecto y quien revise una
demostración local. Es un proyecto personal de aprendizaje sobre Elasticsearch, no un
trabajo académico ni un sistema en producción.

> **Cambio de alcance.** El repositorio arrancó como un laboratorio de eventos sintéticos
> de e-commerce orientado a agregaciones y dashboards de Kibana. Ese alcance se descartó
> sin implementar. El producto es este, y está construido y verificado. La historia
> anterior queda en el commit `ddccbd0`.

---

## 1. Problema

Un curador de terminología necesita encontrar un concepto clínico entre miles usando las
palabras que **realmente escribe**: sin tildes, con abreviaturas, con errores de tipeo, o
con un sinónimo que no figura en el nombre oficial.

Buscar "hipertension" y no encontrar "Hipertensión arterial" no es un problema de
tipeo del usuario. Es una falla del sistema.

Después de encontrarlo, necesita **decidir** sobre él — aprobarlo, rechazarlo, dejar una
nota — y que esa decisión quede registrada de forma confiable.

Eso exige dos mitades: un almacén relacional que guarde la decisión editorial con
garantías transaccionales, y un motor de búsqueda que la haga encontrable con tolerancia
lingüística. Y exige resolver qué pasa cuando los dos dejan de coincidir, porque van a
dejar de coincidir.

## 2. Objetivo de aprendizaje

Ejercitar a Elasticsearch como **motor de búsqueda**: analyzers, relevancia, boosts,
facetas, autocompletado y el problema de consistencia entre un almacén transaccional y
un índice derivado. Alrededor de eso, el stack de una posición backend: Python, API REST,
Docker, Linux y un frontend que consume la API.

## 3. Usuarios

| Usuario | Qué necesita |
|---|---|
| **Curador de terminología** | Encontrar conceptos con lenguaje natural imperfecto, revisar sus descripciones y registrar una decisión |
| **Operador del laboratorio** | Saber si los dos almacenes coinciden y repararlo cuando no |
| **Revisor técnico** | Entender el diseño leyendo la documentación y reproducir la verificación |

## 4. Requisitos y evidencia

Cada requisito tiene una prueba ejecutable. Sin evidencia, el requisito no está cumplido.

| ID | Requisito | Evidencia |
|---|---|---|
| C1 | Modelar conceptos con nombre completamente especificado, etiqueta semántica y sinónimos | `app/models.py`; 20 conceptos en `seed/concepts.json`; [DER](data-model.md#1-diagrama-de-entidad-relación) |
| C2 | Exponer CRUD con validación, conflictos y no encontrados explícitos | `409` en ID duplicado, `422` en payload inválido, `404` en inexistente |
| C3 | Buscar tolerando tildes faltantes, errores de tipeo y sinónimos | `test_search_ignores_missing_accents`, `test_search_tolerates_a_typo`, `test_search_matches_a_synonym_not_present_in_the_fsn` |
| C4 | Los filtros acotan sin alterar la relevancia | `test_filters_do_not_change_the_score` compara puntajes con y sin filtro |
| C5 | Exponer facetas con conteos del resultado completo | `test_facets_count_the_whole_result_set` |
| C6 | Autocompletar por prefijo de la última palabra | `test_suggest_matches_a_prefix_of_the_last_word` |
| C7 | Hacer inspeccionable el análisis de texto | `GET /search/analyze`; `test_analyzers_treat_the_same_text_differently` |
| C8 | Detectar y reparar desincronización entre los dos almacenes | `test_reconcile_detects_drift_and_reindex_repairs_it` borra un documento por detrás de la API y verifica la reparación |
| C9 | Interfaz de curaduría con búsqueda, filtros y cambio de estado | `ui/`; verificada en navegador a 1440px y 390px |
| C10 | El stack local rechaza peticiones sin autenticar y persiste datos | `tests/test_stack.py`; [registro de acceso](access-and-verification.md) |

**C3 es el requisito que define el producto.** Los otros nueve sostienen a ese.

## 5. Criterios de aceptación

Una entrega se considera aceptada cuando:

1. La suite completa pasa contra Elasticsearch real, sin tests salteados por código roto.
2. `GET /admin/reconcile` devuelve `in_sync: true` después de cargar el fixture.
3. Buscar `hipertension` sin tilde encuentra "Hipertensión arterial".
4. Buscar `diabetis` con error de tipeo encuentra las tres diabetes.
5. Buscar `EPOC` encuentra el concepto por sinónimo, aunque la sigla no esté en el FSN.
6. Los puntajes de una consulta con filtro y sin filtro son idénticos.
7. Un `PATCH` de estado deja `indexed_at` igual a `updated_at`, probando que Elasticsearch
   confirmó antes de limpiar el flag.
8. La UI no desborda horizontalmente a 390px ni emite errores de consola.

### Verificación ejecutada el 2026-09-06

```console
$ .\.vennv\Scripts\python.exe -m pytest tests/ -q
33 passed, 2 warnings in 47.81s
```

Suite completa, sin exclusiones. Detalle en
[presentation-verification.md](presentation-verification.md).

## 6. Contrato de conciliación

Es el invariante del sistema, y se puede consultar por HTTP:

```
conceptos_en_base == documentos_en_indice   cuando   pending_index == 0
```

`GET /admin/reconcile` devuelve los tres números y un `in_sync` booleano. La franja
superior de la UI los muestra permanentemente.

**Un desacuerdo es la señal, no un detalle.** El sistema no promete que los dos almacenes
nunca diverjan; promete que la divergencia es visible y reparable. Prometer lo primero
sería mentir.

## 7. Fuera de alcance

Decisiones deliberadas, cada una con su motivo:

| Excluido | Por qué |
|---|---|
| Autenticación en la API y la UI | El servicio es local, publicado en loopback. Es un requisito bloqueante antes de cualquier exposición |
| Migraciones con Alembic | `create_all()` alcanza mientras el esquema se pueda recrear desde cero sin perder nada que importe |
| Indexación asincrónica por worker | La versión sincrónica enseña el problema de los dos almacenes con menos partes móviles |
| PostgreSQL | SQLite alcanza para un escritor. El código no es específico de SQLite |
| Edición de descripciones desde la UI | Se hace por API. La UI cubre el flujo de decisión, que es el que se quería ejercitar |
| Paginación de resultados en la UI | Con 20 conceptos no hay presión. Es necesario antes de miles |
| Relaciones concepto-concepto de SNOMED CT | `is a`, `finding site` y los refsets son otro proyecto |
| Multinodo y tolerancia a fallos distribuida | Un nodo en una máquina no puede demostrarlo, y varios nodos en la misma máquina comparten su dominio de falla |

El fixture de conceptos es un subconjunto ilustrativo en castellano. **No es una
distribución de SNOMED CT**, que requiere licencia de SNOMED International para
redistribuirse.

## 8. Restricciones

- **Local únicamente.** Elasticsearch y Kibana publicados en `127.0.0.1`, solo HTTP.
  El acceso remoto exige un diseño aparte de TLS y control de acceso.
- **Versiones fijadas.** Elasticsearch y Kibana en 9.5.3; cliente `elasticsearch` 9.5.0,
  alineado en versión mayor con el servidor.
- **Un shard primario, cero réplicas.** Es la topología correcta para un nodo único.
- **Recursos finitos.** Elasticsearch limitado a 4 GiB con heap de 2 GiB; Kibana a 2 GiB.
  Cuando la presión de recursos invalide un experimento, hay que reportar la limitación
  en vez de publicar el número.

## 9. Riesgos

- **El mapping es inmutable.** Cambiar un analyzer exige recrear el índice y reindexar.
  Con datos reales eso es una migración planificada, no un `--reset`.
- **~~La integridad depende del ORM.~~ Resuelto el 2026-09-06.** SQLite no aplica claves
  foráneas por defecto (`PRAGMA foreign_keys = 0`), así que el `ON DELETE CASCADE`
  declarado no actuaba y un `DELETE` en SQL crudo dejaba huérfanos. `app/db.py` ahora
  enciende el pragma en cada conexión nueva, solo para SQLite. Evidencia:
  `tests/test_database_integrity.py`.
- **La máquina de estados de curaduría no está forzada.** Los valores se validan; las
  transiciones no. Cualquier estado puede saltar a cualquier otro.
- **`fuzziness: AUTO` es un compromiso.** Tolera los errores de tipeo reales, pero con un
  vocabulario más grande va a traer falsos positivos. Hay que medirlo antes de escalar el
  fixture.
- **Sin suite de frontend.** El build tipa en modo estricto y la verificación fue manual
  en navegador. Un cambio de UI puede romper algo sin que nada lo detecte.

## 10. Estado de entrega

| Capacidad | Estado |
|---|---|
| Stack local autenticado con volúmenes persistentes | Verificado |
| Modelo relacional y fixture | Entregado |
| API de curaduría: CRUD, búsqueda, sugerencias, análisis | Entregado |
| Detección y reparación de deriva entre almacenes | Entregado |
| UI de curaduría en React + TypeScript | Entregado |
| Suite de integración completa en verde | Verificado, 33 tests |
| Documentación con diagramas de arquitectura y datos | Entregado |

Lo que falta para que esto sea software profesional está priorizado en el
[backlog de ingeniería](engineering-backlog.md).
