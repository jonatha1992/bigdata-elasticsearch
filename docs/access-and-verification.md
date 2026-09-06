# Registro de acceso y verificación

Este documento registra cómo iniciar sesión en el stack local y la evidencia de
verificación en vivo recogida el 2026-09-05. Es factual: cada afirmación de más abajo
se comprobó contra el stack en ejecución, no se asumió.

## Quién es el administrador

La cuenta de administrador es el superusuario integrado de Elasticsearch **`elastic`**.

| Superficie | URL | Usuario | Origen de la contraseña |
|---|---|---|---|
| Interfaz web de Kibana | <http://localhost:5601> | `elastic` | `ELASTIC_PASSWORD` en el `.env` local |
| API de Elasticsearch | <http://localhost:9200> | `elastic` | `ELASTIC_PASSWORD` en el `.env` local |

### Por qué `elastic` y no `kibana_system`

- `elastic` es una cuenta reservada e integrada que viene con el rol `superuser`.
  Su contraseña se define desde la variable de entorno `ELASTIC_PASSWORD` cuando el
  clúster arranca por primera vez con `xpack.security.enabled: "true"` (ver `compose.yaml`).
- `kibana_system` es una **cuenta de servicio** interna. Kibana la usa para hablar con
  Elasticsearch en tu nombre. No es un login humano. **No** uses `KIBANA_PASSWORD` para
  iniciar sesión en la interfaz de Kibana.

La contraseña nunca se imprime acá. Se verifica de forma indirecta, desde dentro del
propio entorno del contenedor, así el secreto no queda expuesto.

## Evidencia de verificación en vivo (2026-09-05)

Entorno:

- Motor de Docker: `29.7.2`
- Servicios de Compose presentes: solo `elasticsearch` (ver la brecha más abajo)

### 1. Elasticsearch está arriba y la seguridad se aplica

Una petición sin autenticar a la raíz de la API devuelve `401`, como está diseñado:

```console
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:9200
HTTP 401
```

El cuerpo de la respuesta confirma la excepción de seguridad:

```json
{"error":{"root_cause":[{"type":"security_exception",
"reason":"missing authentication credentials for REST request [/]"}],
"status":401}}
```

### 2. La credencial de administrador `elastic` funciona y es superusuario

Autenticado desde dentro del contenedor (la contraseña se lee de su propio entorno,
nunca se expone al host):

```console
$ docker exec bigdata-elasticsearch-elasticsearch-1 bash -c \
    'curl -s -o /dev/null -w "HTTP %{http_code}\n" \
     -u "elastic:$ELASTIC_PASSWORD" http://localhost:9200/_security/_authenticate'
HTTP 200
```

Rol confirmado como `superuser`:

```json
{"username":"elastic","roles":["superuser"],"enabled":true,
"authentication_realm":{"name":"reserved","type":"reserved"}}
```

### 3. El stack completo se inició y Kibana está sirviendo

`docker compose up -d` creó los contenedores `setup` y `kibana`. El job `setup` corrió
una vez y salió limpiamente, lo que significa que definió correctamente la contraseña de
la cuenta de servicio `kibana_system`:

```console
$ docker inspect -f '{{.State.ExitCode}}' bigdata-elasticsearch-setup-1
0
$ docker logs bigdata-elasticsearch-setup-1
{}
```

Los tres servicios ya están presentes, con `setup` finalizado (0) como corresponde:

```console
$ docker compose ps -a
NAME                                    SERVICE         STATUS
bigdata-elasticsearch-elasticsearch-1   elasticsearch   Up (healthy)
bigdata-elasticsearch-kibana-1          kibana          Up (healthy)
bigdata-elasticsearch-setup-1           setup           Exited (0)
```

Kibana reporta estado disponible y sirve la página de login:

```console
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:5601/api/status
HTTP 200
$ curl -s http://localhost:5601/api/status | grep -oE '"level":"[a-z]+"'
"level":"available"
```

### 4. `elastic` se autentica a través de Kibana como administrador

Una API de Kibana exclusiva de administración (spaces) acepta la credencial `elastic` de
punta a punta:

```console
$ curl -s -o /dev/null -w "HTTP %{http_code}\n" \
    -u "elastic:$ELASTIC_PASSWORD" -H "kbn-xsrf: true" \
    http://<kibana>:5601/api/spaces/space
HTTP 200
```

## Reverificación (2026-09-06)

El stack se volvió a verificar corriendo, y esta vez también desde una aplicación:

```console
$ docker compose ps -a
elasticsearch   Up (healthy)   127.0.0.1:9200->9200/tcp
kibana          Up (healthy)   127.0.0.1:5601->5601/tcp
setup           Exited (0)
```

La API de curaduría autentica contra Elasticsearch usando la misma credencial `elastic`,
leída de `ELASTIC_PASSWORD`. Su endpoint de salud lo confirma:

```json
{"api":"ok","database":"ok","elasticsearch":"9.5.3",
 "index":"clinical-concepts","index_exists":true,"pending_index":0}
```

El servicio **se niega a arrancar contra Elasticsearch sin contraseña**: si
`ELASTIC_PASSWORD` no está definida, `get_client()` lanza un error explícito en vez de
mandar peticiones anónimas que fallarían con un 401 confuso más adelante.

Los 33 tests de integración del repo pasaron contra este stack, incluyendo los cuatro
preexistentes que verifican el 401 sin autenticar, las versiones de los servicios, la
salud del clúster y la página de login de Kibana.

Durante la sesión el contenedor de Elasticsearch salió con código 137 y se relevantó.
Diagnóstico completo en [local-stack.md](local-stack.md); no fue falta de memoria.

## Cómo entrar

1. Abrí <http://localhost:5601>
2. Usuario: `elastic`
3. Contraseña: el valor de `ELASTIC_PASSWORD` de tu `.env` local

Para detener el laboratorio conservando los datos:

```powershell
docker compose down
```

No uses `docker compose down -v`; borra los volúmenes de datos.
