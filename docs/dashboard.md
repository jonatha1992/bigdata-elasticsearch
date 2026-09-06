# Guía de demostración del dashboard offline

> **Cuál es cuál.** Este documento describe el demostrador **offline del laboratorio de
> eventos sintéticos**: una tienda online, sin backend, con datos de muestra en el
> navegador. Ilustra a Elasticsearch como motor **analítico** (conteos, sumas,
> histogramas).
>
> Si buscás la interfaz que sí está conectada a Elasticsearch, es otra:
> [UI de curaduría clínica](curation-ui.md), que ejercita el motor de **búsqueda**.

## Abrir y presentar

Abrí [dashboard/index.html](../dashboard/index.html) en un navegador. Funciona
directamente desde disco, sin Docker, sin instalación, sin conexión de red y sin
credenciales. La interfaz y su documentación embebida están en inglés. Es un demostrador
de presentación offline, no una aplicación desplegada ni un dashboard de Kibana.

1. Empezá con el intervalo por defecto del 1 al 7 de septiembre de 2026 UTC y todas las categorías.
2. Explicá que todos los números se calculan en el navegador a partir de eventos de
   muestra sintéticos y deterministas. No son mediciones del clúster de Elasticsearch.
3. Seleccioná **Audio** y después **Apply filters**. Todos los indicadores, gráficos y
   filas de productos se actualizan al mismo subconjunto. Las fechas incluyen ambos
   extremos en UTC.
4. Seleccioná un rango de fechas fuera de la semana de muestra para demostrar el estado
   vacío. Usá **Reset** para restaurar la muestra completa. Las fechas invertidas muestran
   un error y conservan los resultados válidos anteriores.
5. Bajá hasta **How an event becomes an insight**. Explicá el pipeline objetivo, la base
   de Docker verificada históricamente y las etapas de Python propuestas.
6. Abrí el [PRD](prd.md) y los [diagramas técnicos](architecture.md) para ver requisitos y
   límites de implementación. Los enlaces Markdown abren los documentos fuente; usá un
   visor de Markdown con soporte de Mermaid para renderizar los cuatro diagramas técnicos.

El dashboard en sí incluye un flujo del sistema siempre visible, que no requiere
renderizador de Mermaid. La impresión desde el navegador está soportada mediante una hoja
de estilos de impresión.

## Contrato de datos y métricas

El fixture de la demo autónoma está implementado en `dashboard/model.js`. Es independiente
del generador de Python propuesto y no satisface sus tests de contrato. La demo asigna a
cada evento una categoría y un producto por comodidad de filtrado; esto no prescribe el
esquema definitivo para eventos de búsqueda o de error.

| Elemento | Definición |
|---|---|
| Total de eventos | Cantidad de registros seleccionados del fixture |
| Eventos de compra | Registros seleccionados cuyo `event_type` es `purchase`; no son pedidos únicos |
| Valor de compras | Suma del `amount` de las compras, almacenado en centavos de USD enteros y mostrado en USD |
| Proporción de errores | Cantidad de errores dividida por todos los eventos seleccionados, por 100; N/A cuando está vacío |
| Eventos a lo largo del tiempo | Conteo por fecha UTC presente en los registros seleccionados |
| Composición de eventos | Conteo y proporción de cada uno de los cuatro tipos de evento; los porcentajes se redondean |
| Ranking de productos | Valor de compras por nombre de producto, descendente; con su cantidad de eventos de compra |

La demo usa una única moneda ilustrativa y excluye impuestos, devoluciones y costos.
No calcula ganancia, pedidos únicos, conversión ni comportamiento real de clientes.
El fixture no tiene huecos dentro de su semana de muestra. Un histograma en vivo futuro
debería definir explícitamente los buckets con conteo cero en el rango temporal pedido.

## Dashboard operativo de Kibana: trabajo pendiente

La interfaz operativa prevista sigue siendo Kibana. Esta entrega de documentación y demo
no creó ninguna exportación de saved objects. Los siguientes puntos dependen de un pipeline
de datos funcionando y están cubiertos por el R8 del PRD:

- Crear el mapping explícito de eventos, cargar un fixture determinista y conciliarlo.
- Crear una data view usando el índice seleccionado y `@timestamp`.
- Construir primero los paneles de total de eventos, monto de compras, cantidad/proporción
  de errores y actividad.
- Agregar vistas por producto, desglose de errores y términos de búsqueda cuando existan
  sus campos.
- Asegurar que todos los paneles compartan los filtros de tiempo y categoría; decidir cómo
  se comportan los eventos sin categoría bajo filtros de categoría. No mezclar en silencio
  totales filtrados y sin filtrar.
- Comparar los valores de los paneles con las expectativas del fixture calculadas de forma
  independiente.
- Exportar los saved objects y documentar los pasos de importación, las versiones y el
  intervalo del dataset.

El ranking offline por valor de producto es ilustrativo; el esquema de compras de Python
debe incluir un identificador de producto antes de implementar un panel operativo
equivalente. La demo es un artefacto de presentación útil, no evidencia de haber completado
los requisitos R1 a R9 del PRD.

## Alcance de diseño y entrega

Clasificación M: presentación interactiva localizada y documentación coordinada.
No hay cambios de despliegue, credenciales, base de datos, infraestructura ni
comportamiento de ingesta. El diseño visual usa una paleta fría de instrumentos en azul y
verde azulado, tipografía sobria y una franja de sistema de cuatro etapas. Los controles
tienen estados de foco visibles; los gráficos incluyen etiquetas numéricas; el layout se
adapta a móvil; no se cargan fuentes, librerías ni rastreadores externos.

Rollback: eliminar el directorio `dashboard` y los enlaces de la documentación de
presentación. Los datos y servicios existentes de Docker no se ven afectados. Los tests y
la evidencia de verificación están registrados en
[presentation-verification.md](presentation-verification.md).
