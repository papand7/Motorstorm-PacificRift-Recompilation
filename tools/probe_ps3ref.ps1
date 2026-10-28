param(
  [string]$Self = 'build/ps3ref/spurs.self',
  [int]$Seconds = 15,
  [string]$Name = 'spurs-sample'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$rpcs3 = Join-Path $root 'build/rpcs3/rpcs3.exe'
$target = (Resolve-Path (Join-Path $root $Self)).Path
$outDir = Join-Path $root 'build/ps3ref'
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$stdout = Join-Path $outDir "$Name-stdout.log"
$stderr = Join-Path $outDir "$Name-stderr.log"
$existing = Get-Process rpcs3 -ErrorAction SilentlyContinue
if ($existing) {
  throw "RPCS3 is already running (PID $($existing.Id -join ', ')); stop or isolate that session before probing."
}

$process = $null
try {
  $process = Start-Process -FilePath $rpcs3 -ArgumentList @('--no-gui', ('"' + $target + '"')) -WorkingDirectory (Split-Path $rpcs3) -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
  Write-Output "RPCS3 reference PID $($process.Id)"
  Start-Sleep -Seconds $Seconds
} finally {
  if ($process -and -not $process.HasExited) {
    Stop-Process -Id $process.Id -Force
    $process.WaitForExit(5000) | Out-Null
  }
  $rpcs3Log = Join-Path $root 'build/rpcs3/log/RPCS3.log'
  if (Test-Path -LiteralPath $rpcs3Log) {
    Copy-Item -LiteralPath $rpcs3Log -Destination (Join-Path $outDir "$Name-rpcs3.log") -Force
  }
  Write-Output "Reference logs: $outDir"
}
