# Dirección de diseño de Yoandy

## Prioridades y fuentes

1. Apple Design de Emil Kowalski: https://github.com/emilkowalski/skills/tree/main/skills/apple-design
2. Lucide: https://lucide.dev/guide/lucide
3. Apple Design de dickwu: https://github.com/dickwu/apple-design-skill
4. Anatomy: https://github.com/wheresryan22/anatomy
5. Autoresearch: https://github.com/karpathy/autoresearch
6. Referencias del autor: Rosetta Multinorma y CTEM-Nexus.

Estas referencias se han revisado para el proyecto. No se han instalado globalmente ni se han copiado sus SKILL.md como skills nuevas. Las preferencias quedan en AGENTS.md para conservarlas en este checkout.

## Aplicación concreta

- De Emil: feedback al pulsar, continuidad sin bloqueos decorativos, tipografía del sistema, tracking por tamaño, reducción de movimiento y transparencia.
- De Lucide: 44 SVG del paquete oficial lucide-static 1.57.0, servidos localmente como sprite. Mismo grosor y tamaño por contexto, etiquetas visibles y SVG decorativos con aria-hidden.
- De dickwu: jerarquía, adaptación al ancho, acceso por teclado, colores semánticos y separación entre chrome y contenido. Se aplican principios web, no convenciones exclusivas de apps nativas Apple.
- De Rosetta/Nexus: organización por capacidades, teal discreto, evidencias y resultados explicables. No se reutiliza su código ni se afirma una réplica de sus pantallas.
- De Autoresearch: comparar una referencia y una candidata con un escenario y presupuesto conocidos. No se ejecuta entrenamiento ni un bucle autónomo.
- De Anatomy: reservar explicaciones visuales para mecanismos que necesiten ser entendidos. Esta entrega usa un recorrido funcional de tres pasos con Lucide; no incluye una figura isométrica ni afirma haber aplicado su kit geométrico.

## Sistema de tokens

| Rol | Claro | Oscuro |
|---|---|---|
| Fondo | #f6f8f8 | #101918 |
| Superficie | #ffffff | #182321 |
| Texto | #15282b | #e5efeb |
| Texto secundario | #5b6e71 | #a3b6ae |
| Acento | #08796d | #66d3ac |
| Borde | #dce5e5 | #30433d |

Contrastes calculados desde valores sRGB sólidos: texto claro/superficie 15.33:1; secundario claro 5.37:1; texto blanco/botón teal 5.29:1; texto oscuro/superficie 13.74:1; secundario oscuro 7.58:1; texto oscuro del botón/acento 7.54:1. Esto no sustituye una auditoría de todas las combinaciones ni una prueba del material translúcido sobre contenido.

Tipografía: sistema, cuerpo base 15px escritorio y 16px compacto; títulos con tracking negativo y line-height ajustado; datos monoespaciados solo donde importa. Espaciado en rem y layouts fluidos. La jerarquía combina tamaño, peso y proximidad.

Material: superficies de contenido opacas, blur restringido a sidebar, toolbar y navegación móvil. Se adapta a prefers-reduced-transparency y prefers-contrast. No hay animaciones de fondo ni delays artificiales. No hay gestos complejos que requieran motores de spring.

Elemento distintivo: la evidencia es el centro. Cada resultado abre el motivo y los eventos; el verde no se presenta como una puntuación global de seguridad.

## Revisión antes de entregar

Checks de código: elementos semánticos, diálogo nativo con Escape, labels para formularios, skip link, foco visible, navegación con aria-current, estados con texto e icono además de color, sin fuentes o scripts remotos.

Pendiente de verificación visual manual: escritorio ancho, 390px y 320px, zoom 200%, modo oscuro, teclado y lector de pantalla. No se declara una auditoría WCAG completa.
