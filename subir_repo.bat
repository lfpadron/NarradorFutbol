@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "REPO_URL=https://github.com/lfpadron/NarradorFutbol.git"
set "DEFAULT_BRANCH=main"
set "MODE=%~1"

if /I "%MODE%"=="help" goto :help
if /I "%MODE%"=="-h" goto :help
if /I "%MODE%"=="/?" goto :help
if /I "%MODE%"=="check" (
    set "SAVE_DIFF=N"
    set "DIFF_ONLY=N"
    set "PREFLIGHT_ONLY=S"
    goto :run
)
if /I "%MODE%"=="push" (
    set "SAVE_DIFF=N"
    set "DIFF_ONLY=N"
    goto :run
)
if /I "%MODE%"=="diff" (
    set "SAVE_DIFF=S"
    set "DIFF_ONLY=N"
    goto :run
)
if /I "%MODE%"=="diff-only" (
    set "SAVE_DIFF=S"
    set "DIFF_ONLY=S"
    goto :run
)
if not "%MODE%"=="" (
    echo Opcion no reconocida: %MODE%
    echo.
    goto :help
)

:menu
echo.
echo ==========================================
echo  NarradorFutbol - publicar en GitHub
echo ==========================================
echo Repo: %REPO_URL%
echo.
echo 1. Subir codigo
echo 2. Guardar diff seguro y subir codigo
echo 3. Solo guardar diff seguro
echo 4. Salir
echo.
choice /C 1234 /N /M "Elige una opcion [1-4]: "
if errorlevel 4 exit /b 0
if errorlevel 3 (
    set "SAVE_DIFF=S"
    set "DIFF_ONLY=S"
    goto :run
)
if errorlevel 2 (
    set "SAVE_DIFF=S"
    set "DIFF_ONLY=N"
    goto :run
)
set "SAVE_DIFF=N"
set "DIFF_ONLY=N"
goto :run

:run
call :require_git
if errorlevel 1 exit /b 1
call :ensure_repo
if errorlevel 1 exit /b 1

if /I "%DIFF_ONLY%"=="S" (
    call :save_working_diff
    if errorlevel 1 exit /b 1
    echo.
    echo Diff guardado. No se hizo commit ni push.
    exit /b 0
)

call :ensure_origin
if errorlevel 1 exit /b 1
call :current_branch
if errorlevel 1 exit /b 1
call :refresh_origin
if errorlevel 1 exit /b 1
call :guard_unpushed_history
if errorlevel 1 exit /b 1

if /I "%PREFLIGHT_ONLY%"=="S" (
    echo.
    echo Preparando cambios para revision segura...
    call :stage_safe_changes
    if errorlevel 1 exit /b 1
    echo.
    echo Revision lista. Cambios seguros preparados. No se hizo commit ni push.
    exit /b 0
)

echo.
echo Estado actual:
git status --short
echo.

set "COMMIT_MSG="
set /p "COMMIT_MSG=Mensaje de commit [Actualiza NarradorFutbol]: "
if not defined COMMIT_MSG set "COMMIT_MSG=Actualiza NarradorFutbol"

echo.
echo Preparando cambios...
call :stage_safe_changes
if errorlevel 1 exit /b 1

if /I "%SAVE_DIFF%"=="S" (
    call :save_staged_diff
    if errorlevel 1 exit /b 1
    call :unstage_blocked_files
)

git diff --cached --quiet
if errorlevel 1 (
    echo.
    echo Creando commit...
    git commit -m "%COMMIT_MSG%"
    if errorlevel 1 (
        echo.
        echo No se pudo crear el commit. Revisa git config user.name/user.email o el estado del repo.
        exit /b 1
    )
) else (
    echo.
    echo No hay cambios preparados para commit. Se intentara hacer push de la rama actual.
)

echo.
echo Subiendo rama !BRANCH! a origin...
git push -u origin "!BRANCH!"
if errorlevel 1 (
    echo.
    echo No se pudo hacer push. Revisa credenciales, permisos o conexion con GitHub.
    exit /b 1
)

echo.
echo Listo. Codigo subido a %REPO_URL%
exit /b 0

:require_git
where git >nul 2>nul
if errorlevel 1 (
    echo Git no esta disponible en PATH.
    exit /b 1
)
exit /b 0

:ensure_repo
git rev-parse --is-inside-work-tree >nul 2>nul
if not errorlevel 1 exit /b 0

echo No se detecto un repositorio Git en esta carpeta.
choice /C SN /M "Inicializar git aqui"
if errorlevel 2 exit /b 1

git init
if errorlevel 1 exit /b 1
exit /b 0

:ensure_origin
set "CURRENT_ORIGIN="
for /f "delims=" %%R in ('git remote get-url origin 2^>nul') do set "CURRENT_ORIGIN=%%R"

if not defined CURRENT_ORIGIN (
    echo Agregando remote origin: %REPO_URL%
    git remote add origin "%REPO_URL%"
    if errorlevel 1 exit /b 1
    exit /b 0
)

if /I "!CURRENT_ORIGIN!"=="%REPO_URL%" exit /b 0

echo Remote origin actual:
echo !CURRENT_ORIGIN!
echo.
echo Remote esperado:
echo %REPO_URL%
echo.
choice /C SN /M "Cambiar origin al repo esperado"
if errorlevel 2 exit /b 1

git remote set-url origin "%REPO_URL%"
if errorlevel 1 exit /b 1
exit /b 0

:refresh_origin
echo.
echo Actualizando referencia remota...
git fetch origin --prune
if errorlevel 1 (
    echo No se pudo actualizar origin. Revisa conexion o credenciales antes de publicar.
    exit /b 1
)
exit /b 0

:guard_unpushed_history
set "REMOTE_REF=origin/!BRANCH!"
git rev-parse --verify "!REMOTE_REF!" >nul 2>nul
if errorlevel 1 set "REMOTE_REF=origin/%DEFAULT_BRANCH%"
git rev-parse --verify "!REMOTE_REF!" >nul 2>nul
if errorlevel 1 (
    echo No se encontro una referencia remota para comparar historia local.
    exit /b 1
)

echo.
echo Revisando historia local no subida contra !REMOTE_REF!...
set "BLOCKED_HISTORY="
for /f "delims=" %%F in ('git diff --name-only "!REMOTE_REF!..HEAD" -- "diff_*.txt" "*.patch" "*.key" "*.pem" "*.ppk" "*.p8" "*.p12" "*.pub" "id_rsa" "id_ed25519" "futbol" "futbol.pub" ".env" ".env.*" "*.db" "*.duckdb" "*.sqlite" "*.sqlite3" 2^>nul') do (
    echo  - Archivo bloqueado en historia: %%F
    set "BLOCKED_HISTORY=S"
)
if /I "!BLOCKED_HISTORY!"=="S" (
    echo.
    echo No se hara push: la historia local contiene archivos bloqueados.
    echo Crea una rama limpia desde !REMOTE_REF! o reescribe la historia antes de publicar.
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$limit=95MB; $bad=$false; git rev-list --objects '!REMOTE_REF!..HEAD' | ForEach-Object { $parts = $_ -split ' ', 2; if ($parts.Count -lt 2) { return }; $sizeText = git cat-file -s $parts[0] 2>$null; if ($LASTEXITCODE -ne 0) { return }; $size = [int64]$sizeText; if ($size -ge $limit) { Write-Output ('  - {0} ({1:N1} MB)' -f $parts[1], ($size/1MB)); $bad = $true } }; if ($bad) { exit 1 }"
if errorlevel 1 (
    echo.
    echo No se hara push: hay blobs mayores o iguales a 95 MB en commits no subidos.
    echo GitHub rechaza archivos grandes; limpia la historia antes de publicar.
    exit /b 1
)

set "SECRET_HISTORY="
for /f "delims=" %%F in ('git grep -I -l -E "^[[:space:]]*-{5}BEGIN [A-Z ]*PRIVATE KEY-{5}" HEAD -- . 2^>nul') do (
    echo  - Posible secreto rastreado: %%F
    set "SECRET_HISTORY=S"
)
if /I "!SECRET_HISTORY!"=="S" (
    echo.
    echo No se hara push: se detecto material tipo PRIVATE KEY en archivos rastreados.
    echo Mueve la llave fuera del repo y limpia la historia antes de publicar.
    exit /b 1
)
exit /b 0

:current_branch
set "BRANCH="
for /f "delims=" %%B in ('git branch --show-current 2^>nul') do set "BRANCH=%%B"
if defined BRANCH exit /b 0

set "BRANCH=%DEFAULT_BRANCH%"
git branch -M "%DEFAULT_BRANCH%" >nul 2>nul
exit /b 0

:stage_safe_changes
git add -u -- .
if errorlevel 1 (
    echo Error al preparar cambios rastreados con git add.
    exit /b 1
)
for /f "delims=" %%F in ('git ls-files --others --exclude-standard') do (
    git add -- "%%F"
    if errorlevel 1 (
        echo Error al preparar archivo nuevo: %%F
        exit /b 1
    )
)
call :unstage_blocked_files
call :guard_staged_blocked_files
if errorlevel 1 exit /b 1
call :guard_staged_large_files
if errorlevel 1 exit /b 1
call :guard_staged_secrets
if errorlevel 1 exit /b 1
exit /b 0

:guard_staged_blocked_files
set "BLOCKED_STAGED="
for /f "delims=" %%F in ('git diff --cached --name-only -- "diff_*.txt" "*.patch" "*.key" "*.pem" "*.ppk" "*.p8" "*.p12" "*.pub" "id_rsa" "id_ed25519" "futbol" "futbol.pub" ".env" ".env.*" "*.db" "*.duckdb" "*.sqlite" "*.sqlite3" 2^>nul') do (
    echo  - Archivo bloqueado preparado: %%F
    set "BLOCKED_STAGED=S"
)
if /I "!BLOCKED_STAGED!"=="S" (
    echo.
    echo No se creara commit: hay archivos bloqueados preparados.
    exit /b 1
)
exit /b 0

:guard_staged_large_files
powershell -NoProfile -ExecutionPolicy Bypass -Command "$limit=95MB; $bad=$false; git diff --cached --name-only --diff-filter=AMR | ForEach-Object { if (Test-Path -LiteralPath $_) { $item = Get-Item -LiteralPath $_; if ($item.Length -ge $limit) { Write-Output ('  - {0} ({1:N1} MB)' -f $_, ($item.Length/1MB)); $bad = $true } } }; if ($bad) { exit 1 }"
if errorlevel 1 (
    echo.
    echo No se creara commit: hay archivos preparados mayores o iguales a 95 MB.
    exit /b 1
)
exit /b 0

:guard_staged_secrets
set "SECRET_STAGED="
for /f "delims=" %%F in ('git grep --cached -I -l -E "^[[:space:]]*-{5}BEGIN [A-Z ]*PRIVATE KEY-{5}" -- . 2^>nul') do (
    echo  - Posible secreto preparado: %%F
    set "SECRET_STAGED=S"
)
if /I "!SECRET_STAGED!"=="S" (
    echo.
    echo No se creara commit: se detecto material tipo PRIVATE KEY en cambios preparados.
    exit /b 1
)
exit /b 0

:timestamp
set "STAMP="
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%T"
if not defined STAMP set "STAMP=%RANDOM%"
exit /b 0

:save_working_diff
call :timestamp
set "DIFF_FILE=diff_!STAMP!.txt"
echo Guardando diff en !DIFF_FILE!...
(
    echo NarradorFutbol - git diff
    echo Fecha: !STAMP!
    echo Repo: %REPO_URL%
    echo.
    echo ===== git status --short =====
    git status --short
    echo.
    call :write_safe_working_diff
) > "!DIFF_FILE!"
if errorlevel 1 (
    echo No se pudo guardar el diff.
    exit /b 1
)
echo Diff guardado en !DIFF_FILE!
exit /b 0

:save_staged_diff
call :timestamp
set "DIFF_FILE=diff_!STAMP!.txt"
echo Guardando diff preparado en !DIFF_FILE!...
(
    echo NarradorFutbol - git diff preparado para commit
    echo Fecha: !STAMP!
    echo Repo: %REPO_URL%
    echo.
    echo ===== git status --short =====
    git status --short
    echo.
    call :write_safe_staged_diff
) > "!DIFF_FILE!"
if errorlevel 1 (
    echo No se pudo guardar el diff preparado.
    exit /b 1
)
echo Diff guardado en !DIFF_FILE!
exit /b 0

:write_safe_working_diff
echo ===== git diff --stat =====
git diff --stat -- . ^
    ":(exclude)diff_*.txt" ^
    ":(exclude)*.patch" ^
    ":(exclude)*.key" ^
    ":(exclude)*.pem" ^
    ":(exclude)*.ppk" ^
    ":(exclude)*.p8" ^
    ":(exclude)*.p12" ^
    ":(exclude)*.pub" ^
    ":(exclude)id_rsa" ^
    ":(exclude)id_ed25519" ^
    ":(exclude)futbol" ^
    ":(exclude)futbol.pub" ^
    ":(exclude).env" ^
    ":(exclude).env.*" ^
    ":(exclude)*.db" ^
    ":(exclude)*.duckdb" ^
    ":(exclude)*.sqlite" ^
    ":(exclude)*.sqlite3"
echo.
echo ===== git diff =====
git diff -- . ^
    ":(exclude)diff_*.txt" ^
    ":(exclude)*.patch" ^
    ":(exclude)*.key" ^
    ":(exclude)*.pem" ^
    ":(exclude)*.ppk" ^
    ":(exclude)*.p8" ^
    ":(exclude)*.p12" ^
    ":(exclude)*.pub" ^
    ":(exclude)id_rsa" ^
    ":(exclude)id_ed25519" ^
    ":(exclude)futbol" ^
    ":(exclude)futbol.pub" ^
    ":(exclude).env" ^
    ":(exclude).env.*" ^
    ":(exclude)*.db" ^
    ":(exclude)*.duckdb" ^
    ":(exclude)*.sqlite" ^
    ":(exclude)*.sqlite3"
echo.
echo ===== git diff --cached --stat =====
git diff --cached --stat -- . ^
    ":(exclude)diff_*.txt" ^
    ":(exclude)*.patch" ^
    ":(exclude)*.key" ^
    ":(exclude)*.pem" ^
    ":(exclude)*.ppk" ^
    ":(exclude)*.p8" ^
    ":(exclude)*.p12" ^
    ":(exclude)*.pub" ^
    ":(exclude)id_rsa" ^
    ":(exclude)id_ed25519" ^
    ":(exclude)futbol" ^
    ":(exclude)futbol.pub" ^
    ":(exclude).env" ^
    ":(exclude).env.*" ^
    ":(exclude)*.db" ^
    ":(exclude)*.duckdb" ^
    ":(exclude)*.sqlite" ^
    ":(exclude)*.sqlite3"
echo.
echo ===== git diff --cached =====
git diff --cached -- . ^
    ":(exclude)diff_*.txt" ^
    ":(exclude)*.patch" ^
    ":(exclude)*.key" ^
    ":(exclude)*.pem" ^
    ":(exclude)*.ppk" ^
    ":(exclude)*.p8" ^
    ":(exclude)*.p12" ^
    ":(exclude)*.pub" ^
    ":(exclude)id_rsa" ^
    ":(exclude)id_ed25519" ^
    ":(exclude)futbol" ^
    ":(exclude)futbol.pub" ^
    ":(exclude).env" ^
    ":(exclude).env.*" ^
    ":(exclude)*.db" ^
    ":(exclude)*.duckdb" ^
    ":(exclude)*.sqlite" ^
    ":(exclude)*.sqlite3"
exit /b 0

:write_safe_staged_diff
echo ===== git diff --cached --stat =====
git diff --cached --stat -- . ^
    ":(exclude)diff_*.txt" ^
    ":(exclude)*.patch" ^
    ":(exclude)*.key" ^
    ":(exclude)*.pem" ^
    ":(exclude)*.ppk" ^
    ":(exclude)*.p8" ^
    ":(exclude)*.p12" ^
    ":(exclude)*.pub" ^
    ":(exclude)id_rsa" ^
    ":(exclude)id_ed25519" ^
    ":(exclude)futbol" ^
    ":(exclude)futbol.pub" ^
    ":(exclude).env" ^
    ":(exclude).env.*" ^
    ":(exclude)*.db" ^
    ":(exclude)*.duckdb" ^
    ":(exclude)*.sqlite" ^
    ":(exclude)*.sqlite3"
echo.
echo ===== git diff --cached =====
git diff --cached -- . ^
    ":(exclude)diff_*.txt" ^
    ":(exclude)*.patch" ^
    ":(exclude)*.key" ^
    ":(exclude)*.pem" ^
    ":(exclude)*.ppk" ^
    ":(exclude)*.p8" ^
    ":(exclude)*.p12" ^
    ":(exclude)*.pub" ^
    ":(exclude)id_rsa" ^
    ":(exclude)id_ed25519" ^
    ":(exclude)futbol" ^
    ":(exclude)futbol.pub" ^
    ":(exclude).env" ^
    ":(exclude).env.*" ^
    ":(exclude)*.db" ^
    ":(exclude)*.duckdb" ^
    ":(exclude)*.sqlite" ^
    ":(exclude)*.sqlite3"
exit /b 0

:unstage_blocked_files
for %%F in (diff_*.txt *.patch *.key *.pem *.ppk *.p8 *.p12 *.pub id_rsa id_ed25519 futbol futbol.pub .env .env.* *.db *.duckdb *.sqlite *.sqlite3) do (
    if exist "%%F" git reset -q -- "%%F" >nul 2>nul
)
exit /b 0

:help
echo Uso:
echo   subir_repo.bat            Muestra menu interactivo
echo   subir_repo.bat check      Revisa y prepara cambios seguros sin commit ni push
echo   subir_repo.bat push       Sube codigo sin guardar diff
echo   subir_repo.bat diff       Guarda diff seguro y sube codigo
echo   subir_repo.bat diff-only  Solo guarda diff seguro
echo.
echo Repo configurado:
echo   %REPO_URL%
exit /b 0
