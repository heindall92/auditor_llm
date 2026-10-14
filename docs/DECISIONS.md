# Decisiones de las fases 0 y 1

1. Biblioteca estándar de Python para ejecución y validación explícita mediante dataclasses.
   Sin dependencia de modelos externos; el formato JSON tiene un validador estricto propio.
2. pytest se configura como herramienta de desarrollo. Las pruebas usan unittest y también
   pueden ejecutarse con la biblioteca estándar sin descargar paquetes.
3. Un subprocess por ejecución permite terminar el guion en timeout. No se usan hilos que
   continúen ejecutándose tras vencer el plazo. No se crean nietos en este adaptador.
4. Los fixtures definen telemetría de referencia. No se presenta como efecto real de un LLM.
5. El evaluador exige tanto cobertura completa como resultados funcionales exactos para pass.
6. Un error operativo prevalece como inconclusive, conservando referencias a violaciones
   ya observadas. Evita confundir una ejecución incompleta con una auditoría satisfactoria.
7. No hay licencia elegida automáticamente: el propietario la decidirá antes de publicar.
8. MCP, modelos reales, HTML, CI e integraciones se mantienen fuera de esta entrega.

## Ampliación autorizada 0.0.2

Las decisiones anteriores describen la primera entrega 0.0.1. Por petición posterior
del propietario se añadió web local, adaptador de texto LLM, exportación HTML y
comparación individual. MCP e instrumentación de agentes siguen pendientes.
El contrato de texto declara explícitamente su cobertura y no modifica el significado
del adaptador sintético. Ver STATUS.md y DESIGN_SYSTEM.md para el estado actual.


## Despliegue autorizado 0.0.3

El propietario pidió alojar la aplicación completa para usarla desde el móvil.
Se conserva el núcleo Python y se añade WSGI con Waitress opcional, Docker y un
Blueprint de Render. La instancia es privada y de un solo operador; no se afirma
autenticación multiusuario ni persistencia en el plan gratuito. Se reutilizan las
rutas locales, y el modo remoto fija endpoint/modelo desde el servidor para no
enviar su clave a una URL elegida desde el navegador.
