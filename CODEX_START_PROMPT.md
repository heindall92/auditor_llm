# Prompt inicial de referencia

Ya ejecutado para las fases 0 y 1; consulta STATUS.md antes de continuar.

```text
Vamos a comenzar un proyecto local de auditoría de seguridad de agentes LLM.
Lee el roadmap adjunto y las instrucciones existentes del repositorio.
El nombre de trabajo es AEGIS Agent Lab; no requiere decidir marca todavía.

Implementa únicamente las fases 0 y 1: un núcleo Python con CLI, runner,
esquemas validados, evaluador y un adaptador determinista guionizado.
No implementes interfaz web, proveedor LLM, MCP ni conexiones externas.
Si el directorio contiene trabajo previo, inspecciónalo y respétalo.

Entrega:
1. Estructura de proyecto, pyproject.toml y configuración de pytest.
2. README con instalación y comandos que realmente funcionen.
3. AGENTS.md con las reglas del roadmap.
4. Modelo de amenazas y esquema de evidencias documentados.
5. Tres fixtures: operación legítima, acción prohibida completada
   e instrumentación insuficiente.
6. Eventos JSONL y resumen JSON con execution_status y security_verdict.
7. Pruebas significativas del evaluador, aislamiento entre ejecuciones,
   esquema inválido, excepción y timeout.

Los tres fixtures deben producir pass, fail e inconclusive respectivamente.
Un fallo del runner nunca debe aparecer como un pass de seguridad.
Usa únicamente datos sintéticos. La suite debe funcionar sin red ni claves.
Define códigos de salida documentados para éxito, fallo detectado y ejecución
incompleta o inválida, sin confundir esos casos.

Ejecuta los checks disponibles. Corrige los fallos y termina indicando
qué funciona, qué has probado, qué no pudiste ejecutar y qué queda pendiente.
No afirmes haber auditado un LLM con el adaptador guionizado.
No publiques nada ni modifiques otros repositorios.
```
