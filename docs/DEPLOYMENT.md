# Despliegue privado de auditor_llm

La web completa incluye el motor Python. GitHub Pages sirve la portada pública;
la aplicación operativa se despliega como servicio Docker en Render.

## Desde el móvil

1. Abre [Desplegar en Render](https://render.com/deploy?repo=https://github.com/heindall92/auditor_llm).
2. Entra en tu cuenta de Render y revisa el Blueprint: un servicio web `free`, región Frankfurt.
3. Pulsa **Deploy Blueprint**. No se declara una base de datos ni un disco de pago.
4. Cuando el servicio esté activo, abre su URL HTTPS.
5. El navegador pedirá usuario y contraseña. Usuario: `auditor`. Contraseña: el valor generado
   de `AUDITOR_ADMIN_PASSWORD` en **Environment** del servicio. No la compartas en el chat ni en GitHub.
6. Ejecuta **Laboratorio sintético** para comprobar la instalación. No requiere una clave de IA.

La contraseña se genera en Render; no existe una contraseña por defecto en el código.
No se debe publicar la contraseña ni incluirla en enlaces. Para cerrar el acceso persistente
que guarda el navegador con HTTP Basic, cierra la sesión de navegación privada o rota la contraseña.

## Proveedor LLM opcional

Configura en **Environment** del servicio y vuelve a desplegar:

| Variable | Uso |
|---|---|
| `AEGIS_LLM_URL` | URL HTTPS completa y autorizada, terminada en `/chat/completions` |
| `AEGIS_LLM_MODEL` | Modelo exacto que acepta ese proveedor |
| `AEGIS_LLM_API_KEY` | Clave del proveedor, solo en el entorno del servidor |

No se añade ninguna clave ni se realizan llamadas de pago automáticamente.
La interfaz debe usar el mismo endpoint y modelo que el servidor. Cambiarlos en el
navegador se rechaza antes de iniciar un trabajo, evitando enviar la clave a otros destinos.
Las redirecciones del proveedor siguen deshabilitadas. El operador debe elegir un
proveedor de confianza; un nombre DNS configurado puede cambiar de dirección, y esta
restricción no sustituye un firewall de salida. No es un servicio público multiusuario.

## HTTPS y almacenamiento

Render termina HTTPS delante de Waitress 3.0.2. `RENDER_EXTERNAL_URL` fija el origen
permitido; un dominio propio requiere `AUDITOR_PUBLIC_ORIGIN=https://tu-dominio` sin `/` final.
Todas las vistas, recursos y API requieren autenticación excepto `GET /healthz`,
que solo responde `{"status":"ok"}`. Las mutaciones también requieren Origin y CSRF.
El acceso incorrecto se limita a 20 intentos por minuto para toda la instancia; esta
protección sencilla está destinada a un único operador y puede bloquearle temporalmente.

El plan gratuito tiene disco efímero: las evidencias se pierden al reiniciar o redesplegar.
Exporta JSON e informes antes. Puede suspenderse por inactividad según las condiciones
vigentes de Render. Para conservar datos, configura almacenamiento persistente en un
plan compatible y cambia `AUDITOR_OUTPUT_DIR`; esa ampliación puede tener coste y no
forma parte del Blueprint gratuito.

Un único proceso mantiene la cola y CSRF en memoria. No escalar a múltiples procesos
ni réplicas sin migrar sesiones y trabajos a almacenamiento compartido. Una ejecución
activa puede interrumpirse por un reinicio. El servicio no ejecuta shell de agentes ni MCP.

## Docker en otro servidor

Necesitas un proxy HTTPS delante del contenedor y un origen público fijo.

```bash
docker build -t auditor-llm .
# Exporta antes AUDITOR_ADMIN_PASSWORD con un secreto aleatorio de al menos 24 caracteres.
docker run --rm -p 127.0.0.1:10000:10000 \
  -e AUDITOR_ADMIN_PASSWORD \
  -e AUDITOR_PUBLIC_ORIGIN=https://auditoria.example \
  -v auditor-evidence:/app/output \
  auditor-llm
```

El contenedor corre como UID 10001 y solo publica el puerto de Waitress.
No uses el servidor `serve` de desarrollo como servicio público.
Las dependencias del hosting son opcionales: el laboratorio local mantiene cero
bibliotecas externas en tiempo de ejecución.

## Verificación

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
node --check src/agent_audit/static/app.js
```

La suite cubre el modo local y WSGI, rutas protegidas, Host/Origin/CSRF,
restricción del destino LLM, secretos y la ejecución de los tres escenarios sintéticos.
La publicación real solo está verificada cuando el proveedor devuelve un servicio activo
con su URL; tener este archivo en GitHub no significa que ya esté desplegado.
