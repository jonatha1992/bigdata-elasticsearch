# Stack local: alcance, decisión y verificación

## Alcance del producto

El usuario quiere un proyecto personal de aprendizaje de Big Data y autorizó iniciar
Docker y preparar Elasticsearch y Kibana. Esta entrega provee la base local sobre la
que corre el [sistema de curaduría clínica](architecture.md). Los benchmarks y un
clúster multinodo quedan fuera; están en el
[backlog de ingeniería](engineering-backlog.md).

Gobernanza: reclasificado de M a L antes de arrancar los servicios, porque el contrato
global incluye explícitamente autenticación, secretos y topología de despliegue. La
exposición práctica está restringida a un entorno de aprendizaje local. Este único
documento contiene el alcance de producto proporcionado, el ADR, el diseño técnico, las
tareas y el registro de verificación, en lugar de duplicar esos datos entre varios
documentos.

Criterios de aceptación:

- Elasticsearch y Kibana corren en la misma versión fijada, 9.5.3.
- Elasticsearch rechaza peticiones sin autenticar y acepta credenciales locales.
- Kibana reporta estado disponible y sirve su página de login.
- Los puertos publicados se enlazan exclusivamente al loopback IPv4.
- Los datos sobreviven a la recreación de contenedores mediante volúmenes nombrados
  específicos del proyecto.
- El setup termina con éxito antes de que arranque Kibana.
- Las instrucciones de arranque, parada y acceso están documentadas sin publicar secretos.

## ADR: laboratorio Docker autenticado de nodo único

Decisión: usar imágenes Docker oficiales, un nodo de Elasticsearch, Kibana y un servicio
de setup de una sola ejecución. Las alternativas consideradas fueron un despliegue en la
nube y un quickstart sin autenticación. Los contenedores locales encajan con la PC
disponible y permiten experimentos repetibles; la autenticación aporta una base útil de
aprendizaje.

El TLS sobre HTTP está deshabilitado solo para este laboratorio publicado en loopback.
El tráfico dentro de la red Docker del proyecto también es HTTP. Esto no es una plantilla
de despliegue de producción ni para máquinas compartidas. No lo publiques remotamente sin
un diseño aparte de TLS y control de acceso. La autenticación y la autorización siguen
habilitadas.

Usá el administrador integrado `elastic` para la sesión inicial de aprendizaje local.
Kibana se conecta usando `kibana_system`, nunca la cuenta de administrador. La ingesta
futura de la aplicación debería recibir una credencial aparte con el mínimo privilegio.

Las contraseñas alfanuméricas aleatorias e independientes y las claves de cifrado estables
de Kibana se guardan en `.env`, excluido del control de versiones. `.env.example` contiene
solo marcadores vacíos. Estos son secretos de desarrollo local, no un vault de producción;
el usuario del host y los administradores de Docker pueden inspeccionar la configuración
de los contenedores.

## Diseño técnico

- `elasticsearch`: límite de 4 GiB de memoria, heap de JVM de 2 GiB, puerto 127.0.0.1:9200.
- `setup`: 256 MiB como máximo; espera la salud autenticada de ES y después define la
  contraseña de `kibana_system` vía su API de seguridad con un timeout HTTP acotado.
- `kibana`: límite de 2 GiB de memoria, heap de Node de 1.5 GiB, puerto 127.0.0.1:5601;
  espera a que el setup termine con éxito, persiste sus datos y claves de cifrado.
- `elasticsearch-data` y `kibana-data`: volúmenes nombrados con alcance del proyecto
  Compose `bigdata-elasticsearch`.
- La salud de ES espera al menos amarillo: las réplicas pueden quedar sin asignar en un
  solo nodo. Verde es deseable, pero amarillo no equivale a un laboratorio de nodo único
  fallido.
- Los logs de servicio rotan a los 10 MiB con tres archivos por contenedor de larga
  duración.

El motor Linux actual de Docker reporta aproximadamente 15.3 GiB de memoria disponible.
No hace falta cambiar la configuración global de WSL para la configuración inicial.

## Tareas y responsabilidades

1. Orquestador: crear la configuración, las credenciales locales y la documentación.
2. Orquestador: validar Compose; descargar imágenes; iniciar e inspeccionar la salud de los servicios.
3. Revisor independiente: inspeccionar la configuración sin leer secretos; verificar el
   comportamiento público de salud y login, los bindings y el estado de los servicios tras
   el arranque.
4. Orquestador: verificar las APIs autenticadas y la persistencia, después actualizar el handoff.

## Compatibilidad y recuperación

Este proyecto no altera ningún repositorio existente ni las credenciales globales de
Docker. Las versiones de Elasticsearch y Kibana deben mantenerse alineadas. Para detener
el stack, ejecutá `docker compose down`: los volúmenes nombrados se conservan. No agregues
`-v` salvo que quieras descartar intencionalmente todos los datos del laboratorio.
Conservá `.env` junto con los volúmenes; cambiar solo `ELASTIC_PASSWORD` no rota la
contraseña ya almacenada en Elasticsearch. El servicio de setup actualiza `kibana_system`
en los arranques posteriores usando la contraseña de administrador existente. Mantené las
claves de cifrado de Kibana entre reinicios.

Las actualizaciones y regresiones de versión sobre datos persistidos quedan fuera de esta
entrega. Antes de una actualización futura, usá los procedimientos soportados de snapshot
y upgrade.

## Método de validación

Excepción explícita al TDD universal: configuración declarativa y documentación. No se
introduce comportamiento de aplicación ni código Python de producción. RED/GREEN y la
refactorización no aplican a esta entrega de solo configuración. La validación más cercana:
validación del esquema de Compose, arranque real de contenedores, chequeos de autenticación
HTTP, chequeos de estado y login de Kibana, inspección de bindings y persistencia tras la
recreación. Los tests de runtime dependen de Docker y son chequeos de integración, no tests
unitarios rápidos.

Resultados iniciales: la validación del esquema de Compose pasó. La descarga de imágenes
por defecto falló con un error de sesión de inicio del administrador de credenciales de
Windows. Una configuración temporal y aislada de Docker, con una entrada de autenticación
vacía para el registro público, permitió descargas anónimas; las credenciales globales de
Docker no se modificaron.

## Resultados de runtime (2026-09-06)

El stack se verificó corriendo:

```console
$ docker compose ps -a
elasticsearch   Up (healthy)   127.0.0.1:9200->9200/tcp
kibana          Up (healthy)   127.0.0.1:5601->5601/tcp
setup           Exited (0)
```

Los 33 tests de integración del repo pasaron contra este stack. Los criterios de
aceptación declarados más arriba quedaron todos cubiertos por evidencia ejecutada.

### Incidente: salida con código 137

A mitad de la sesión, el contenedor de Elasticsearch salió con código 137 y Kibana quedó
reiniciándose. Diagnóstico:

```console
$ docker inspect bigdata-elasticsearch-elasticsearch-1 \
    --format '{{.State.Status}} exit={{.State.ExitCode}} oom={{.State.OOMKilled}}'
exited exit=137 oom=false restarts=0
```

El código 137 es 128+9, es decir SIGKILL. Suele leerse como falta de memoria, pero acá
`OOMKilled` era `false` y los logs muestran un apagado **ordenado**: `stopping ...`,
`shutting down watcher thread`, `watcher has stopped and shutdown`.

Un proceso que registra su secuencia de apagado recibió SIGTERM antes del SIGKILL. No
fue un crash ni presión de memoria: algo lo detuvo desde afuera, con toda probabilidad
un reinicio de Docker Desktop.

Recuperación: `docker compose up -d --pull never`. Los datos sobrevivieron intactos
porque viven en volúmenes nombrados, que es exactamente para lo que están.

La lección práctica: no leas el 137 como "se quedó sin memoria" sin mirar `OOMKilled` y
los logs. Los dos casos se ven igual desde afuera y se arreglan distinto.

## Dependencias de aplicación (2026-09-06)

Se instalaron por primera vez, para el servicio de curaduría clínica. Están fijadas en
`requirements.txt`.

- `fastapi` 0.141.1, `uvicorn` 0.52.4, `pydantic` 2.13.5, `pydantic-settings` 2.15.0
- `sqlalchemy` 2.0.52
- `elasticsearch` 9.5.0 — versión mayor alineada con el servidor 9.5.3
- `pytest` 9.1.1, `httpx` 0.28.1

Todas resolvieron con wheels para Python 3.14 en Windows; no hizo falta compilar nada.

La UI usa Node 22.23.2 y npm 10.9.8, con React 18, TypeScript 5.7 y Vite 6. Node no es
requisito para la API ni para los tests de Python.
