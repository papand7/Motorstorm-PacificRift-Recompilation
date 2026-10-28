param(
    [ValidateRange(1, 600)][int]$Seconds = 8,
    [string]$Name = 'first-frame',
    [switch]$SilentAudio,
    [switch]$FirstFrame,
    [ValidateSet('native', 'silent', 'unavailable')][string]$AudioPolicy = 'silent',
    [string]$AtomEa = '',
    # Optional alternate executable (e.g. the trace-hooked build); default unchanged.
    [string]$Exe = ''
)

# Development profile: original PPU/SPU and RSX paths remain enabled. The
# optional silent path asks cellAudio to report unavailable, not success.
$ErrorActionPreference = 'Stop'
if ($FirstFrame -and $SilentAudio) {
    throw 'Use -AudioPolicy unavailable with -FirstFrame; -SilentAudio is the legacy audio-unavailable switch.'
}
if (-not $FirstFrame -and $PSBoundParameters.ContainsKey('AudioPolicy')) {
    throw '-AudioPolicy requires -FirstFrame.'
}
$root = Split-Path -Parent $PSScriptRoot
$exe = if ($Exe) { $Exe } else { Join-Path $root 'build/motorstorm/MotorStormPacificRiftRecomp.exe' }
$elf = Join-Path $root 'generated/decrypted/EBOOT.elf'
$game = Join-Path $root 'original/game'
$logs = Join-Path $root 'generated/logs'
foreach ($required in @($exe, $elf, $game)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing local input: $required" }
}
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$saved = @{}
$names = @('PS3_VFS_ROOT', 'SPURS_LFQ_TRACE', 'SPU_LFQ_ATOM_EA',
           'PS3_NET_ONLINE', 'PS3_NO_AUDIO', 'FIRST_FRAME', 'FIRST_FRAME_AUDIO')
foreach ($key in $names) { $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
try {
    [Environment]::SetEnvironmentVariable('PS3_VFS_ROOT', $game, 'Process')
    # Keep a caller's larger SPURS_LFQ_TRACE budget (N > 1); default 1.
    [Environment]::SetEnvironmentVariable('SPURS_LFQ_TRACE', $(if ($saved['SPURS_LFQ_TRACE']) { $saved['SPURS_LFQ_TRACE'] } else { '1' }), 'Process')
    [Environment]::SetEnvironmentVariable('SPU_LFQ_ATOM_EA', $(if ($AtomEa) { $AtomEa } else { $saved['SPU_LFQ_ATOM_EA'] }), 'Process')
    [Environment]::SetEnvironmentVariable('PS3_NET_ONLINE', $null, 'Process')
    [Environment]::SetEnvironmentVariable('PS3_NO_AUDIO', $(if ($SilentAudio) { '1' } else { $null }), 'Process')
    [Environment]::SetEnvironmentVariable('FIRST_FRAME', $(if ($FirstFrame) { '1' } else { $null }), 'Process')
    [Environment]::SetEnvironmentVariable('FIRST_FRAME_AUDIO', $(if ($FirstFrame) { $AudioPolicy } else { $null }), 'Process')
    if ($FirstFrame) {
        Write-Output "FIRST_FRAME audio=$AudioPolicy network=offline trophy=existing input=existing savedata=existing"
    }
    $stdout = Join-Path $logs "$Name-stdout.log"
    $stderr = Join-Path $logs "$Name-stderr.log"
    $process = Start-Process -FilePath $exe -ArgumentList ('"' + $elf + '"') `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr
    if (-not $process.WaitForExit($Seconds * 1000)) {
        # Whole-process cost at the cut-off (tracer overhead comparisons).
        $process.Refresh()
        Write-Output ("CPU {0:N1}s peakWS {1:N0}MB peakPrivate {2:N0}MB" -f `
            $process.TotalProcessorTime.TotalSeconds, ($process.PeakWorkingSet64 / 1MB), `
            ($process.PeakPagedMemorySize64 / 1MB))
        Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
        $process.WaitForExit()
        Write-Output "TIMEOUT ${Seconds}s pid=$($process.Id) stdout=$stdout stderr=$stderr"
    } else {
        Write-Output "EXIT $($process.ExitCode) pid=$($process.Id) stdout=$stdout stderr=$stderr"
    }
} finally {
    foreach ($key in $names) {
        [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process')
    }
}
