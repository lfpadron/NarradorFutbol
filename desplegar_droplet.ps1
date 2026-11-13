# Despliega en el droplet la version que ya esta publicada en GitHub.
# Usa la llave "futbol" situada junto a este script, sin importar desde donde se ejecute.
# Compatible con Windows PowerShell 5.1 y PowerShell 7.

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# Los errores de SSH se muestran directamente y su codigo se procesa abajo.
if (Test-Path variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

try {
    $keyPath = Join-Path $PSScriptRoot 'futbol'
    if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) {
        throw "No se encontro la llave SSH: $keyPath"
    }

    $sshCommand = Get-Command ssh.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1
    $sshArguments = @(
        '-i', $keyPath,
        '-o', 'IdentitiesOnly=yes',
        '-o', 'ConnectTimeout=15',
        '-o', 'ServerAliveInterval=15',
        '-o', 'ServerAliveCountMax=3',
        'root@161.35.127.211',
        'bash -se'
    )

    # Bash detiene el despliegue en el primer error y devuelve su codigo a SSH.
    # No se imprime el contenido de la llave ni del archivo de entorno.
    $remoteScript = @'
set -Eeuo pipefail
step="Iniciar despliegue"
trap 'rc=$?; printf "\nERROR: %s (codigo %s).\n" "$step" "$rc" >&2; exit "$rc"' ERR

step="Acceder a /opt/astrogato-missions/narradorfutbol"
printf '\n[1/4] %s\n' "$step"
cd -- /opt/astrogato-missions/narradorfutbol

step="Verificar Git, Docker Compose y deploy/cpanel/analista-futbol.env"
command -v git >/dev/null
command -v docker >/dev/null
docker compose version
test -f deploy/cpanel/analista-futbol.env

step="Actualizar el codigo desde GitHub"
printf '\n[2/4] %s\n' "$step"
git pull --ff-only

step="Reconstruir e iniciar la aplicacion; esperar su comprobacion de salud"
printf '\n[3/4] %s\n' "$step"
docker compose --env-file deploy/cpanel/analista-futbol.env -f deploy/cpanel/compose.analista-futbol.yaml up -d --build --wait --wait-timeout 180

step="Consultar el estado de los contenedores"
printf '\n[4/4] %s\n' "$step"
docker compose --env-file deploy/cpanel/analista-futbol.env -f deploy/cpanel/compose.analista-futbol.yaml ps

printf '\nDespliegue remoto completado correctamente.\n'
exit 0
'@

    Write-Host 'Desplegando Narrador de Futbol en root@161.35.127.211...' -ForegroundColor Cyan
    Write-Host 'Se descargara la version publicada en GitHub. Los cambios locales deben subirse primero.'
    Write-Host 'SSH puede solicitar la frase de la llave o confirmar la identidad del servidor.'
    Write-Host ''

    # Normalizar a LF para Bash. La linea final evita que el CRLF de la tuberia
    # de Windows forme parte del ultimo comando remoto.
    ($remoteScript.Replace("`r`n", "`n") + "`n") | & $sshCommand.Source @sshArguments
    $deployExitCode = $LASTEXITCODE
    if ($deployExitCode -ne 0) {
        [Console]::Error.WriteLine("ERROR: el despliegue fallo (codigo $deployExitCode). Revisa el error original mostrado arriba.")
        exit $deployExitCode
    }

    Write-Host 'EXITO: la aplicacion fue actualizada y su comprobacion de salud termino correctamente.' -ForegroundColor Green
    exit 0
}
catch {
    [Console]::Error.WriteLine("ERROR: $($_.Exception.Message)")
    exit 1
}
