# Sala de edición: instala en esta compu (Windows) el programa que edita los videos de tu oficina.
# Lo corre INSTALAR_SALA.bat. Se puede correr otra vez para actualizar.
$ErrorActionPreference = "Continue"  # git y pip escriben avisos que no son errores
$Rama = "claude/keen-johnson-v42a39"
$RepoUrl = "https://github.com/DR4k3RM4N/DR4k3RM4N.git"
$Dir = Join-Path $env:LOCALAPPDATA "SalaEdicion"
$Repo = Join-Path $Dir "repo"
$Venv = Join-Path $Dir "venv"

function Paso($t) { Write-Host ""; Write-Host "  ▶ $t" -ForegroundColor Yellow }
function Bien($t) { Write-Host "    ✔ $t" -ForegroundColor Green }
function Recargar-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Tiene($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Instalar($id, $nombre) {
  Paso "Instalando $nombre (puede tardar unos minutos)…"
  winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements | Out-Host
  Recargar-Path
}

Write-Host ""
Write-Host "  ==============================================" -ForegroundColor Cyan
Write-Host "    🎬  Sala de edición — instalador" -ForegroundColor Cyan
Write-Host "  ==============================================" -ForegroundColor Cyan

if (-not (Tiene "winget")) {
  Write-Host "  Falta 'winget' (Instalador de aplicaciones de Microsoft). Instálalo desde la Microsoft Store y vuelve a correr esto." -ForegroundColor Red
  exit 1
}
Recargar-Path
if (-not (Tiene "git")) { Instalar "Git.Git" "Git" } else { Bien "Git ya está" }
$py = $null
try { $py = (& py -3.12 -c "import sys; print(sys.executable)" 2>$null) } catch {}
if (-not $py) { Instalar "Python.Python.3.12" "Python 3.12"; $py = (& py -3.12 -c "import sys; print(sys.executable)") } else { Bien "Python 3.12 ya está" }
if (-not (Tiene "ffmpeg")) { Instalar "Gyan.FFmpeg" "ffmpeg (el motor de video)" } else { Bien "ffmpeg ya está" }
Recargar-Path
if (-not (Tiene "ffmpeg")) {
  $link = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Links"
  if (Test-Path (Join-Path $link "ffmpeg.exe")) { $env:Path += ";$link" }
}

Paso "Bajando el programa de la sala…"
New-Item -ItemType Directory -Force -Path $Dir | Out-Null
if (Test-Path (Join-Path $Repo ".git")) {
  git -C $Repo fetch --depth 1 origin $Rama | Out-Host
  git -C $Repo reset --hard "origin/$Rama" | Out-Host
} else {
  git clone --depth 1 --branch $Rama $RepoUrl $Repo | Out-Host
}
Bien "Programa listo"

Paso "Preparando Python y el oído de Cris (Whisper con tu tarjeta de video; la primera vez baja ~2 GB)…"
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) { & $py -m venv $Venv }
$vpy = Join-Path $Venv "Scripts\python.exe"
& $vpy -m pip install -q --upgrade pip | Out-Host
& $vpy -m pip install -q -r (Join-Path $Repo "salaedicion\requirements_compu.txt") | Out-Host
Bien "Listo"

$cfg = Join-Path $Dir "config.json"
$dar_alta = $true
if (Test-Path $cfg) {
  $r = Read-Host "  Esta compu ya estaba dada de alta. ¿Darla de alta otra vez con un código nuevo? (s/N)"
  $dar_alta = ($r -match "^[sS]")
}
if ($dar_alta) {
  Write-Host ""
  Write-Host "  En tu oficina, abre la pestaña 'Sala' y pícale a 'Generar código'." -ForegroundColor Cyan
  $servidor = Read-Host "  Dirección de tu oficina (Enter = https://51-195-201-84.sslip.io)"
  if (-not $servidor) { $servidor = "https://51-195-201-84.sslip.io" }
  $nombre = Read-Host "  Nombre para esta compu (Enter = $env:COMPUTERNAME)"
  if (-not $nombre) { $nombre = $env:COMPUTERNAME }
  while ($true) {
    $codigo = Read-Host "  Código de 6 números"
    & $vpy (Join-Path $Repo "salaedicion\compu.py") --vincular $codigo --servidor $servidor --nombre $nombre
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "  Intenta otra vez (o genera otro código en la pestaña Sala)." -ForegroundColor Red
  }
}

Paso "Haciendo que arranque sola al prender la compu…"
$pyw = Join-Path $Venv "Scripts\pythonw.exe"
$inicio = [Environment]::GetFolderPath("Startup")
$ws = New-Object -ComObject WScript.Shell
$acceso = $ws.CreateShortcut((Join-Path $inicio "Sala de edicion.lnk"))
$acceso.TargetPath = $pyw
$acceso.Arguments = "`"$(Join-Path $Repo 'salaedicion\compu.py')`""
$acceso.WorkingDirectory = $Repo
$acceso.Description = "Sala de edicion: edita los videos de tu oficina"
$acceso.Save()
# acceso en el escritorio para ver qué está haciendo
$escritorio = [Environment]::GetFolderPath("Desktop")
$ver = $ws.CreateShortcut((Join-Path $escritorio "Sala de edicion - que esta haciendo.lnk"))
$ver.TargetPath = "notepad.exe"
$ver.Arguments = "`"$(Join-Path $Dir 'compu.log')`""
$ver.Save()
Bien "Arranca sola al prender la compu"

Paso "Arrancando…"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -like "*salaedicion*compu.py*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Process -FilePath $pyw -ArgumentList "`"$(Join-Path $Repo 'salaedicion\compu.py')`"" -WorkingDirectory $Repo -WindowStyle Hidden
Write-Host ""
Write-Host "  ✅ ¡Listo! Esta compu ya aparece en la Sala de edición de tu oficina (en unos segundos)." -ForegroundColor Green
Write-Host "     Si quieres ver qué está haciendo: 'Sala de edicion - que esta haciendo' en tu escritorio." -ForegroundColor Green
