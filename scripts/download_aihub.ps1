# AI Hub 데이터셋 다운로드 (Windows native, aihubshell 불필요)
#
# AI Hub는 Linux용 aihubshell 스크립트만 공식 제공하지만, 내부적으로 단순 curl 호출이라
# Windows 10/11 내장 curl.exe로 동등하게 처리 가능.
#
# 사용 전 준비:
#   1. https://aihub.or.kr 로그인 → 마이페이지 → API key 발급 클릭
#   2. 등록된 이메일로 키 수신 (예: 8ac3...d9f2)
#   3. 데이터셋 신청·승인 완료 상태여야 함
#
# 사용 예:
#   $env:AIHUB_API_KEY = "발급받은_키"
#   .\scripts\download_aihub.ps1 -DatasetKey 71560 -Name dialect_jungnoh_gangwon
#   .\scripts\download_aihub.ps1 -DatasetKey 71561 -Name dialect_jungnoh_gyeongsang

param(
    [Parameter(Mandatory=$true)][string]$DatasetKey,
    [Parameter(Mandatory=$true)][string]$Name,
    [string]$ApiKey = $env:AIHUB_API_KEY,
    [string]$BaseDir = "C:\TTT-data\raw",
    [string]$FileKey = "all",
    [switch]$SkipExtract
)

$ErrorActionPreference = "Stop"

if (-not $ApiKey) {
    Write-Error "API key가 없습니다. -ApiKey 인자로 전달하거나 `$env:AIHUB_API_KEY 환경변수 설정."
    exit 1
}

$target = Join-Path $BaseDir $Name
New-Item -ItemType Directory -Force -Path $target | Out-Null

# 드라이브 여유공간 점검 (다운로드 + 압축해제 = 원본의 2~3배 필요)
$drive = Get-PSDrive C
$freeGB = [math]::Round($drive.Free / 1GB, 1)
Write-Host "=== AI Hub 다운로드 ==="
Write-Host "  Dataset Key  : $DatasetKey"
Write-Host "  이름         : $Name"
Write-Host "  저장 경로    : $target"
Write-Host "  C 여유       : $freeGB GB"
if ($freeGB -lt 200) {
    Write-Warning "C 여유 200GB 미만. 압축해제까지 고려하면 부족할 수 있음."
}
Write-Host ""

$tarPath = Join-Path $target "download.tar"
$url = "https://api.aihub.or.kr/down/0.6/$DatasetKey.do?fileSn=$FileKey"

Write-Host "다운로드 시작 (-C - 재개 지원, 크면 수 시간 걸릴 수 있음)..."
& curl.exe -L -C - -o $tarPath -H "apikey:$ApiKey" -w "`nHTTP: %{http_code}`n" $url
if ($LASTEXITCODE -ne 0) {
    Write-Error "curl 실패 (exit $LASTEXITCODE)"
    exit 1
}

if ($SkipExtract) {
    Write-Host "`n압축 해제 건너뜀 (-SkipExtract). download.tar 만 저장됨."
    return
}

Write-Host "`ntar 풀기..."
Push-Location $target
try {
    & tar.exe -xf download.tar
    if ($LASTEXITCODE -ne 0) { throw "tar 실패 (exit $LASTEXITCODE)" }
} finally {
    Pop-Location
}

# AI Hub는 큰 파일을 .part1/.part2/... 로 쪼개서 보내는 경우가 있음. 자동 병합.
$firstParts = Get-ChildItem -Path $target -Recurse -File | Where-Object { $_.Name -match '\.part1$' }
foreach ($firstPart in $firstParts) {
    $baseName = $firstPart.FullName -replace '\.part1$', ''
    $stem = $firstPart.BaseName  # 예: "foo.zip"
    $parts = Get-ChildItem -Path $firstPart.DirectoryName -File |
        Where-Object { $_.Name -match "^$([regex]::Escape($stem))\.part\d+$" } |
        Sort-Object { [int](($_.Name -split '\.part')[-1]) }

    Write-Host "병합: $baseName ($($parts.Count) 파트)"
    $combined = ($parts | ForEach-Object { "`"$($_.FullName)`"" }) -join "+"
    & cmd /c "copy /b $combined `"$baseName`" >nul"
    if ($LASTEXITCODE -eq 0) {
        $parts | Remove-Item -Force
    } else {
        Write-Warning "병합 실패: $baseName (수동 확인 필요)"
    }
}

Write-Host ""
Write-Host "=== 다운로드·압축해제 완료 ==="
Write-Host "다음 단계: 라벨 zip 1개 까서 JSON 구조 확인"
Write-Host "  Get-ChildItem $target -Recurse -Filter '[라벨]*.zip' | Select-Object -First 1"
