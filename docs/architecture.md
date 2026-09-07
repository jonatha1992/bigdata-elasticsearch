# Arquitectura del sistema

Actualizado el 2026-09-06.

Un solo sistema: **curaduría de terminología clínica**. Un servicio FastAPI sobre dos
almacenes — SQLite guarda la decisión editorial, Elasticsearch guarda una proyección
buscable de esa decisión — con una interfaz React para el curador.

Todo lo que se dibuja acá existe y corre. No hay diagramas de intención en este
documento: lo propuesto y no construido vive en el
[backlog de ingeniería](engineering-backlog.md).

| Documento | Qué contiene |
|---|---|
| Este | Contexto, componentes, despliegue, secuencias, pipelines, flujo de curaduría |
| [data-model.md](data-model.md) | DER, esquema físico y el documento de Elasticsearch |
| [curation-api.md](curation-api.md) | Endpoints, diseño del índice, ejemplos |
| [curation-ui.md](curation-ui.md) | Componentes de la UI y decisiones de frontend |
| [prd.md](prd.md) | Requisitos y criterios de aceptación |

---

## 1. Contexto

Quién usa el sistema y contra qué habla.

```mermaid
flowchart LR
    Curator["Curador de terminología"]
    Ops["Operador del laboratorio"]

    subgraph System["Sistema de curaduría clínica"]
        UI["UI de curaduría<br/>React + TypeScript"]
        API["API de curaduría<br/>FastAPI"]
        SQL[("SQLite<br/>registro editorial")]
        ES[("Elasticsearch<br/>índice de búsqueda")]
    end

    Kibana["Kibana<br/>inspección de índices"]

    Curator -->|"busca, revisa, decide"| UI
    UI -->|"HTTP /api"| API
    API -->|"SQLAlchemy"| SQL
    API -->|"HTTP autenticado"| ES
    Ops -->|"conciliar, reindexar"| API
    Ops -->|"inspeccionar mapping y documentos"| Kibana
    Kibana --> ES
```

El curador nunca habla con Elasticsearch directamente. Kibana es una herramienta de
diagnóstico para el operador, no parte del camino del producto.

---

## 2. Componentes

Qué módulo hace qué, y quién depende de quién.

```mermaid
flowchart TD
    subgraph Front["ui/ — React 18 + TypeScript 5.7 + Vite 6"]
        App["App.tsx<br/>estado y orquestación"]
        SearchBar["SearchBar<br/>búsqueda y autocompletado"]
        Facets["Facets<br/>filtros con conteos"]
        ResultList["ResultList<br/>resultados y resaltado"]
        ConceptPanel["ConceptPanel<br/>detalle y cambio de estado"]
        StatusStrip["StatusStrip<br/>conciliación visible"]
        AnalyzerPeek["AnalyzerPeek<br/>tokens de la consulta"]
        ApiClient["api.ts<br/>cliente HTTP tipado"]
    end

    subgraph Back["app/ — FastAPI y SQLAlchemy 2.0"]
        Main["main.py<br/>arranque, CORS, /health"]
        RConcepts["routers/concepts.py<br/>CRUD"]
        RSearch["routers/search.py<br/>búsqueda, sugerencias, analyze"]
        RAdmin["routers/admin.py<br/>índice, reindex, reconcile"]
        Schemas["schemas.py<br/>contrato Pydantic"]
        Models["models.py<br/>ORM Concept y Description"]
        Indexer["indexer.py<br/>proyección a documento"]
        Search["search.py<br/>constructores de query"]
        EsIndex["es_index.py<br/>mapping y analyzers"]
        EsClient["es_client.py<br/>cliente y ciclo del índice"]
        Db["db.py<br/>engine y sesiones"]
        Config["config.py<br/>settings desde .env"]
    end

    SQL[("curation.db")]
    ES[("clinical-concepts")]

    App --> SearchBar
    App --> Facets
    App --> ResultList
    App --> ConceptPanel
    App --> StatusStrip
    App --> AnalyzerPeek
    SearchBar --> ApiClient
    Facets --> ApiClient
    ResultList --> ApiClient
    ConceptPanel --> ApiClient
    StatusStrip --> ApiClient
    AnalyzerPeek --> ApiClient
    ApiClient -->|"proxy /api de Vite"| Main
    Main --> RConcepts
    Main --> RSearch
    Main --> RAdmin
    RConcepts --> Models
    RConcepts --> Indexer
    RConcepts --> Schemas
    RSearch --> Search
    RSearch --> Schemas
    RAdmin --> Indexer
    RAdmin --> EsClient
    RAdmin --> Models
    Indexer --> Models
    Indexer --> EsClient
    Search --> EsIndex
    EsClient --> EsIndex
    EsClient --> Config
    Models --> Db
    Db --> Config
    Db --> SQL
    EsClient --> ES
```

Tres separaciones deliberadas:

- **`schemas.py` no es `models.py`.** La forma de la base y la forma del cable cambian
  por motivos distintos. Mezclarlas obliga a versionar la API cada vez que se agrega una
  columna.
- **`search.py` no habla con la base.** Construye cuerpos de consulta; el router los
  ejecuta. Los constructores se pueden testear sin Elasticsearch arriba.
- **`indexer.py` es el único que sabe proyectar.** Un solo lugar decide cómo una fila se
  convierte en documento, así que el mapping y la proyección no pueden divergir en
  silencio.

---

## 3. Despliegue

Verificado el 2026-09-06 de punta a punta: navegador → Vite → FastAPI → SQLite y
Elasticsearch.

```mermaid
flowchart LR
    Curator["Curador y navegador"]

    subgraph Host["Host Windows 11 — todo publicado en loopback"]
        subgraph Node["Node 22"]
            Vite["Vite 6 :5173<br/>servidor de desarrollo"]
        end
        subgraph Py["Python 3.14 — entorno .vennv"]
            API["uvicorn :8000<br/>FastAPI"]
            DB[("curation.db<br/>archivo SQLite")]
        end
        subgraph Docker["Red Docker — proyecto bigdata-elasticsearch"]
            ES["Elasticsearch 9.5.3<br/>nodo único :9200"]
            Setup["setup<br/>corre una vez y sale"]
            Kibana["Kibana 9.5.3 :5601"]
            ESV[("volumen elasticsearch-data")]
            KV[("volumen kibana-data")]
        end
    end

    Curator -->|"HTTP"| Vite
    Vite -->|"proxy /api, sin CORS"| API
    API -->|"SQLAlchemy"| DB
    API -->|"HTTP básico autenticado"| ES
    Curator -->|"diagnóstico"| Kibana
    Setup -->|"fija la contraseña de kibana_system"| ES
    Setup -->|"su éxito habilita el arranque"| Kibana
    Kibana -->|"credencial kibana_system"| ES
    ES --- ESV
    Kibana --- KV
```

Notas de despliegue que importan:

- **La API no está en contenedor.** Corre en el host contra el Elasticsearch de Docker.
  Es lo cómodo para desarrollar con recarga; empaquetarla es trabajo pendiente.
- **Vite redirige `/api/*` y saca el prefijo.** El navegador ve un solo origen, así que
  no hay CORS en desarrollo. Es también la forma en que un reverse proxy serviría a los
  dos en producción.
- **Elasticsearch: 4 GiB de límite, heap de JVM de 2 GiB.** Kibana: 2 GiB, heap de Node
  de 1.5 GiB. Los volúmenes nombrados sobreviven a `docker compose down`; `down -v` los
  borra.
- **Solo HTTP, solo loopback.** No es una plantilla de producción. Ver
  [local-stack.md](local-stack.md).
- Nada de la capa Python es específico de SQLite: pasar a PostgreSQL es cambiar
  `database_url` e instalar el driver.

---

## 4. Camino de escritura: dos almacenes, una decisión

El problema central del sistema. Una edición tiene que llegar a dos lugares y el segundo
puede fallar.

```mermaid
sequenceDiagram
    actor Curator as Curador
    participant UI as UI React
    participant API as FastAPI
    participant DB as SQLite
    participant ES as Elasticsearch

    Curator->>UI: Cambia el estado de curaduría
    UI->>API: PATCH /concepts/{id}
    API->>DB: Aplica cambios y marca pending_index = true
    DB-->>API: commit confirmado
    Note over DB: La decisión editorial ya está a salvo

    API->>ES: index(id, documento proyectado, refresh=wait_for)

    alt Elasticsearch confirma
        ES-->>API: 200 acknowledged
        API->>DB: pending_index = false, indexed_at = ahora
        API-->>UI: 200 con pending_index = false
    else Elasticsearch falla o no responde
        Note over API: Un fallo de índice NO rechaza una edición ya commiteada
        API-->>UI: 200 con pending_index = true
        Note over DB: La fila queda marcada como reparable
    end

    UI->>API: GET /admin/reconcile
    API->>DB: count de conceptos y de pendientes
    API->>ES: count de documentos
    API-->>UI: in_sync = false si difieren
    UI-->>Curator: La franja superior se pone en alerta
```

Cuatro decisiones que vale la pena entender:

1. **La fila se marca sucia ANTES de indexar.** Si el proceso muere entre los dos pasos,
   queda evidencia. Marcarla después dejaría deriva invisible, que es el peor de los
   estados: incorrecto y silencioso.
2. **Un fallo de indexación no rechaza la edición.** El curador ya decidió. Perder esa
   decisión por una caída de Elasticsearch es peor que servir un índice atrasado un rato.
3. **`refresh=wait_for` en vez de `refresh=true`.** Espera al refresh natural en lugar de
   forzar uno. La escritura es visible cuando responde, sin castigar al índice con un
   refresh por documento.
4. **La desincronización se muestra, no se esconde.** `StatusStrip` la pone en la cara
   del curador en vez de dejar que la descubra por una búsqueda que calladamente devuelve
   de menos.

---

## 5. Camino de lectura: de la tecla al resultado

```mermaid
sequenceDiagram
    actor Curator as Curador
    participant UI as UI React
    participant API as FastAPI
    participant ES as Elasticsearch

    Curator->>UI: Escribe "hipertension"
    Note over UI: useDebounced espera a que deje de tipear
    UI->>API: GET /search/suggest?q=hipertension
    API->>ES: multi_match bool_prefix sobre suggest y sus n-gramas
    ES-->>API: sugerencias por prefijo
    API-->>UI: SuggestResponse
    UI-->>Curator: Desplegable navegable con flechas

    Curator->>UI: Enter
    UI->>API: GET /search?q=hipertension&semantic_tag=trastorno
    Note over API: build_filters separa filtros de scoring
    API->>ES: bool con must de texto y filter de términos
    ES-->>API: hits, highlight y aggregations
    API-->>UI: SearchResponse con facetas y fragmentos
    Note over UI: El resaltado se reconstruye como nodos mark reales
    UI-->>Curator: Resultados, facetas con conteos y resaltado

    opt El curador no encuentra lo que busca
        Curator->>UI: Abre el inspector de análisis
        UI->>API: GET /search/analyze?text=...&analyzer=clinical_text
        API->>ES: _analyze
        ES-->>API: tokens con posiciones y offsets
        API-->>UI: AnalyzeResponse
        UI-->>Curator: Los tokens exactos que produjo la consulta
    end
```

**Las respuestas viejas se descartan.** Cada efecto de la UI lleva una bandera
`cancelled`: si la respuesta lenta de una consulta anterior llega después de una nueva,
se tira. Sin eso, escribís rápido y la pantalla te muestra el resultado de hace tres
letras.

El resaltado **nunca** usa `dangerouslySetInnerHTML`. Elasticsearch devuelve los
fragmentos con `<mark>` ya insertado, y ese fragmento contiene texto que cargó un
curador. Inyectarlo como HTML crudo es un agujero de XSS a cambio de una palabra en
negrita.

---

## 6. Pipeline de análisis de texto

Acá se decide si una búsqueda encuentra algo. El mismo texto se trata de tres formas
distintas, a propósito.

```mermaid
flowchart LR
    Input["Texto de entrada:<br/>Hipertensión arterial"]

    subgraph CT["clinical_text — recall alto"]
        CT1["standard tokenizer"] --> CT2["lowercase"] --> CT3["asciifolding"] --> CT4["spanish_stop"] --> CT5["stemmer light_spanish"]
    end

    subgraph CE["clinical_exact — precisión"]
        CE1["standard tokenizer"] --> CE2["lowercase"] --> CE3["asciifolding"]
    end

    subgraph CK["clinical_keyword — normalizador"]
        CK1["sin tokenizar:<br/>toda la cadena"] --> CK2["lowercase"] --> CK3["asciifolding"]
    end

    Input --> CT1
    Input --> CE1
    Input --> CK1

    CT5 --> CTOut["hipertens, arterial<br/>matchea hipertensivo"]
    CE3 --> CEOut["hipertension, arterial<br/>NO matchea hipertensivo"]
    CK3 --> CKOut["hipertension arterial<br/>un solo token"]

    CTOut --> Use1["Caja de búsqueda principal"]
    CEOut --> Use2["Boost de aciertos exactos"]
    CKOut --> Use3["Facetas, filtros y ordenamiento"]
```

Por qué las tres:

- **`asciifolding` no es un detalle.** Los curadores escriben "hipertension" sin tilde
  todo el tiempo. Sin folding, esas consultas devolverían cero en silencio.
- **El stemming sube el recall y baja la precisión.** `clinical_text` colapsa
  "hipertensión" e "hipertensivo" en la misma raíz. Eso encuentra más, pero también
  encuentra cosas que no son exactamente lo que pediste.
- **`clinical_exact` recupera la precisión con boosts.** Un acierto sin stemmear pesa más
  (`fsn.exact^6`) que uno stemmeado (`fsn^4`), así que lo exacto sube al tope sin perder
  lo aproximado.
- **El normalizador no es un analyzer.** No parte el texto: produce un único token con
  toda la cadena. Es lo que hace que una faceta diga "estructura corporal" y no
  "estructura" + "corporal".

Boosts completos, de mayor a menor: `fsn.exact^6`, `preferred_term.exact^5`, `fsn^4`,
`preferred_term^3`, `terms.exact^2`, `terms^1`. Un acierto exacto le gana a uno
stemmeado, y el nombre completamente especificado le gana a un sinónimo.

### Filtros versus scoring

```mermaid
flowchart TD
    Q["Consulta del curador"] --> Split{"¿Qué tipo de cláusula es?"}
    Split -->|"texto libre"| Must["contexto must<br/>multi_match con fuzziness AUTO"]
    Split -->|"tipo semántico, estado, activo"| Filter["contexto filter<br/>term queries"]
    Must --> Score["Aporta al puntaje de relevancia"]
    Filter --> NoScore["NO aporta al puntaje<br/>cacheable por Elasticsearch"]
    Score --> Bool["bool query"]
    NoScore --> Bool
    Bool --> Results["Resultados ordenados<br/>solo por relevancia textual"]
```

Un filtro responde sí o no. No debe influir en qué tan relevante es un documento.
Mezclar las dos cosas es la forma clásica de terminar con rankings sin explicación. Hay
un test que fija esa regla: `test_filters_do_not_change_the_score` compara los puntajes
con y sin filtro y exige que sean idénticos.

---

## 7. Pipeline de indexación y conciliación

Cómo una fila relacional termina siendo un documento buscable, y cómo se repara cuando
no llega.

```mermaid
flowchart TD
    Write["Escritura en la API:<br/>POST o PATCH /concepts"] --> Mark["pending_index = true<br/>y commit en SQLite"]
    Mark --> Project["indexer.to_document<br/>aplana concepto y descripciones activas"]
    Project --> Index["client.index<br/>refresh = wait_for"]

    Index --> Ack{"¿Elasticsearch confirmó?"}
    Ack -->|"sí"| Clear["pending_index = false<br/>indexed_at = ahora"]
    Ack -->|"no"| Dirty["La fila queda marcada.<br/>El curador recibe 200 igual"]

    Clear --> Synced["Estado sincronizado"]
    Dirty --> Recon

    Recon["GET /admin/reconcile"] --> Compare{"¿counts iguales<br/>y pendientes en cero?"}
    Compare -->|"sí"| InSync["in_sync = true"]
    Compare -->|"no"| Drift["in_sync = false<br/>Alerta en la franja de la UI"]

    Drift --> Reindex["POST /admin/reindex"]
    Reindex --> Bulk["helpers.bulk<br/>raise_on_error = false"]
    Bulk --> Inspect["Se inspecciona CADA item,<br/>no el estado HTTP de la petición"]
    Inspect --> PerItem{"¿El item tuvo éxito?"}
    PerItem -->|"sí"| ClearOne["Limpia el flag de esa fila"]
    PerItem -->|"no"| Report["Cuenta el fallo y devuelve<br/>concept_id y error"]
    ClearOne --> Synced
    Report --> Drift
```

**Una petición bulk puede devolver HTTP 200 con documentos fallados adentro.** Reportar
la petición como exitosa sería mentir. Por eso `reindex_pending` clasifica item por item
y solo limpia el flag de las filas que Elasticsearch aceptó de verdad.

`POST /admin/reindex?only_pending=false` reconstruye todos los documentos. Es lo que se
corre después de cambiar el mapping — junto con `scripts/seed.py --reset`, porque los
analyzers y los tipos de campo son inmutables una vez creado el índice.

El contrato de conciliación, en una línea:

```
conceptos_en_base == documentos_en_indice   cuando   pending_index == 0
```

---

## 8. Flujo de trabajo de curaduría

Lo que hace una persona, de punta a punta.

```mermaid
flowchart TD
    Start(["El curador abre la UI"]) --> Load["Carga inicial:<br/>conceptos, facetas y franja de estado"]
    Load --> Check{"¿La franja dice sincronizado?"}
    Check -->|"no"| Repair["Pulsa reparar:<br/>POST /admin/reindex"]
    Repair --> Load
    Check -->|"sí"| Search["Escribe una consulta"]

    Search --> Suggest["Aparecen sugerencias por prefijo"]
    Suggest --> Pick{"¿Encontró el concepto?"}

    Pick -->|"no"| Why["Abre el inspector de análisis"]
    Why --> Understand["Ve los tokens reales de su consulta"]
    Understand --> Refine["Ajusta términos o filtros"]
    Refine --> Search

    Pick -->|"sí"| Open["Abre el panel de detalle"]
    Open --> Review["Revisa FSN, etiqueta semántica<br/>y descripciones"]
    Review --> Decide{"¿Qué decide?"}

    Decide -->|"falta información"| Note["Escribe una nota de curaduría"]
    Decide -->|"pasa a revisión"| ToReview["curation_status = in_review"]
    Decide -->|"aprueba"| Approve["curation_status = approved"]
    Decide -->|"rechaza"| Reject["curation_status = rejected"]

    Note --> Save
    ToReview --> Save
    Approve --> Save
    Reject --> Save

    Save["PATCH /concepts/{id}"] --> Persist["SQLite commitea<br/>y marca pending_index"]
    Persist --> Reindexed{"¿Elasticsearch confirmó?"}
    Reindexed -->|"sí"| Fresh["El resultado refleja el estado nuevo:<br/>indexed_at igual a updated_at"]
    Reindexed -->|"no"| Flagged["La franja avisa que hay pendientes"]
    Flagged --> Repair
    Fresh --> More{"¿Sigue curando?"}
    More -->|"sí"| Search
    More -->|"no"| End(["Fin"])
```

El camino "no lo encontré → miro los tokens → entiendo por qué" es el que convierte a la
búsqueda de caja negra en algo diagnosticable. Es la razón de que `/search/analyze` sea
un endpoint de producto y no una herramienta de debug escondida.

---

## 9. Estados de curaduría

```mermaid
stateDiagram-v2
    [*] --> draft: POST /concepts
    draft --> in_review: el curador lo eleva
    in_review --> approved: cumple los criterios editoriales
    in_review --> rejected: no cumple
    in_review --> draft: vuelve por falta de información
    approved --> in_review: reapertura por revisión posterior
    rejected --> in_review: reapertura con nueva evidencia
    draft --> [*]: DELETE /concepts/id
    approved --> [*]: DELETE /concepts/id
    rejected --> [*]: DELETE /concepts/id
```

**Honestidad sobre esta máquina de estados: hoy no está forzada en código.** Los cuatro
valores de `curation_status` se validan contra el `Literal` de Pydantic, pero cualquier
transición entre ellos se acepta. Las flechas de arriba son la política editorial
prevista, no una invariante del sistema. Forzarla es trabajo pendiente y está en el
[backlog](engineering-backlog.md).

`active` es un eje distinto de `curation_status`: un concepto aprobado puede quedar
inactivo cuando se retira de uso. En SNOMED CT nada se borra, se inactiva. Este modelo
conserva esa idea aunque permita `DELETE` para la limpieza del laboratorio.

---

## 10. Modelo de datos

El DER, el esquema físico y el documento de Elasticsearch viven en
[data-model.md](data-model.md), con la correspondencia campo a campo entre las dos
representaciones.

---

## 11. Límites conocidos de esta arquitectura

- **La indexación es sincrónica.** El paso a Elasticsearch ocurre dentro del request. Un
  sistema en producción lo movería a un worker que consume una tabla de outbox: la
  historia de recuperación es la misma, cambia quién ejecuta el paso.
- **SQLite tiene un solo escritor a la vez.** Alcanza para un curador. Con escrituras
  concurrentes aparece `database is locked`; ese es el momento de PostgreSQL.
- **Sin autenticación en la API.** Cualquiera que llegue a la página puede cambiar
  estados. Es local; poner auth antes de exponerlo a otra máquina.
- **Un solo nodo, cero réplicas.** No se puede demostrar tolerancia a fallos distribuida
  con esta topología, y un experimento multinodo en la misma máquina sigue compartiendo
  el dominio de falla del host.
- **Sin migraciones.** `create_all()` alcanza para arrancar. Alembic va antes del primer
  cambio de esquema sobre datos que importen.

El listado completo con prioridades está en el
[backlog de ingeniería](engineering-backlog.md).
