param(
    [string]$Test = "smoke",
    [string]$URL  = "https://13.126.249.86.nip.io"
)
Write-Host "🚀 Running k6 $Test test against $URL" -ForegroundColor Cyan
switch ($Test) {
    "smoke" {
        & "C:\Program Files\k6\k6.exe" run --vus 1 --duration 30s `
            --env BASE_URL=$URL `
            tests/load/k6_test.js
    }
    "load" {
        & "C:\Program Files\k6\k6.exe" run --vus 10 --duration 5m `
            --env BASE_URL=$URL `
            tests/load/k6_test.js
    }
    "stress" {
        & "C:\Program Files\k6\k6.exe" run --vus 50 --duration 10m `
            --env BASE_URL=$URL `
            tests/load/k6_test.js
    }
    "spike" {
        & "C:\Program Files\k6\k6.exe" run --vus 100 --duration 2m `
            --env BASE_URL=$URL `
            tests/load/k6_test.js
    }
}
