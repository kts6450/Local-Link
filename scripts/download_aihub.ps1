# AI Hub 데이터셋 다운로드 헬퍼 (Windows PowerShell)
#
# 사용 예:
#   .\scripts\download_aihub.ps1 -DatasetKey 71560 -Name dialect_jungnoh_gangwon
#   .\scripts\download_aihub.ps1 -DatasetKey 71561 -Name dialect_jungnoh_gyeongsang
#
# 사전 준비:
#   1. aihubshell 설치:  pip install aihubshell
#   2. AI Hub 로그인:    aihubshell -mode l -id <your-id> -pw <your-pw>
#   3. 데이터 신청 승인 완료 상태여야 함

param(
    [Parameter(Mandatory=$true)][string]$DatasetKey,
    [Parameter(Mandatory=$true)][string]$Name,
    [string]$BaseDir = "C:\TTT-data\raw"
)

$ErrorActionPreference = "Stop"

$target = Join-Path $BaseDir $Name
New-Item -ItemType Directory -Force -Path $target | Out-Null

Write-Host "=== AI Hub 다운로드 ==="
Write-Host "  Dataset Key : $DatasetKey"
Write-Host "  이름        : $Name"
Write-Host "  저장 경로   : $target"
Write-Host ""

# C 드라이브 여유공간 사전 점검
$drive = Get-PSDrive C
$freeGB = [math]::Round($drive.Free / 1GB, 1)
Write-Host "C 드라이브 여유: $freeGB GB"
if ($freeGB -lt 200) {
    Write-Warning "C 드라이브 여유 공간이 200GB 미만입니다. 진행 전 D로 기존 데이터 이동을 고려하세요."
}
Write-Host ""

aihubshell -mode d -datasetkey $DatasetKey -o $target

Write-Host ""
Write-Host "=== 다운로드 완료 ==="
Write-Host "다음 단계:"
Write-Host "  1. 라벨 zip 1개 열어 JSON 구조 확인"
Write-Host "     예: Expand-Archive `"$target\Training\[라벨]*.zip`" -DestinationPath C:\tmp\peek -Force"
Write-Host "  2. preprocess_zip.py 의 라벨 파싱 로직 확인/수정"
Write-Host "  3. 전처리 실행"
