# Continuar el proyecto en Codex

Lee AGENTS.md, docs/STATUS.md, docs/ROADMAP.md y docs/DESIGN_SYSTEM.md.
Ya existe CLI, web local, motor sintético, adaptador LLM de texto configurable,
historial, evidencias, comparaciones y exportación. No reinicies el proyecto.

Primero ejecuta la suite y haz QA visual en un navegador disponible:
320px, 390px, escritorio, claro/oscuro, zoom 200%, teclado y diálogos.
Corrige problemas observados sin cambiar la dirección Apple Design + Lucide.
No sustituyas los iconos por emojis ni añadas cifras ficticias.

Después implementa el laboratorio de herramientas de la fase 2:
corpus ficticio por usuario, search_documents y create_ticket con almacenes
efímeros por ejecución, autorización fuera del modelo y variantes vulnerable/protegida.
Los efectos deben comprobarse en el almacén de laboratorio, no inferirse de una
respuesta verbal ni confiar en una telemetría declarada por el propio agente.
Mantén adaptadores y contratos separados para scripted, llm_text y agente instrumentado.
Prueba acceso cruzado, aislamiento, tarea legítima y acciones bloqueadas.

No presentes pass en una prueba de texto como auditoría de herramientas o MCP.
No contactes proveedores reales ni ejecutes peticiones de pago automáticamente.
Consulta la documentación oficial del proveedor antes de ampliar su adaptador.
Conserva prompts y respuestas de laboratorio, elimina secretos y documenta límites.
Ejecuta los checks, actualiza STATUS.md y explica qué verificaste y qué queda pendiente.
