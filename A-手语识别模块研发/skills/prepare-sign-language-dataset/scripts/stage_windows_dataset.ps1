param(
  [Parameter(Mandatory=$true)][string]$SourceRoot,
  [string]$Distro = 'Ubuntu-24.04',
  [string]$LinuxStage = '/home/bestfunc/sign-dataset-stage'
)
$ErrorActionPreference='Stop'
$resolved=(Resolve-Path -LiteralPath $SourceRoot).Path
$uncSuffix=$LinuxStage.TrimStart('/').Replace('/','\')
$target="\\wsl.localhost\$Distro\$uncSuffix"
New-Item -ItemType Directory -Force -Path $target | Out-Null
$videos=Get-ChildItem -LiteralPath $resolved -File -Recurse | Where-Object {$_.Extension.ToLower() -in @('.mp4','.mov','.mkv','.avi','.webm','.m4v')}
$manifest=@()
foreach($video in $videos){
  $relative=$video.FullName.Substring($resolved.Length).TrimStart('\')
  $dest=Join-Path $target $relative
  New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
  Copy-Item -LiteralPath $video.FullName -Destination $dest -Force
  $linuxPath=($LinuxStage.TrimEnd('/')+'/'+$relative.Replace('\','/'))
  $manifest+=[pscustomobject]@{original_path=$video.FullName;staged_path=$linuxPath;bytes=$video.Length;sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath $video.FullName).Hash}
}
$manifest | Export-Csv -LiteralPath (Join-Path $target 'source_manifest.csv') -NoTypeInformation -Encoding UTF8
Write-Output ([pscustomobject]@{source=$resolved;target=$target;videos=$videos.Count})
