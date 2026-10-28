param(
    [ValidateRange(1, 60)][int]$Seconds = 8,
    [string]$Name = 'startup-lfq-explicit-nosys',
    [string]$AtomEa = ''
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root 'build/motorstorm/MotorStormPacificRiftRecomp.exe'
$elf = Join-Path $root 'generated/decrypted/EBOOT.elf'
$game = Join-Path $root 'original/game'
$logs = Join-Path $root 'generated/logs'
foreach ($required in @($exe, $elf, $game)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing local input: $required" }
}
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$stdout = Join-Path $logs "$Name-stdout.log"
$stderr = Join-Path $logs "$Name-stderr.log"
$env:PS3_VFS_ROOT = $game
$env:SPURS_LFQ_TRACE = '1'
if ($AtomEa) { $env:SPU_LFQ_ATOM_EA = $AtomEa }
$process = Start-Process -FilePath $exe -ArgumentList ('"' + $elf + '"') `
    -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout `
    -RedirectStandardError $stderr
try {
    if (-not $process.WaitForExit($Seconds * 1000)) {
        Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        $process.WaitForExit()
        Write-Output "TIMEOUT ${Seconds}s pid=$($process.Id) stdout=$stdout stderr=$stderr"
    } else {
        Write-Output "EXIT $($process.ExitCode) pid=$($process.Id) stdout=$stdout stderr=$stderr"
    }
} finally {
    Remove-Item Env:SPURS_LFQ_TRACE -ErrorAction SilentlyContinue
    Remove-Item Env:SPU_LFQ_ATOM_EA -ErrorAction SilentlyContinue
}
