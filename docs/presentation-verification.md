# Registro de verificación y handoff

Última actualización: 2026-09-06.

Dos entregas registradas acá, en orden cronológico inverso.

---

# Entrega 2 — Curaduría de terminología clínica (2026-09-06)

API FastAPI sobre SQLite y Elasticsearch, con UI React + TypeScript. Se instalaron
dependencias de aplicación por primera vez en el proyecto. No se modificó la
configuración de Docker, las credenciales ni los volúmenes.

## Entregado

- `app/` — servicio FastAPI: modelos SQLAlchemy, mapping del índice, proyección a
  Elasticsearch, constructores de query y tres routers.
- `ui/` — interfaz React + TypeScript con Vite, sin librerías de UI externas.
- `scripts/seed.py` y `seed/concepts.json` — 20 conceptos clínicos de ejemplo.
- `tests/conftest.py` y `tests/test_curation_api.py` — 29 tests de integración.
- [curation-api.md](curation-api.md) y [curation-ui.md](curation-ui.md).
- `requirements.txt` — dependencias de Python fijadas.

## Chequeos ejecutados

### Suite de tests

```console
$ .\.vennv\Scripts\python.exe -m pytest tests/test_curation_api.py tests/test_stack.py -q
33 passed in 48.09s
```

29 tests nuevos más los 4 preexistentes de infraestructura. Son tests de **integración**:
necesitan el stack Docker arriba. Usan su propio índice (`clinical-concepts-test`) y su
propio archivo SQLite en un directorio temporal, así que no tocan los datos de
desarrollo. Si Elasticsearch no responde, la suite se saltea con un mensaje explícito en
vez de fallar de forma confusa.

Cobertura: salud del servicio, CRUD completo, rechazos de validación (`422`), conflicto
de ID (`409`), inexistente (`404`), paginación y filtros, insensibilidad a tildes,
tolerancia a errores de tipeo, búsqueda por sinónimo, independencia de los filtros
respecto del score, facetas, resaltado, estado vacío, autocompletado, comparación entre
analyzers, y detección y reparación de desincronización.

### Dos bugs que encontraron los tests

Los dos eran reales:

1. `client.indices.exists()` devuelve un `HeadApiResponse`, no un `bool`. Es *truthy*,
   así que dentro de un `if` funciona, pero Pydantic lo rechazó al validar la respuesta
   de `/health`. Corregido con un `bool()` explícito.
2. `Concept.preferred_term` leía `description.active` en objetos todavía no persistidos.
   Los defaults de columna de SQLAlchemy se aplican en el `INSERT`, así que antes del
   flush el valor es `None`, no `True`. En el camino de producción no se notaba porque
   siempre hay commit antes de indexar; el test con un objeto transitorio lo expuso.

El primero es del tipo que rompe recién al serializar. El segundo solo aparece si
escribís el test.

### Carga de datos

```console
$ .\.vennv\Scripts\python.exe -m scripts.seed --reset
index: clinical-concepts
index_created: True
concepts_inserted: 20
concepts_in_fixture: 20
selected: 20
indexed: 20
failed: 0
```

### Comportamiento de búsqueda, contra el stack real

| Consulta | Resultado observado |
|---|---|
| `hipertension` (sin tilde) | 1 acierto: "Hipertensión arterial", puntaje 13.82 |
| `diabetis` (con error de tipeo) | 3 aciertos: las tres diabetes |
| `EPOC` | 1 acierto por sinónimo; la sigla no está en el nombre completamente especificado |
| `diabetes mel` (autocompletado) | 3 sugerencias por prefijo |
| `dolor to` (autocompletado) | 2 sugerencias |
| Consulta vacía | 20 conceptos; facetas: trastorno 7, procedimiento 5, hallazgo 3, sustancia 3, estructura corporal 2 |
| Filtro trastorno + aprobado | 6 conceptos |

### Build de la UI

```console
$ npm run build
✓ 36 modules transformed.
dist/assets/index-DtG5C2Od.js   157.37 kB │ gzip: 50.73 kB
✓ built in 784ms
```

TypeScript en modo estricto, con `noUncheckedIndexedAccess`, `noUnusedLocals` y
`noUnusedParameters`.

### Verificación en navegador

Ejecutada con herramientas de Playwright contra el stack completo corriendo.

| Comprobación | Resultado |
|---|---|
| Carga inicial | 20 conceptos; franja "20 en base · 20 en índice · Sincronizado" |
| Facetas | conteos correctos por tipo semántico y estado |
| Búsqueda `hipertension` | 1 resultado, puntaje 13.82, con `<mark>hipertensivo</mark>` renderizado |
| Recálculo de facetas | tras filtrar, se recalculan al subconjunto |
| Panel de detalle | carga las 4 descripciones con sus flags |
| `PATCH` de estado | guardó, reindexó, e `indexed_at` quedó igual a `updated_at` |
| Responsive 1440px y 390px | sin desborde horizontal |
| Consola del navegador | sin errores tras agregar el favicon |

El `PATCH` es la comprobación que más importa. Que la marca de indexación coincida con
la de actualización es la evidencia de que Elasticsearch confirmó **antes** de limpiar
el flag `pending_index`. Verificado también contra la API:

```json
{"concept_id":"38341003","curation_status":"in_review",
 "pending_index":false,
 "updated_at":"2026-09-06T22:40:45.689381",
 "indexed_at":"2026-09-06T22:40:45.688362"}
```

El concepto se restauró después a `approved`, y `reconcile` volvió a `in_sync: true`.

Nota de método: durante la sesión de navegador hubo interacciones que no fueron
ordenadas explícitamente por el guion de verificación. Por eso el resultado del `PATCH`
se confirmó por segunda vez contra la API, no solo por lo que mostraba la pantalla.

### Incidente de infraestructura

A mitad de la sesión el contenedor de Elasticsearch salió con código 137. Los logs
muestran un apagado ordenado (`stopping ...`, `watcher has stopped`), y
`OOMKilled: false`. No fue un crash ni falta de memoria: algo lo detuvo desde afuera,
probablemente un reinicio de Docker Desktop. Se levantó con `docker compose up -d` y los
datos sobrevivieron: están en volúmenes nombrados.

## Excepciones de método

La documentación y el estilado estático usan la excepción explícita de TDD para
elementos no funcionales; sus chequeos más cercanos son revisión de lectura, inspección
de enlaces y revisión visual en navegador.

No hay suite automatizada de frontend. El build tipa en modo estricto y la verificación
en navegador fue manual. Vitest y Testing Library son el siguiente paso.

No se hizo auditoría con lector de pantalla. El marcado usa roles ARIA correctos para el
combobox y los filtros, pero marcado correcto no equivale a auditoría.

## Límites de esta entrega

- Sin autenticación en la API ni en la UI.
- Sin migraciones; `create_all()` alcanza para arrancar, Alembic va antes del primer
  cambio de esquema sobre datos que importen.
- La indexación es sincrónica. Un worker con tabla de outbox es el paso siguiente.
- SQLite tiene un solo escritor a la vez. Con workers concurrentes aparece
  `database is locked`; ese es el momento de pasar a PostgreSQL.
- El fixture no es una distribución de SNOMED CT, que requiere licencia.

## Rollback

Eliminar `app/`, `ui/`, `scripts/`, `seed/`, `curation.db` y los dos documentos nuevos.
Borrar el índice con `DELETE /clinical-concepts`. Conservar `.env`, la configuración de
Docker y los volúmenes nombrados. No hubo despliegue a producción.

---

# Entrega 1 — Dashboard de presentación offline (2026-09-06)

Clasificación M: demostrador interactivo local y documentación de producto enlazada.
No cambió infraestructura, credenciales ni datos persistentes.

## Entregado

- [PRD](prd.md): intención del producto, requisitos medibles y hitos propuestos.
- [Arquitectura](architecture.md): diagramas Mermaid con los límites entre lo existente y lo propuesto.
- [Dashboard](../dashboard/index.html): métricas sintéticas offline, filtros compartidos
  de fecha y categoría, gráficos, ranking de productos y flujo del sistema visible.
- [Guía de presentación](dashboard.md): cómo mostrar la demo y qué queda para Kibana.

## Chequeos ejecutados

| Comportamiento | RED | GREEN | Refactor | Verificación final |
|---|---|---|---|---|
| Métricas, filtros combinados, resultados vacíos, fechas inválidas, fixture determinista | `node --test dashboard/model.test.js` falló porque no se pudo importar la API de `model.js`, ausente a propósito | Mismo comando: 5 pasaron, 0 fallaron | No hizo falta refactor aparte; funciones puras pequeñas con aserciones independientes | Un revisor independiente reejecutó la suite: 5 pasaron |
| Renderizado en navegador | La aserción falló mientras `app.js` estaba ausente a propósito | Las aserciones pasaron tras la implementación | Un helper compartido del DOM mantiene consistente la inserción de texto | Métricas por defecto, filtrado, estado vacío, fechas invertidas y reset: todos pasaron |

Chequeos adicionales:

- `node --check dashboard/app.js` pasó.
- La revisión independiente no encontró contradicciones de métricas ni de estado.
- Línea base en navegador: 940 eventos, 140 eventos de compra, USD 22.430,00 de valor de
  compras, 47 eventos de error y 5,0% de proporción de errores.
- Responsive a 390px y 1440px: sin desborde horizontal.
- Los diagramas Mermaid recibieron revisión de fuente y lectura, no renderizado
  automatizado. El diagrama de sistema del dashboard se renderiza en HTML/CSS.

## Límites de esta entrega

La demo no tiene backend ni métricas en vivo. Usa un fixture de JavaScript aparte y no
implementa el módulo `events.py` que esperan los tests del generador. Esos tests
preexistentes no se modificaron y **siguen fallando**: `tests/test_events.py` importa un
módulo que no existe.

La recuperación y el almacenamiento de Memorix no pudieron enlazarse a este workspace
sin Git. La CLI tampoco estaba disponible. No se afirma que haya habido sincronización
de memoria.
