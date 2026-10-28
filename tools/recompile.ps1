param(
    [string]$Elf = 'generated/decrypted/EBOOT.elf'
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$sdk = Join-Path $projectRoot 'ps3recomp'
$python = if ($env:PYTHON) { $env:PYTHON } elseif (Test-Path 'C:\Program Files\PyManager\python.exe') { 'C:\Program Files\PyManager\python.exe' } else { (& py -3 -c 'import sys;print(sys.executable)') }
$elfPath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $Elf))
$analysis = Join-Path $projectRoot 'generated/analysis'
$ppu = Join-Path $projectRoot 'generated/ppu'
$logs = Join-Path $projectRoot 'generated/logs'
New-Item -ItemType Directory -Force $analysis, $ppu, $logs | Out-Null

if (-not (Test-Path -LiteralPath $elfPath -PathType Leaf)) {
    throw "Missing decrypted ELF: $elfPath"
}
$stream = [System.IO.File]::OpenRead($elfPath)
try {
    $header = New-Object byte[] 20
    if ($stream.Read($header, 0, 20) -ne 20 -or
        $header[0] -ne 0x7f -or $header[1] -ne 0x45 -or
        $header[2] -ne 0x4c -or $header[3] -ne 0x46 -or
        $header[4] -ne 2 -or $header[5] -ne 2 -or
        $header[18] -ne 0 -or $header[19] -ne 0x15) {
        throw 'Input must be a decrypted, big-endian ELF64 PowerPC executable; SELF is rejected.'
    }
} finally { $stream.Dispose() }

Get-FileHash -LiteralPath $elfPath -Algorithm SHA256 |
    Format-List | Out-File (Join-Path $logs 'decrypted-elf-hash.txt')

function Invoke-Tool([string]$name, [string[]]$arguments) {
    $log = Join-Path $logs "$name.log"
    "python $($arguments -join ' ')" | Out-File $log
    & $python @arguments 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { throw "$name failed ($LASTEXITCODE); see $log" }
}

$base = [System.IO.Path]::GetFileNameWithoutExtension($elfPath)
Invoke-Tool 'ppu-loader' @((Join-Path $sdk 'tools/ppu_loader.py'), $elfPath, '-o', $analysis)
$functions = Join-Path $analysis "$base.functions.json"
$imports = Join-Path $analysis "$base.imports.json"
$functionCount = @((Get-Content -Raw -LiteralPath $functions | ConvertFrom-Json)).Count
if ($functionCount -eq 0) { throw "Loader found no PPU functions; inspect $analysis before lifting." }

Invoke-Tool 'ppu-lifter' @((Join-Path $sdk 'tools/ppu_lifter.py'), $elfPath,
    '--functions', $functions, '--hle-stubs', $imports, '--output', $ppu, '--jobs', '4')
Invoke-Tool 'hle-nids' @((Join-Path $sdk 'tools/gen_hle_nids.py'), '--all',
    '--out', (Join-Path $ppu 'ppu_hle_nids.cpp'))

$port = Join-Path $projectRoot 'port'
if (-not (Test-Path -LiteralPath $port)) {
    Copy-Item -LiteralPath (Join-Path $sdk 'templates/project') -Destination $port -Recurse
    $cmake = Join-Path $port 'CMakeLists.txt'
    (Get-Content -Raw -LiteralPath $cmake).Replace('MyGameRecomp', 'MotorStormPacificRiftRecomp') |
        Set-Content -LiteralPath $cmake
}

$spuInput = Join-Path $logs 'spu-discovery.log'
& $python (Join-Path $sdk 'tools/extract_spu_images.py') $elfPath '-o' (Join-Path $projectRoot 'generated/spu') 2>&1 |
    Tee-Object -FilePath $spuInput
Write-Host "SPU discovery exit code: $LASTEXITCODE (see $spuInput)"

& (Join-Path $PSScriptRoot 'build_port.cmd')
if ($LASTEXITCODE -ne 0) { throw "Native build failed ($LASTEXITCODE)." }
