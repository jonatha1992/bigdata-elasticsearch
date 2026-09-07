# Registro de verificación y handoff

Última actualización: 2026-09-06.

Registro de la entrega del sistema de curaduría clínica y de la evidencia ejecutada
para verificarla.

> **Nota de alcance.** Una entrega anterior — el demostrador offline del laboratorio de
> eventos sintéticos — se retiró del repositorio junto con el resto de ese alcance. Su
> registro de verificación se eliminó con ella; queda en el commit `ddccbd0`.

---

# Curaduría de terminología clínica (2026-09-06)

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
$ .\.vennv\Scripts\python.exe -m pytest tests/ -q
33 passed, 2 warnings in 47.81s
```

Suite completa del repositorio, sin exclusiones: 29 tests de la API de curaduría más
los 4 de infraestructura. Son tests de **integración**:
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

