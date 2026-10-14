# Reglas del proyecto

- Lee docs/ROADMAP.md, docs/STATUS.md y las instrucciones existentes antes de editar.
- Python para el núcleo. La web local y el adaptador de texto LLM están autorizados en esta revisión.
- Usar datos sintéticos. Contactar endpoints LLM solo tras iniciar una ejecución explícita.
- La suite predeterminada funciona sin red, credenciales ni LLM.
- Separa execution_status de security_verdict.
- Nunca conviertas errores, timeouts o falta de evidencia en pass.
- Distingue el adaptador guionizado de una auditoría de un modelo real.
- Evalúa acciones y efectos observables con políticas explícitas.
- No uses un LLM como único juez de hallazgos.
- No registres secretos ni razonamiento interno privado.
- Prueba fallos esperados, tareas legítimas e instrumentación insuficiente.
- Mantén documentación, ejemplos y código alineados.
- Implementa solo la fase solicitada; no amplíes el alcance sin motivo.
- No publiques ni crees repositorios remotos en tareas locales.
- Antes de cerrar una tarea, ejecuta los checks y documenta los no ejecutados.

## Preferencias visuales de Yoandy
- Prioridad: Apple Design de Emil Kowalski y Lucide. Ver docs/DESIGN_SYSTEM.md.
- Inspiración adicional: Rosetta Multinorma y CTEM-Nexus del autor.
- Iconos Lucide reales, locales y con licencia conservada; sin emojis como sustitutos.
- Tipografía del sistema, jerarquía clara, superficies sobrias y cristal solo en navegación.
- Respuesta inmediata al pulsar y accesibilidad por teclado; respetar preferencias del sistema.
- Anatomy para explicaciones visuales cuando aporten valor, no como decoración de cada pantalla.
- Autoresearch inspira comparaciones acotadas. No implica entrenamiento ni bucles autónomos sin límite.
- MCP y permisos reales del agente requieren instrumentación; no presentar probes de texto como esa auditoría.


## Nombre provisional
- Repositorio y producto: auditor_llm. Mantener agent_audit, AEGIS_LLM_* y los marcadores del protocolo por compatibilidad hasta una migración explícita.
