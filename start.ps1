# businessintelligence.ai - Local Stack Runner (PowerShell)
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  businessintelligence.ai - Stack Startup Script  " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Write-Host "Notice: .env not found. Copying from .env.example..." -ForegroundColor Yellow
        Copy-Item ".env.example" ".env"
    }
}

Write-Host "" 
Write-Host "[1/2] Launching Backend API (FastAPI) on http://localhost:8000..." -ForegroundColor Green
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "Set-Location backend; python -m uvicorn api.main:app --reload --port 8000"

Write-Host "[2/2] Launching Frontend (Next.js) on http://localhost:3000..." -ForegroundColor Green
Start-Process pwsh -ArgumentList "-NoExit", "-Command", "Set-Location web; npm run dev"

Write-Host ""
Write-Host "Stack launched!" -ForegroundColor Cyan
Write-Host "  Backend API : http://localhost:8000" -ForegroundColor White
Write-Host "  Swagger Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  Web App     : http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "Each service runs in its own terminal window." -ForegroundColor Gray
