# Conectar la oficina a tu WhatsApp

Tu equipo te escribe por WhatsApp (ideas nuevas, videos listos, problemas) y tú les contestas como en
un chat: *sí 1*, *no 2 ya la hicimos*, *busca apps de encuestas*, *¿cómo van?*.

Se usa la **API oficial de WhatsApp de Meta**. Es gratis crear la cuenta; Meta cobra por mensaje
(en México, alrededor de **$0.0085 USD** cada uno; revisa la tabla de precios de Meta). Para gastar
poco, la oficina junta varios avisos en un solo mensaje y, por defecto, solo te escribe lo importante.

> Meta cambia sus pantallas seguido; si un nombre no coincide exactamente, busca el más parecido.

---

## 1. Crea la app en Meta (10 min)

1. Entra a **developers.facebook.com** con tu Facebook y dale **Mis apps → Crear app**.
2. Elige el caso de uso **"Conectar con clientes por WhatsApp"** (o tipo **Empresa** y luego agrega
   el producto **WhatsApp**).
3. Si te pide un **portafolio comercial** (Business), crea uno con el nombre de tu canal.

## 2. Número y tu teléfono

En tu app → **WhatsApp → Configuración de la API** (o "API Setup"):

1. Meta te da un **número de prueba gratis**. Ese será el número de tu "equipo".
2. En **"Para"** (destinatarios), agrega **tu número de WhatsApp** y confírmalo con el código que te
   llega. (Con el número de prueba solo se puede escribir a números confirmados; para ti basta.)
3. Copia el **Identificador del número de teléfono** (*Phone number ID*). Lo vas a pegar después.

## 3. Token permanente

El token que aparece en esa pantalla **caduca en 24 horas**. Haz uno permanente:

1. Ve a **business.facebook.com → Configuración → Usuarios → Usuarios del sistema**.
2. **Agregar** → nombre `oficina`, rol **Administrador**.
3. **Asignar activos** → tu app → control total.
4. **Generar token** → elige tu app, caducidad **Nunca**, y marca los permisos
   `whatsapp_business_messaging` y `whatsapp_business_management`.
5. Copia el token y guárdalo (solo se muestra una vez).

## 4. Clave secreta de la app

En tu app → **Configuración de la app → Básica** → **Clave secreta de la app** → **Mostrar** y cópiala.
(Sirve para comprobar que los mensajes que llegan a tu oficina vienen de verdad de Meta.)

## 5. La plantilla para que te puedan escribir primero

WhatsApp solo deja que el negocio te escriba primero con una **plantilla aprobada**. Cuando tú le
contestas, por 24 horas ya se platica normal.

1. Entra a **business.facebook.com → WhatsApp Manager → Plantillas de mensajes → Crear plantilla**.
2. Categoría **Utilidad**. Nombre: `novedad_oficina`. Idioma: **Español (MEX)**.
3. Cuerpo (escríbelo así, con la variable):
   ```
   Novedad de tu oficina: {{1}}
   ```
   Si te pide un ejemplo para `{{1}}`: `Paola te trajo 5 ideas nuevas`.
4. Envíala a revisión. Suele aprobarse en minutos u horas.

## 6. Pon los datos en tu servidor

Entra al servidor y corre el asistente; te va preguntando cada dato:

```bash
ssh ubuntu@51.195.201.84
```

```bash
cd /opt/canal/autocanal && sudo -u canal .venv/bin/python oficina.py --configurar-whatsapp
```

Al final te muestra dos cosas para el paso 7: la **URL del webhook** y el **token de verificación**.
Luego reinicia:

```bash
sudo systemctl restart oficina
```

## 7. Webhook: para que tus respuestas lleguen a la oficina

En tu app → **WhatsApp → Configuración** (Configuration) → **Webhook → Editar**:

1. **URL de devolución de llamada**: la que te dio el asistente
   (`https://51-195-201-84.sslip.io/whatsapp/webhook`).
2. **Token de verificación**: el que te dio el asistente.
3. **Verificar y guardar**. Luego, en los campos del webhook, **suscríbete a `messages`**.

## 8. Prueba

```bash
cd /opt/canal/autocanal && sudo -u canal .venv/bin/python oficina.py --probar-whatsapp
```

Te debe llegar un WhatsApp de prueba. Contéstale **ayuda** y Paola te responde con lo que puede hacer.

---

## Qué le puedes escribir

| Escribes | Pasa |
|---|---|
| `ideas` · `busca apps de encuestas` | Paola busca ideas y te las manda numeradas |
| `pendientes` | Te pasa las ideas y los videos que esperan tu respuesta |
| `sí 1` · `dale a la 2` | Arranca ese video |
| `no 3 ya la hicimos` | La descarta y aprende por qué |
| `opino 1 enfócalo en el pago mínimo` | Se lo pasa al equipo |
| `¿cómo van?` | Quién está haciendo qué, y cuánto llevas gastado hoy |
| Cualquier otra cosa | Haiku entiende lo que quisiste decir (cuesta una fracción de centavo) |

Cada idea conserva su número aunque apruebes o descartes otras. **Publicar** se hace en la oficina,
donde ves el video y la lista de comprobación; por WhatsApp te llega el enlace.

## Ajustes en `.env`

- `AVISOS_NIVEL=todo` para recibir también cada entrega entre agentes (más mensajes, más costo).
  Con `importante` (por defecto) solo: ideas listas, video listo, publicado y problemas.
- Solo se obedecen mensajes de tu número (`WHATSAPP_JEFE`); los de cualquier otro se ignoran.

## Si algo falla

- **No llega nada con `--probar-whatsapp`**: lee el mensaje que sale. Casi siempre es la plantilla
  (no aprobada todavía, o con otro nombre/idioma) o tu número no está confirmado en el paso 2.
- **Contestas y la oficina no reacciona**: revisa el paso 7 (URL, token y que estés suscrito a
  `messages`). En el servidor, `sudo journalctl -u oficina -n 30` muestra los últimos avisos.
