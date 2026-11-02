# PulsoLive

Analítica para lives de TikTok Shop. Dice **qué hizo que se vendiera más** (hora, día, host, perfil del host, promoción, guion, duración, momentos dentro del live) y **qué hacer para repetirlo**.

Pensado para agencias que operan lives de varias marcas, para marcas con equipo propio y para creadores.

## Qué incluye

| Módulo | Qué hace |
|---|---|
| **Importación** | Sube el CSV/Excel exportado de Seller Center o LIVE Center. Reconoce columnas en español e inglés, formatos de dinero (`$12,345.67`), duraciones (`1h 23m`, `01:23:45`) y fechas. Si reimportas, actualiza el live en lugar de duplicarlo. |
| **Etiquetado rápido** | Host, promoción, tipo de guion, formato, escenario y producto, uno tras otro (unos 30 s por live). |
| **¿Qué vende más?** | Para cada factor calcula el efecto simple y el efecto *controlando lo demás* (regresión ridge). También da la confianza según tamaño de muestra y prueba de Welch, cuánto pesa cada factor y un mapa de calor día × hora. |
| **Momentos del live** | Con datos minuto a minuto detecta picos de ventas y caídas de audiencia, y los liga al momento que los causó. Agregado entre lives, muestra qué momentos suben pedidos (por ejemplo, "quedan pocas piezas": +100% en los 5 minutos siguientes). |
| **Transcripciones** | Sube un `.srt`, `.vtt` o texto con marcas de tiempo. Detecta los momentos por palabras clave (gratis) o con IA (Claude), que además resume el live y da retroalimentación al host. |
| **Recomendaciones** | Lista priorizada de qué repetir, corregir, probar y qué datos faltan. Incluye diagnóstico del embudo (retención, conversión, ticket). |
| **Ranking de hosts** | Ventas/h, conversión, retención y ticket contra el promedio del equipo, con coaching automático. |
| **Playbook por marca** | La receta del mejor live, los momentos que hay que meter en el guion, lives para estudiar y calendario sugerido de 7 días. |
| **Reportes** | Diario, semanal y mensual contra el periodo anterior. Se pueden imprimir o guardar como PDF, opcionalmente con resumen ejecutivo de IA. En el plan Agencia llevan tu logo y se comparten con link. |
| **Pruebas A/B** | Define dos variantes, marca los lives de cada una y la app dice si ya hay ganador. |
| **SaaS** | Organizaciones multi-cliente, roles (dueño, admin, analista, solo lectura para clientes), invitaciones, prueba de 14 días, planes con límites y cobro con Stripe. |

## Planes (MXN, IVA incluido)

| Plan | Mensual | Marcas | Usuarios | Análisis IA/mes | Extras |
|---|---|---|---|---|---|
| Creator | $699 | 1 | 1 | 10 | Reportes, playbook |
| Pro | $2,490 | 5 | 3 | 40 | + transcripciones, A/B, ranking de hosts |
| Agencia | $6,990 | 20 | 10 | 150 | + marca blanca, links para compartir |
| Enterprise | Cotización | ∞ | ∞ | ∞ | + API TikTok Shop, alertas en vivo |

El anual cuesta 10 meses (2 meses gratis). Los precios y límites están en `accounts/plans.py`.

## Correrlo en tu compu

```bash
cd pulsolive
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo          # cuenta demo con 6 meses de datos
python manage.py runserver
```

Abre http://localhost:8000 y entra con **demo@pulsolive.app / demo12345**. Los datos demo tienen patrones escondidos (las noches venden más, flash sale, la host Ana, "quedan pocas piezas"…) para ver cómo los descubre el análisis. También sirven para hacer demos de venta.

Para crear un administrador: `python manage.py createsuperuser` (panel en `/admin/`).

Pruebas: `python manage.py test insights`

## Configuración

Todo va en variables de entorno (ver `.env.example`):

- **`ANTHROPIC_API_KEY`**: activa los resúmenes y el análisis de transcripciones con Claude. Sin ella, todo lo demás funciona con el motor de reglas.
- **`STRIPE_*`**: crea en Stripe un producto con un precio mensual por plan y pon los `price_...` en `STRIPE_PRICE_CREATOR/PRO/AGENCY`. El webhook va en `https://TU-DOMINIO/stripe/webhook/` con los eventos `checkout.session.completed` y `customer.subscription.*`. Sin llaves, elegir plan lo activa en "modo demo".
- **`DATABASE_URL`**: Postgres en producción.

## Desplegar

Hay `Dockerfile` y `render.yaml` (Render.com). En Railway, Fly.io o cualquier servicio con Docker funciona igual: define las variables, una base Postgres y listo. El contenedor corre migraciones al arrancar.

## Arquitectura

```
pulsolive/
  accounts/   organizaciones, roles, invitaciones, planes (plans.py), Stripe (billing.py)
  lives/      marcas, hosts, lives, minuto a minuto, momentos, transcripciones, importadores
  insights/   engine.py (estadística pura, sin BD), services.py, ai.py (Claude), reportes, A/B
  templates/  HTML (Django templates), static/ CSS y gráficas (Chart.js incluido localmente)
```

`insights/engine.py` no depende de Django. Recibe una lista de lives y devuelve análisis, así que se puede probar y mejorar por separado.

## Siguientes fases (roadmap)

1. **Conexión directa a TikTok Shop**. Hay que registrarse como desarrollador en TikTok Shop Partner Center y pedir los permisos de analítica de LIVE. Así los lives se importarían solos cada día. Ya están las variables `TIKTOK_SHOP_APP_KEY/SECRET` en settings, pero falta implementar el cliente; los endpoints dependen de la aprobación de la app.
2. **Transcripción automática del video**: subir la grabación y transcribirla con un servicio de voz a texto, en vez de subir el `.srt`.
3. **Alertas en vivo**: "la retención está cayendo, lanza la oferta" mientras transmites (requiere datos en tiempo real vía API).
4. **Análisis de comentarios**: preguntas frecuentes, objeciones y productos que pide la gente.
5. **Benchmarks por categoría** con datos anónimos de todas las cuentas.
6. Envío automático de reportes por correo cada lunes y cada inicio de mes.

## Nota sobre las conclusiones

El análisis muestra **asociaciones** en tus datos, con su tamaño de muestra y nivel de confianza. Con pocos lives lo dice claramente. Para confirmar una causa, usa una prueba A/B. Los atributos del host (como el género) se presentan como dato de audiencia, nunca como juicio sobre personas, y se separan de otros factores como el horario.
