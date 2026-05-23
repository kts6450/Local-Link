# 저장소 루트에 .env 생성 (.env.example 복사)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile = Join-Path $Root ".env"
$Example = Join-Path $Root ".env.example"

if (-not (Test-Path $Example)) {
    Write-Error ".env.example 이 없습니다"
    exit 1
}
if (Test-Path $EnvFile) {
    Write-Host "이미 있습니다: $EnvFile"
    Write-Host "덮어쓰려면 Remove-Item .env 후 다시 실행"
    exit 0
}
Copy-Item $Example $EnvFile
Write-Host "생성됨: $EnvFile"
Write-Host "TTT_MODEL_ID=elderly_command 등을 확인한 뒤 백엔드를 재시작하세요."
