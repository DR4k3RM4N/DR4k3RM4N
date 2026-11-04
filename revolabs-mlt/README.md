# RevoLabs MLT

**Monitor de Lives de TikTok** · Revo Labs · Uso interno

Ves varios lives de TikTok a la vez en una sola ventana, con alertas cuando alguno se cae, favoritas, guías de encuadre y más.

## ⬇️ Descargar

Entra a **[Releases → última versión](../../releases/latest)** y descarga el archivo de tu computadora:

| Computadora | Archivo |
|---|---|
| Windows | `RevoLabs-MLT-Windows.zip` |
| Mac con chip Apple (M1, M2, M3, M4) | `RevoLabs-MLT-Mac-AppleSilicon.zip` |
| Mac con procesador Intel | `RevoLabs-MLT-Mac-Intel.zip` |

¿No sabes qué Mac tienes? Menú  → **Acerca de esta Mac**. Si dice "Chip Apple M…", es Apple Silicon; si dice "Procesador Intel…", es Intel.

> Necesitas iniciar sesión en GitHub con una cuenta que tenga acceso a este repositorio. Si no ves la página de descargas, pide acceso al administrador.

## Instalar

**Windows**
1. Haz clic derecho sobre el zip → **Extraer todo**.
2. Abre `RevoLabs-MLT-<versión>.exe`. No necesita instalación.
3. Si sale "Windows protegió su PC", pulsa **Más información** → **Ejecutar de todas formas**.

**Mac**
1. Abre el zip y arrastra **RevoLabs MLT** a la carpeta **Aplicaciones**.
2. Ábrela. Si Mac dice que no puede verificarla, ve a **Ajustes del Sistema → Privacidad y seguridad** y pulsa **Abrir de todas formas**.
3. Si dice que la app "está dañada", abre **Terminal** y ejecuta:
   ```bash
   xattr -cr "/Applications/RevoLabs MLT.app"
   ```

## Actualizar

Descarga la versión nueva desde Releases y reemplaza la anterior. Tu lista de lives, favoritas y notas se conservan.

Las novedades de cada versión están en [LEEME.md](LEEME.md).

## Publicar una versión nueva (administradores)

1. Cambia `"version"` en `package.json` (por ejemplo `0.5.2`) y anota las novedades en `LEEME.md`.
2. Sube los cambios y crea la etiqueta de la versión:
   ```bash
   git tag v0.5.2
   ```
   ```bash
   git push origin main --tags
   ```
3. GitHub compila sola la app para Windows y Mac (pestaña **Actions**, unos 10 minutos) y la publica en **Releases**.

También puedes lanzarla a mano en **Actions → Publicar versión → Run workflow**.

### Desarrollo

```bash
npm install
```
```bash
npm start
```
