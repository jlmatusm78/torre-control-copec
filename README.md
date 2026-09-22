# Torre de Control COPEC

Dashboard Streamlit de evolución de alertas Guardian y FlotaGo desde Google Sheets.

- Vista inicial: últimas 6 semanas completas (lunes a domingo), con opciones de 4 y 5.
- Comparación de última semana completa contra la anterior.
- Vista mensual de 2 a 24 meses: mes anterior, mismo mes del año anterior o mes elegido.
- Comparación personalizada dentro de los últimos 24 meses, sin períodos superpuestos.
- Filtros por plataforma, transportista, una o varias alertas, planta, conductor y búsqueda. Sin tipos seleccionados se muestra el total.
- Diferencias absolutas y porcentuales, promedios, desglose por alerta y transportista, detalle y gestión de fatiga.
- Exportación Excel de ambas bases, evolución, comparaciones y filtros.
- No se agrega control de ingreso; se conserva el esquema de acceso del despliegue.

## Interpretación

Cada fila es un evento. No se deduplican IDs porque pueden repetirse entre fuentes. El histórico no tiene el antiguo límite de enero de 2026. Las fechas futuras se excluyen; la fecha de referencia usa America/Santiago.

La cobertura se infiere por plataforma antes de filtrar alertas o transportistas. Períodos sin registros de referencia son desconocidos y se dibujan como huecos. Los períodos que exceden el intervalo observado o llegan al presente se identifican como parciales/en curso y no generan porcentajes concluyentes. La existencia de registros no garantiza que la carga esté completa; para certificar ceros se necesitaría una fuente de control de carga.

Los conteos de tablas y detalles son registros observados, incluso cuando la cobertura es parcial. Un valor cero sin referencia no demuestra ausencia de alertas. Los promedios diarios usan días calendario y permiten contextualizar meses o intervalos de distinta duración. Aumentos/disminuciones no equivalen a cambios de riesgo sin kilómetros, viajes u horas de exposición.

## Ejecución y validación

Usar Python 3.11 o superior, instalar `requirements.txt` y ejecutar `streamlit run app.py`. Configurar las credenciales de Sheets como explica `DEPLOYMENT.md`; no subir secretos al repositorio.

Para pruebas: instalar `pytest` y ejecutar `python -m pytest -q` desde la raíz. Las pruebas de interfaz inyectan datos sintéticos, sin conectarse a Google Sheets.

## Evolución por alerta

El total se muestra primero, seguido de un gráfico por tipo de alerta. Los filtros se aplican a todos los gráficos. Cuando hay eventos de fatiga en la evolución mostrada, se agrega una evolución de Cumple/No cumple; las respuestas no válidas se cuentan aparte. El Excel incluye estas series.

Todas las categorías se unifican ignorando mayúsculas, minúsculas, espacios redundantes y tildes, sin equivalencias entre palabras diferentes. Se conserva Incidente original en el detalle y el Excel.

## Cumplimiento comparativo de fatiga

Cada alerta de fatiga incluye porcentaje actual y de referencia, diferencia en puntos porcentuales, cantidad y variación de No cumple, y respuestas sin información. La tasa es SI/(SI+NO); respuestas vacías o no válidas se excluyen. Sin respuestas válidas no se dibuja un punto ni se interpreta como 0 %. Las comparaciones requieren cobertura comparable y respuestas válidas en ambos períodos. Las tasas de períodos parciales se etiquetan como observadas. El Excel agrega Tasa cumplimiento y Comparación cumplimiento.
