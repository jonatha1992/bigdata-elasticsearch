# API de curaduría de terminología clínica

Servicio FastAPI sobre dos almacenes: **SQLite** para el registro editorial y
**Elasticsearch** para la búsqueda. Es el slice vertical que ejercita el stack del
puesto: Python, API REST, Docker, Elasticsearch y un modelo de dominio tipo SNOMED CT.

Verificado el 2026-09-06 contra Elasticsearch 9.5.3 en local: la suite completa en
verde (33 tests), 20 conceptos cargados y conciliados.

Documentos relacionados: la [arquitectura](architecture.md) tiene los diagramas de
secuencia y los pipelines; el [modelo de datos](data-model.md) tiene el DER, el
esquema físico y la correspondencia con el documento de Elasticsearch.

## Levantar el entorno

Elasticsearch y Kibana corren en Docker. La API corre local, sin contenedor.

```powershell
cd D:\Repositorio\bigdata-elasticsearch
docker compose up -d --pull never
.\.vennv\Scripts\python.exe -m scripts.seed --reset
.\.vennv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- Documentación interactiva: <http://127.0.0.1:8000/docs>
- Estado del servicio: <http://127.0.0.1:8000/health>

`scripts/seed.py --reset` borra el índice y vacía las tablas antes de cargar.
Es la única forma de aplicar un mapping modificado: los analyzers y los tipos de
campo son inmutables una vez creado el índice.

La contraseña sale de `ELASTIC_PASSWORD` en el `.env` local. Si falta, el servicio
falla al primer contacto con Elasticsearch en vez de mandar peticiones anónimas.

## Modelo de datos

Un concepto tiene un nombre completamente especificado (FSN), una etiqueta
semántica y muchas descripciones (sinónimos). Es una simplificación didáctica de
SNOMED CT, no un formato de release.

| Tabla | Campos relevantes |
|---|---|
| `concepts` | `concept_id` (PK), `fsn`, `semantic_tag`, `module`, `active`, `curation_status`, `curation_note`, `effective_time` |
| `descriptions` | `concept_id` (FK), `term`, `type` (`fsn`/`synonym`), `language`, `preferred`, `active` |

Estados de curaduría: `draft` → `in_review` → `approved` | `rejected`.

Dos campos existen solo por el problema de los dos almacenes:

- `pending_index`: la fila se marca sucia **antes** de indexar.
- `indexed_at`: se completa **solo** cuando Elasticsearch confirmó la escritura.

Una caída entre ambos pasos deja evidencia recuperable en lugar de desincronización
silenciosa. `POST /admin/reindex` repara lo que quedó marcado.

## Endpoints

### Conceptos

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/concepts` | Crea un concepto e indexa. `409` si el ID ya existe |
| `GET` | `/concepts` | Lista paginada. Filtros: `curation_status`, `semantic_tag`, `pending_index` |
| `GET` | `/concepts/{id}` | Un concepto con sus descripciones. `404` si no existe |
| `PATCH` | `/concepts/{id}` | Actualización parcial. `descriptions` reemplaza la lista completa |
| `DELETE` | `/concepts/{id}` | Borra de ambos almacenes. `204` |

### Búsqueda

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/search` | Búsqueda full-text con filtros, facetas y resaltado |
| `GET` | `/search/suggest` | Autocompletado por prefijo |
| `GET` | `/search/analyze` | Muestra los tokens que produce un analyzer |

### Operación

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/admin/index` | Crea el índice si falta. Nunca parchea uno existente |
| `POST` | `/admin/reindex` | Reindexa lo pendiente. `?only_pending=false` reconstruye todo |
| `GET` | `/admin/reconcile` | Compara conteos relacional vs índice |
| `GET` | `/health` | Estado de API, base, Elasticsearch e índice |

## Diseño del índice

Tres tratamientos del mismo texto, a propósito:

| Nombre | Qué hace | Para qué |
|---|---|---|
| `clinical_text` | minúsculas + quita acentos + quita stopwords + stemming español | Caja de búsqueda principal. Recall alto |
| `clinical_exact` | minúsculas + quita acentos, **sin** stemming | Precisión. Sube los aciertos exactos por encima de los stemmeados |
| `clinical_keyword` | normalizador: un solo token para toda la cadena | Filtros exactos, facetas y ordenamiento |

`asciifolding` importa más de lo que parece en castellano clínico: los curadores
escriben "hipertension" sin tilde todo el tiempo. Sin folding, esas consultas
devolverían cero en silencio.

Campos indexados:

- `fsn`, `preferred_term` — `text` + subcampos `.exact` y `.raw`
- `terms` — todos los sinónimos activos, aplanados en un solo campo multivaluado
- `suggest` — `search_as_you_type`, campo de primer nivel (genera sus propios
  subcampos `._2gram` y `._3gram`, así que no puede ser un multi-field)
- `semantic_tag`, `curation_status`, `module` — `keyword`, para facetas y filtros
- `active` — `boolean`; `effective_time`, `indexed_at` — `date`

El mapping es `dynamic: strict`: un campo no declarado hace fallar la indexación en
vez de inventar un tipo. Preferible que la sorpresa aparezca al escribir y no seis
meses después, cuando una consulta devuelve mal.

Boosts, de mayor a menor: `fsn.exact^6`, `preferred_term.exact^5`, `fsn^4`,
`preferred_term^3`, `terms.exact^2`, `terms^1`. Un acierto exacto le gana a uno
stemmeado, y el nombre completamente especificado le gana a un sinónimo.

### Filtros versus scoring

Los filtros van en contexto `filter`, nunca en `must`. Un filtro responde sí o no,
es cacheable y **no debe** influir en el puntaje de relevancia. Solo la parte de
texto libre va en contexto de scoring. Mezclarlos es la forma clásica de terminar
con rankings que no tienen explicación.

Hay un test que fija esa regla: `test_filters_do_not_change_the_score`.

## Ejemplos

Búsqueda sin tilde, encuentra igual:

```console
$ curl -s "http://127.0.0.1:8000/search?q=hipertension+arterial"
```

Búsqueda con error de tipeo (`fuzziness: AUTO`):

```console
$ curl -s "http://127.0.0.1:8000/search?q=diabetis"
```

Búsqueda por sinónimo que no aparece en el FSN:

```console
$ curl -s "http://127.0.0.1:8000/search?q=EPOC"
```

Filtro más facetas:

```console
$ curl -s "http://127.0.0.1:8000/search?q=&semantic_tag=trastorno&curation_status=approved"
```

Autocompletado:

```console
$ curl -s "http://127.0.0.1:8000/search/suggest?q=diabetes+mel"
```

Ver qué hace el analyzer, que es la herramienta para responder "por qué no matcheó":

```console
$ curl -s "http://127.0.0.1:8000/search/analyze?text=Enfermedades+pulmonares+cronicas&analyzer=clinical_text"
```

## Tests

```powershell
.\.vennv\Scripts\python.exe -m pytest tests/ -q
```

Son tests de **integración**: necesitan el stack de Docker arriba. Si Elasticsearch
no responde, la suite se saltea con un mensaje explícito en vez de fallar confusa.

Usan su propio índice (`clinical-concepts-test`) y su propio archivo SQLite en un
directorio temporal, así que nunca tocan los datos de desarrollo.

Resultado al 2026-09-06: **33 pasan, 0 fallan**, en 47,81 segundos. Es la suite
completa del repositorio, sin exclusiones.

Cobertura: salud del servicio, CRUD completo, rechazos de validación (`422`),
conflicto de ID (`409`), inexistente (`404`), paginación y filtros, insensibilidad a
tildes, tolerancia a typos, búsqueda por sinónimo, independencia de filtros respecto
del score, facetas, resaltado, estado vacío, autocompletado, comparación entre
analyzers, y detección y reparación de desincronización.

### Dos bugs que encontraron los tests

Vale la pena registrarlos, porque los dos eran reales:

1. `client.indices.exists()` devuelve un `HeadApiResponse`, no un `bool`. Es
   *truthy*, así que en un `if` funciona, pero Pydantic lo rechazó al validar la
   respuesta. Se resolvió con un `bool()` explícito.
2. `Concept.preferred_term` leía `description.active` en objetos todavía no
   persistidos. Los defaults de columna de SQLAlchemy se aplican en el `INSERT`, así
   que antes del flush el valor es `None`, no `True`. En el camino de producción no
   se notaba porque siempre hay commit antes de indexar; el test transitorio lo
   expuso.

## Limitaciones actuales

- **SQLite tiene un solo escritor a la vez.** Alcanza para un desarrollador. Con
  workers concurrentes vas a ver `database is locked`; ese es el momento de pasar a
  PostgreSQL. Nada en `models.py` ni en `db.py` es específico de SQLite: el cambio es
  la URL de conexión más el driver.
- **Sin migraciones.** `create_all()` alcanza para arrancar; Alembic va antes del
  primer cambio de esquema sobre datos que importen.
- **Sin autenticación en la API.** El servicio es local. Poner auth antes de
  exponerlo a cualquier otra máquina.
- **La indexación es sincrónica.** Un sistema real mueve el paso de indexar a un
  worker que consume una tabla de outbox. La historia de recuperación es la misma;
  cambia quién ejecuta el paso.
- **Los fallos de indexación no se registran.** `index_concept` captura la excepción
  y devuelve `False` sin dejar rastro del motivo. Cuando una fila quede pendiente, no
  vas a saber si fue un timeout, un error de mapping o una credencial vencida.
- **La FK de `descriptions` no se aplica.** SQLite trae `PRAGMA foreign_keys` en `0`
  y el proyecto no lo enciende, así que el borrado en cascada depende del ORM.
- El fixture de `seed/concepts.json` es un subconjunto ilustrativo y reducido, en
  castellano. **No es una distribución de SNOMED CT**, que requiere licencia de
  SNOMED International para su redistribución.

## Próximos pasos

La UI de curaduría ya está entregada; está documentada en
[curation-ui.md](curation-ui.md).

Lo que sigue, priorizado con su motivo y su señal de urgencia, está en el
[backlog de ingeniería](engineering-backlog.md). Los tres primeros que tocan a esta
API: credencial de mínimo privilegio para Elasticsearch, alias de índice para
reindexar sin caída, y Alembic antes del primer cambio de esquema sobre datos que
importen.
