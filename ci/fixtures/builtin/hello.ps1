$ErrorActionPreference = "Stop"
$sum = (2,3,5 | Measure-Object -Sum).Sum
if ($sum -ne 10) { throw "PowerShell smoke assertion failed" }
Write-Output "ZEIBAEL_POWERSHELL_OK"
