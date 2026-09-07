# Backlog de ingeniería

Actualizado el 2026-09-06.

Qué separa a este proyecto de software profesional, ordenado por lo que realmente
importa. No es una lista de deseos: cada punto dice **qué falta**, **por qué duele** y
**cuál es la señal de que ya no se puede postergar**.

El criterio de orden no es la dificultad. Es cuánto daño hace la ausencia.

---

## Cómo leer las prioridades

| Nivel | Significa |
|---|---|
| **P0 — Bloqueante** | No se puede exponer ni confiar el dato sin esto |
| **P1 — Necesario** | El proyecto ya duele sin esto; es lo próximo a construir |
| **P2 — Maduración** | Lo que convierte un proyecto que anda en uno que se mantiene |
| **P3 — Escala** | Solo tiene sentido con volumen o usuarios reales |

---

## P0 — Bloqueante antes de cualquier exposición

### Autenticación y autorización en la API

Hoy cualquiera que llegue a `http://127.0.0.1:8000` puede aprobar, rechazar o borrar
conceptos. No hay identidad, no hay rol, no hay registro de quién decidió qué.

En un sistema de curaduría eso no es un hueco de seguridad nada más: es un hueco de
**trazabilidad editorial**. "¿Quién aprobó este concepto?" es una pregunta que el sistema
hoy no puede responder.

Mínimo viable: OAuth2 con tokens JWT (FastAPI lo trae de fábrica con
`OAuth2PasswordBearer`), un rol `curator` y un rol `admin`, y una columna
`decided_by` en `concepts`.

**Señal de urgencia:** el momento en que esto escuche en algo que no sea loopback.

### Credencial de mínimo privilegio para Elasticsearch

La API se conecta como `elastic`, que es superusuario. Puede borrar cualquier índice del
clúster, no solo el suyo.

Arreglo: un rol de Elasticsearch limitado a `clinical-concepts*` con los privilegios
`read`, `write`, `create_index` y `manage`, y un usuario propio para la aplicación.

**Señal de urgencia:** ya. Es media hora de trabajo y elimina toda una clase de accidente.

### Encender las claves foráneas de SQLite

Verificado: `PRAGMA foreign_keys = 0`. El `ON DELETE CASCADE` del esquema está declarado
pero **no se aplica**. Hoy lo salva el `cascade="all, delete-orphan"` del ORM, lo que
significa que la integridad referencial depende de que absolutamente todo pase por
SQLAlchemy.

```python
from sqlalchemy import event

@event.listens_for(engine, "connect")
def _enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

**Señal de urgencia:** el primer script que toque la base sin pasar por el ORM.

---

## P1 — Lo próximo a construir

### Migraciones con Alembic

`create_all()` crea tablas que no existen. No altera las que sí existen. Agregar una
columna hoy significa borrar la base y recargar el fixture.

Eso está bien mientras el único dato sea un fixture regenerable. Deja de estar bien en el
instante en que haya una decisión de curaduría que no se pueda reconstruir.

**Señal de urgencia:** el primer cambio de esquema sobre datos que no querés perder.

### Alias de índice para reindexado sin caída

Hoy la aplicación apunta al índice `clinical-concepts` por su nombre literal. Como el
mapping es inmutable, cambiar un analyzer exige: borrar el índice, recrearlo, reindexar.
Durante ese hueco **la búsqueda devuelve cero resultados**, y devolver cero sin error es
el peor modo de fallo posible.

El patrón profesional: la aplicación escribe y lee contra un **alias**; los índices reales
llevan versión.

```
clinical-concepts        (alias)  →  clinical-concepts-v3  (índice real)
```

Reindexar pasa a ser: crear `v4`, poblarlo, mover el alias atómicamente, borrar `v3`.
Cero caída, y rollback instantáneo si algo salió mal.

**Señal de urgencia:** el primer cambio de mapping con usuarios reales del otro lado.

### Suite de tests de frontend

`ui/` no tiene ni un test. El build tipa en modo estricto y la verificación fue manual en
navegador, pero un cambio puede romper el resaltado, el debounce o la navegación por
teclado sin que nada lo detecte.

Lo que más falta cubrir, en orden: que `ResultList` no interprete HTML del servidor (es
una defensa de XSS y hoy nada la protege de una regresión), que las respuestas viejas se
descarten, y que el combobox se navegue con teclado.

Herramientas: Vitest + Testing Library para componentes, Playwright para el flujo completo.

**Señal de urgencia:** la segunda persona que toque el frontend.

### Tests unitarios que no necesiten Docker

Los 33 tests son de **integración**: sin el stack arriba, se saltean. Eso significa que
hoy no existe una comprobación rápida que corra en segundos.

Los constructores de `search.py` son funciones puras que devuelven diccionarios. Se pueden
testear sin Elasticsearch, y ahí es donde vive la lógica de boosts y de separación entre
filtro y scoring. Lo mismo `indexer.to_document`.

**Señal de urgencia:** la primera vez que esperes 48 segundos para saber si rompiste algo.

### Integración continua

No hay CI. Los tests corren cuando alguien se acuerda.

Un workflow de GitHub Actions con Elasticsearch como service container: lint, typecheck,
tests de Python, build de la UI y tests de frontend. Que el estado del repositorio sea un
hecho verificable y no una afirmación del README.

**Señal de urgencia:** el primer commit que rompa algo sin que nadie se entere.

### Linting y formato automáticos

Sin `ruff`, sin `mypy`, sin `pre-commit`. El código está bien escrito, pero por disciplina
personal, no por una barrera.

`ruff check` + `ruff format` + `mypy --strict` sobre `app/`, enganchados en `pre-commit`.
El código ya está tipado; `mypy` es casi gratis.

**Señal de urgencia:** ya. Cuesta una tarde y no hay que volver a discutirlo.

---

## P2 — Lo que hace que un proyecto se mantenga

### Empaquetar la API

La API corre en el host contra el Elasticsearch de Docker. Reproducirla exige Python
3.14, un entorno virtual con nombre particular y comandos de PowerShell.

Un `Dockerfile` multi-stage para la API, otro para servir el build de la UI con nginx, y
los dos como servicios en `compose.yaml`. `docker compose up` levanta el sistema entero.
Eso convierte "andá a leer el README" en un comando.

### Logging estructurado y correlación de peticiones

Hoy los errores se tragan en silencio. `index_concept` captura `Exception` y devuelve
`False` sin registrar **por qué** falló. Cuando `pending_index` quede en `true`, no vas a
tener forma de saber si fue un timeout, un error de mapping o una credencial vencida.

Ese `except Exception: return False` es la decisión correcta — no rechazar una edición ya
commiteada — pero le falta la otra mitad: dejar registro.

Logging JSON con un ID de correlación por petición, y el error real en el log aunque la
respuesta HTTP sea 200.

### Observabilidad

`/health` responde si los componentes están vivos. No dice si el sistema está **sano**:
cuántas búsquedas por minuto, cuál es la latencia p95, cuántas filas llevan pendientes
más de cinco minutos.

Métricas de Prometheus vía `prometheus-fastapi-instrumentator`, más un contador de
`pending_index` como gauge. Una fila pendiente hace treinta segundos es normal; una
pendiente hace una hora es un incidente, y hoy nada los distingue.

### Registro de decisiones de arquitectura

Las decisiones buenas de este proyecto están explicadas en comentarios de código y en
prosa de la documentación. Eso funciona mientras el autor se acuerde.

Un directorio `docs/adr/` con un archivo por decisión — contexto, alternativas, decisión,
consecuencias — hace que la próxima persona (o vos en seis meses) no reabra una discusión
ya cerrada.

Candidatas evidentes: por qué dos almacenes y no solo Elasticsearch; por qué marcar sucio
antes de indexar; por qué los filtros van en contexto `filter`; por qué SQLite.

### Higiene del repositorio

Falta lo básico de un repositorio público:

- **`LICENSE`** — sin licencia, nadie puede usar el código legalmente, aunque esté visible.
- **`CHANGELOG.md`** — qué cambió entre versiones.
- **`CONTRIBUTING.md`** — cómo levantar el entorno y cuál es el estándar de un cambio.
- **Plantillas de issue y PR** — que la información llegue completa la primera vez.
- **Versionado semántico** — hoy la API declara `0.1.0` y nada la mueve.

### Generar los tipos del frontend desde OpenAPI

`ui/src/types.ts` replica a mano lo que `app/schemas.py` ya define. Dos fuentes de verdad
para el mismo contrato, y nada las obliga a coincidir: agregar un campo en Pydantic y
olvidarlo en TypeScript no rompe el build, rompe en runtime.

FastAPI ya publica `/openapi.json`. `openapi-typescript` genera los tipos desde ahí, en el
paso de build.

### Forzar la máquina de estados de curaduría

Los cuatro valores de `curation_status` se validan. Las transiciones no: un concepto puede
saltar de `draft` a `approved` sin pasar por revisión.

Una capa de servicio con la tabla de transiciones válidas, `409` en una transición ilegal,
y tests por cada arista.

### Restricciones en la base

La validación de Pydantic protege la puerta HTTP. No protege un script que abra la base
directamente. Faltan: `CHECK` sobre `curation_status` y `type`, y un índice único parcial
que impida dos descripciones preferidas activas en el mismo idioma para el mismo concepto.

---

## P3 — Solo con volumen o usuarios reales

### PostgreSQL

SQLite admite un escritor a la vez. Con workers concurrentes vas a ver
`database is locked`.

Nada en `models.py` ni en `db.py` es específico de SQLite: el cambio es la URL de conexión
más el driver. Que sea barato es el resultado de una decisión de diseño, no una casualidad.

**Señal de urgencia:** el primer `database is locked` en un log.

### Indexación asincrónica con tabla de outbox

La indexación ocurre dentro del request. Si Elasticsearch está lento, el curador espera.

El patrón: la transacción escribe la fila **y** un registro de outbox atómicamente; un
worker consume el outbox y indexa con reintentos y backoff. `pending_index` ya es media
implementación de esta idea; lo que falta es quién ejecuta el paso.

### Paginación en la UI

La UI trae hasta 25 resultados y ahí queda. Con miles de conceptos hace falta paginar o
scroll infinito. La API ya soporta `limit` y `offset`.

### Sinónimos gestionados con `synonym_graph`

Hoy los sinónimos son filas de `descriptions`. Un filtro `synonym_graph` permitiría que
"IAM" y "infarto agudo de miocardio" se traten como equivalentes en tiempo de consulta,
editables sin recrear el índice.

### Benchmarks reproducibles

No hay línea base de rendimiento. Cuánto tarda indexar 10.000 conceptos, cuál es el p95 de
una búsqueda con facetas, cuánto pesa el índice.

Registrar configuración, versiones, hardware, repeticiones, warm-up, documentos por
segundo, y p50/p95 de consulta. **Excluir la generación de datos del cronometraje de la
indexación**, y registrar el límite de visibilidad por separado: si no, el tiempo de
refresh cambia en silencio el significado del throughput.

Un número de rendimiento sin su configuración al lado no es un dato, es una anécdota.

### Auditoría de accesibilidad con lector de pantalla

El marcado usa roles ARIA correctos: `combobox`, `listbox`, `option`, `aria-expanded`,
`aria-selected`, `aria-pressed`, foco visible, `role="alert"` en los errores.

Marcado correcto **no es lo mismo** que auditoría. Nadie lo probó con NVDA ni con VoiceOver.

---

## Lo que este proyecto ya hace bien

Vale registrarlo, porque en un backlog todo parece deuda:

- **Los tests encontraron bugs reales**, no cobertura decorativa. Dos, documentados con su
  causa raíz.
- **Los fallos se hacen visibles en vez de esconderse.** `pending_index`, `/admin/reconcile`
  y la franja de estado son la misma idea aplicada tres veces.
- **El bulk se inspecciona item por item.** Una petición bulk puede devolver HTTP 200 con
  documentos fallados adentro; contarlos es la diferencia entre reportar y mentir.
- **El resaltado no usa `dangerouslySetInnerHTML`.** Es la decisión correcta sobre XSS
  tomada sin que nadie la exigiera.
- **`dynamic: strict` en el mapping.** La sorpresa aparece al escribir, no seis meses
  después cuando una consulta devuelve mal.
- **La documentación distingue lo verificado de lo supuesto**, y nombra sus propios
  límites.

Eso es más de lo que tienen muchos proyectos con CI y badges.
