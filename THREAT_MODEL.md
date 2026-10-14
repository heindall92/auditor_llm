# Modelo de amenazas inicial

## Activos

Integridad de conclusiones, correlación de evidencia, política del usuario ficticio,
disponibilidad del runner y separación de estado entre ejecuciones.

## Actores y fronteras

El operador selecciona un fixture sintético local. Los archivos JSON se validan como
entrada no confiable: tamaño, campos, tipos, límites y secuencia de acciones.
El runner confía en su código instalado y en el adaptador guionizado; no carga plugins
ni evalúa código desde JSON. El trabajador está separado mediante subprocess y recibe
solo un escenario validado. El evaluador contrasta efectos simulados con una política explícita.

El contenido de un fixture puede mentir sobre la cobertura o los efectos: la fase 1
valida la lógica de evaluación, no la verdad de un sistema externo. Un operador con
control del código, fixtures o archivos de salida puede falsificar los resultados.

## Amenazas cubiertas y comprobadas

- JSON mal formado, duplicados, exceso de tamaño, campos desconocidos y tipos incorrectos.
- Secuencias incoherentes: terminal sin intento, reutilización de call_id y recurso distinto.
- Estado heredado entre ejecuciones: proceso y directorio independientes.
- Falsos pass por error, timeout, falta de cobertura o llamadas sin resolver.
- Bloqueo de toda tarea legítima presentado como defensa eficaz.
- Exceso de acciones: se detiene el guion y se registra error.
- Protocolo del trabajador inválido: resultado inconcluso, nunca éxito.

## Exclusiones

No hay exposición de servicios, acceso a modelos reales, herramientas efectivas,
shell del agente, garantías de aislamiento frente a código hostil ni cadena de custodia.
Los datos son ficticios. La redacción general de secretos y hashes pertenecen a una
fase posterior. No aportar datos reales al fixture.

La fase 2 añadirá herramientas con autorización fuera del modelo y comprobación
independiente del efecto. La fase 3 añadirá un modelo real y su frontera de confianza.



## Extensión 0.0.2: web local y salida LLM

La web se enlaza solo a 127.0.0.1. Valida Host, Origin y un token CSRF de sesión para mutaciones; aplica CSP same-origin, sin CORS abierto ni secretos en el navegador. Las rutas estáticas no pueden salir del directorio de recursos. Estos controles no sustituyen autenticación para hosting remoto: no exponer el puerto públicamente.

Un endpoint elegido por el operador recibe la clave configurada y prompts sintéticos. Solo se acepta HTTPS remoto o HTTP loopback, sin userinfo/query/fragmentos y sin seguir redirecciones. El contenido del modelo se trata como no confiable y se escapa en HTML. El adaptador no ejecuta comandos, herramientas ni código del modelo.

La ausencia literal de un señuelo no descarta otras fugas; no hay análisis semántico o de codificaciones. La clave del entorno se redacta si aparece reflejada, pero no existe un detector general de secretos. Los resultados se guardan como archivos locales sin cifrado ni firma. Los límites de red son de E/S, no una garantía estricta de wall-clock.
