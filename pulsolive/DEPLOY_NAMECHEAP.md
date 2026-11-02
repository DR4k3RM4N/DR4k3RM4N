# Publicar PulsoLive en Namecheap (cPanel)

Guía para hosting compartido de Namecheap (planes Stellar con cPanel). Toma unos 20 minutos y no necesitas instalar nada en tu computadora.

> Ejemplo: usaremos el subdominio `pulso.tudominio.com`. Cambia `tudominio.com` por tu dominio real.

## 0. ¿Tu plan lo soporta?

Entra a **cPanel** y busca en la sección *Software* el ícono **"Setup Python App"**.

- **Sí aparece:** sigue esta guía.
- **No aparece:** tu plan no permite apps de Python (o solo tienes el dominio). En ese caso conviene publicarlo en Render.com y apuntar tu dominio de Namecheap hacia allá.

## 1. Crea el subdominio

cPanel → **Domains** (o *Subdomains*) → crea `pulso` en tu dominio.

## 2. Baja el código desde GitHub

cPanel → **Git™ Version Control** → **Create**:

- **Clone a Repository:** activado
- **Clone URL:** `https://github.com/DR4k3RM4N/DR4k3RM4N.git`
- **Repository Path:** `pulsolive_repo`
- **Repository Name:** `pulsolive`

Da clic en **Create**. Luego, en **Manage** → *Pull or Deploy*, cambia la rama a **`claude/friendly-mendel-1bihpd`** si no lo está.

> Si tu repositorio es privado y no deja clonar: descarga el ZIP desde GitHub, súbelo con **File Manager** a tu carpeta principal y descomprímelo. Ajusta las rutas de abajo.

## 3. Crea la app de Python

cPanel → **Setup Python App** → **Create Application**:

| Campo | Valor |
|---|---|
| Python version | La más alta disponible (**3.11 o mayor**; Django 5.2 no funciona con 3.9 o menos) |
| Application root | `pulsolive_repo/pulsolive` |
| Application URL | `pulso.tudominio.com` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

En **Environment variables** agrega estas variables:

| Nombre | Valor |
|---|---|
| `DEBUG` | `false` |
| `SECRET_KEY` | una cadena larga y aleatoria (mínimo 50 caracteres; ver paso 4) |
| `ALLOWED_HOSTS` | `pulso.tudominio.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://pulso.tudominio.com` |
| `SITE_URL` | `https://pulso.tudominio.com` |

Da clic en **Create**.

## 4. Instala y prepara (Terminal de cPanel)

Arriba de la página de tu app aparece un comando que empieza con `source /home/...`. Cópialo.

Abre cPanel → **Terminal**, pégalo y presiona Enter. Luego corre:

```bash
pip install -r requirements.txt
```
```bash
python manage.py migrate
```
```bash
python manage.py collectstatic --noinput
```
```bash
python manage.py seed_demo
```

Para generar una `SECRET_KEY` (pégala en las variables del paso 3):

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

> **Sin Terminal:** en la página de la app, en *Configuration files*, agrega `requirements.txt` y da **Run Pip Install**. Luego usa el campo **Execute python script** con `manage.py migrate`, después `manage.py collectstatic --noinput` y al final `manage.py seed_demo`.

## 5. Activa HTTPS y reinicia

1. cPanel → **SSL/TLS Status** → selecciona el subdominio → **Run AutoSSL**.
2. Regresa a **Setup Python App** y da **Restart** a la app.

Abre `https://pulso.tudominio.com` y entra con **demo@pulsolive.app / demo12345**.

## Actualizar cuando haya cambios

1. Git Version Control → **Manage** → **Update from Remote**.
2. En la Terminal, después del comando `source ...`, corre:

```bash
python manage.py migrate
```
```bash
python manage.py collectstatic --noinput
```

3. Setup Python App → **Restart**.

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `Killed` o error de memoria durante `pip install` | Repite el comando; si sigue, pide a soporte de Namecheap más memoria temporal o instala de uno en uno: `pip install pandas`, luego el resto. |
| "Bad Request (400)" | `ALLOWED_HOSTS` no coincide con la dirección exacta. |
| "CSRF verification failed" al entrar | Falta `CSRF_TRUSTED_ORIGINS` con `https://`. |
| Página sin estilos | Corre `collectstatic` y reinicia la app. |
| Error 500 / "Incomplete response" | Revisa `stderr.log` en la carpeta de la app (File Manager). |
| Se queda dando vueltas / redirige infinito | Activa el SSL (paso 5) o agrega la variable `SECURE_SSL_REDIRECT=false` mientras tanto. |

## Notas

- Para pruebas, la base de datos es SQLite (archivo `db.sqlite3` en la carpeta de la app). Para producción con clientes, usa la base de datos MySQL/Postgres que ofrezca tu plan o un servicio externo.
- Cambia la contraseña de la cuenta demo o bórrala antes de compartir el link con clientes.
