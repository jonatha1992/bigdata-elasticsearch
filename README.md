# Laboratorio de Elasticsearch

Proyecto personal de aprendizaje sobre Elasticsearch: ingesta, indexación, búsqueda,
agregación y almacenamiento. No hay trabajo académico de por medio.

El repo contiene **dos entregables** sobre la misma infraestructura Docker:

| Entregable | Estado | Qué ejercita |
|---|---|---|
| [**Curaduría de terminología clínica**](#1-curaduría-de-terminología-clínica) | Funcionando | Elasticsearch como **motor de búsqueda**: analyzers, relevancia, autocompletado. Más FastAPI, SQLite y React |
| [**Laboratorio de eventos sintéticos**](#2-laboratorio-de-eventos-sintéticos) | Documentado, sin implementar | Elasticsearch como **motor analítico**: agregaciones, histogramas, benchmarks |

Son las dos mitades del mismo motor. La primera está construida y verificada; la
segunda tiene diseño y criterios de aceptación, pero su generador de Python nunca se
escribió.

## Infraestructura común

Elasticsearch y Kibana corren en Docker, fijados en 9.5.3. Iniciá Docker Desktop y
después:

```powershell
cd D:\Repositorio\bigdata-elasticsearch
docker compose up -d --pull never
docker compose ps -a
```

`--pull never` usa las imágenes ya descargadas. En una máquina nueva, traelas primero
con `docker compose pull`.

- Kibana: <http://localhost:5601>, usuario `elastic`.
- API de Elasticsearch: <http://localhost:9200>, mismas credenciales.
- Contraseña: el valor de `ELASTIC_PASSWORD` en tu `.env` local. **No** uses
  `KIBANA_PASSWORD`: esa es de la cuenta de servicio interna de Kibana.
- Una petición sin autenticar debe devolver HTTP 401.

Ambos puertos se publican solo en `127.0.0.1`. Es un laboratorio local que usa
únicamente HTTP; no lo expongas sin revisar antes el diseño del despliegue.

Detener conservando los datos:

```powershell
docker compose down
```

Evitá `down -v`: borra los volúmenes. Cambiar solo `ELASTIC_PASSWORD` en `.env` no
cambia la contraseña ya almacenada en un clúster existente.

Detalles de configuración, límites de recursos y recuperación en
[local-stack.md](docs/local-stack.md). Evidencia de autenticación en
[access-and-verification.md](docs/access-and-verification.md).

---

## 1. Curaduría de terminología clínica

Servicio FastAPI sobre dos almacenes: **SQLite** para la decisión editorial,
**Elasticsearch** para la búsqueda. Modelo de conceptos clínicos tipo SNOMED CT, con
una UI de curaduría en React + TypeScript.

Es el camino que ejercita el stack completo de una posición backend: API REST, Docker,
Linux, Elasticsearch, y el problema real de mantener dos almacenes sincronizados.

### Levantar

```powershell
# 1. Infraestructura
docker compose up -d --pull never

# 2. Cargar datos de ejemplo (una vez)
.\.vennv\Scripts\python.exe -m scripts.seed --reset

# 3. API
.\.vennv\Scripts\python.exe -m uvicorn app.main:app --reload

# 4. UI, en otra terminal
cd ui
npm install
npm run dev
```

- API y documentación interactiva: <http://127.0.0.1:8000/docs>
- UI de curaduría: <http://localhost:5173>

Vite escucha en `localhost`, que en Windows resuelve a IPv6. `127.0.0.1:5173` puede no
responder aunque el servidor esté arriba.

### Probalo

Buscá `hipertension` sin tilde. Encuentra "Hipertensión arterial". Escribí `diabetis`
con error de tipeo: encuentra las tres diabetes. Buscá `EPOC`: aparece por sinónimo,
aunque esa sigla no está en el nombre completamente especificado.

Después abrí el desplegable "¿Cómo se analiza esta consulta?" y mirá en qué tokens se
parte lo que escribiste. Ahí está la explicación de todo lo anterior.

### Verificación

```console
$ .\.vennv\Scripts\python.exe -m pytest tests/test_curation_api.py tests/test_stack.py -q
33 passed in 48.09s
```

Al 2026-09-06: 33 tests en verde, 20 conceptos cargados y conciliados contra
Elasticsearch 9.5.3, y la UI probada en navegador real a 1440px y 390px.

### Documentación

- [curation-api.md](docs/curation-api.md): diseño del índice, analyzers, endpoints,
  ejemplos, los dos bugs que encontraron los tests, y límites conocidos.
- [curation-ui.md](docs/curation-ui.md): componentes, decisiones de diseño y evidencia
  de verificación en navegador.
- [architecture.md](docs/architecture.md): diagramas de despliegue, flujo de datos y
  modelo conceptual.

---

## 2. Laboratorio de eventos sintéticos

Diseño de un flujo que va de eventos sintéticos de tienda online a documentos
validados, métricas conciliadas y un dashboard. **Está documentado, no implementado.**

- [Requisitos de producto (PRD)](docs/prd.md): objetivos, alcance y criterios de aceptación.
- [Diagramas de arquitectura](docs/architecture.md): flujo de datos, secuencia de reintentos y modelo de eventos.
- [Dashboard de demostración](dashboard/index.html): ejemplos sintéticos interactivos; funciona sin Docker.
- [Guía de presentación](docs/dashboard.md): filtros, definiciones de métricas y seguimiento en Kibana.

El dashboard es un demostrador offline, no una conexión a Elasticsearch.
`tests/test_events.py` importa un `events.py` que no existe: esos tests fallan si
corrés la suite completa. Es el contrato del generador que quedó sin escribir.

Para correr solo lo que pasa:

```powershell
.\.vennv\Scripts\python.exe -m pytest tests/test_curation_api.py tests/test_stack.py -q
```

## Entorno

- Directorio del proyecto: `D:\Repositorio\bigdata-elasticsearch`.
- Entorno virtual: `.vennv` (el nombre pedido por el usuario).
- Python 3.14.6; pip 26.1.2; entorno aislado confirmado.
- Node 22.23.2; npm 10.9.8 (solo para la UI).
- Windows 11 Pro, Ryzen 7 5700G, 16 procesadores lógicos, 31.3 GB de RAM.
- Docker CLI 29.7.2, Compose 5.3.1. WSL versión 2 por defecto.

Activar el entorno virtual en PowerShell:

```powershell
.\.vennv\Scripts\Activate.ps1
```

La ejecución directa funciona sin activarlo:

```powershell
.\.vennv\Scripts\python.exe --version
```

Dependencias de Python fijadas en `requirements.txt` (FastAPI, SQLAlchemy, cliente
`elasticsearch` 9.5.0, pytest). Para reconstruir el entorno:

```powershell
.\.vennv\Scripts\python.exe -m pip install -r requirements.txt
```

### Estructura

```
app/          servicio FastAPI (modelos, índice, búsqueda, routers)
ui/           interfaz React + TypeScript
scripts/      carga del fixture
seed/         20 conceptos clínicos de ejemplo
tests/        tests de integración
dashboard/    demostrador offline del laboratorio de eventos
docs/         documentación
compose.yaml  Elasticsearch + Kibana
```

## Evaluación de NotebookLM

Notebook: [BIG DATA](https://notebooklm.google.com/notebook/f73407c1-9c7f-4146-b94d-80ab5bbfd62e),
32 fuentes indexadas. Se inspeccionó el inventario y se leyeron directamente las
fuentes relevantes; esto no implica que se haya auditado cada una.

- La transcripción sobre mappings cubre mappings explícitos y dinámicos, text versus
  keyword, analizadores, objetos anidados y reindexación. Es el material que más se
  aplica al índice de conceptos clínicos.
- La transcripción sobre agregaciones cubre métricas, buckets, subagregaciones y
  pipeline aggregations.
- La guía de instalación de ELK apunta a Fedora 23 y hace referencia a Kibana 4. Sus
  instrucciones no sirven como guía de configuración actual.
- La fuente "Introduccion a Elasticsearch 2026 - Aprender BIG DATA desde cero" devuelve
  solo su título (64 caracteres), no contenido didáctico.
- "Tecnologias y Arquitecturas de Big Data" contiene una conversación previa con IA
  sobre un portfolio personal. Es contexto, no autoridad técnica.
- La transcripción sobre mappings omite una salvedad importante: la detección numérica
  para cadenas numéricas está deshabilitada por defecto. Verificá contra la
  documentación oficial en vez de copiar la transcripción.

## Referencias oficiales

- [Dynamic field mapping](https://www.elastic.co/docs/manage-data/data-store/mapping/dynamic-field-mapping)
- [Text analysis](https://www.elastic.co/docs/manage-data/data-store/text-analysis)
- [Docker installation](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-elasticsearch-docker-basic)
- [Kibana version compatibility](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-kibana-with-docker)
- [Clusters, nodes, and shards](https://www.elastic.co/docs/deploy-manage/distributed-architecture/clusters-nodes-shards)
- [Near-real-time search](https://www.elastic.co/docs/manage-data/data-store/near-real-time-search)
- [Small-cluster resilience](https://www.elastic.co/docs/deploy-manage/production-guidance/availability-and-resilience/resilience-in-small-clusters)
