# Estado del proyecto · 0.0.3

Fecha: 14 de octubre de 2026. Código preparado para hosting privado. La publicación efectiva depende de conectar una cuenta de alojamiento.

## Implementado

- Núcleo Python y CLI de las fases 0–1, con las pruebas existentes conservadas.
- Aplicación web local con siete secciones: panel, objetivos, pruebas, ejecuciones, evidencias, comparación y ajustes.
- Estética Apple Design inspirada principalmente en Emil Kowalski, iconos reales Lucide y preferencias registradas en AGENTS.md.
- Tres escenarios sintéticos; importación/validación de escenarios JSON desde la web.
- Ocho probes de texto para un endpoint chat/completions configurable.
- Pruebas MCP/permisos y aislamiento entre usuarios identificadas como pendientes; skipped/inconclusive en API.
- Trabajos en segundo plano, progreso, límites y cancelación antes de la siguiente petición.
- Historial persistido en archivos locales; inspector de eventos y respuestas.
- Exportación JSON e informe HTML con contenido escapado.
- Comparación individual de ejecuciones del mismo escenario y advertencias de compatibilidad.
- Clave vía AEGIS_LLM_API_KEY, sin credenciales en navegador; sin CDN, fuentes remotas ni analítica.
- Servidor solo en loopback, control Host/Origin/CSRF y CSP same-origin.

## Verificación

- Suite pytest: 44 pruebas aprobadas.
- Incluye HTTP local real contra un doble de proveedor, controles de acceso de la web,
  flujo completo de los tres fixtures, oráculos de fuga literal, respuestas incompletas,
  errores, clave reflejada, escape HTML, tamaño y validación de entrada.
- `node --check src/agent_audit/static/app.js`: aprobado.
- Contraste de los seis pares principales calculado; valores en DESIGN_SYSTEM.md.
- No se contactaron proveedores LLM externos y no se consumieron tokens de un modelo real.

## Límites de verificación

No se dispuso de la habilidad de control de navegador requerida en este entorno para la QA visual. No se inició un preview alternativo ni se instalaron navegadores. La interfaz requiere revisión manual visual en escritorio, móvil, zoom 200% y con lector de pantalla.

No se verificó compatibilidad con un proveedor real, no se ejecutaron agentes externos,
y no se declara certificación de seguridad o accesibilidad completa.

## Próximos pasos

1. QA visual en Codex con navegador disponible.
2. Probar un endpoint autorizado con una sola tarea funcional antes de ampliar la suite.
3. Implementar herramientas del laboratorio e instrumentación independiente de efectos.
4. Añadir MCP, firmas/hashes, CI y validación externa después de estabilizar los contratos.

Ver CODEX_NEXT_PROMPT.md. La prioridad de diseño persiste en AGENTS.md dentro de este proyecto; las skills externas no están instaladas globalmente.

## Hosting privado 0.0.3

- Rutas compartidas por el servidor local y WSGI; Waitress opcional 3.0.2.
- Docker sin root y Blueprint gratuito de Render, con contraseña generada por el proveedor.
- HTTP Basic en todas las vistas/API, excepto salud; Host/Origin/CSRF conservados.
- Destino y modelo LLM fijados por el servidor en modo alojado; sin proveedor ni claves por defecto.
- Ocho pruebas nuevas de acceso, límites, configuración y flujo completo.
- Ver DEPLOYMENT.md para pérdida de datos en disco efímero, un solo operador y límites de DNS.
- No se declara publicación efectiva ni QA visual del hosting hasta comprobar la URL activa.
