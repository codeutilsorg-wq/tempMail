# EasyTempInbox Deployment Script
# Usage: .\deploy.ps1 [all|parser|api|frontend]

param(
    [Parameter(Position=0)]
    [ValidateSet("all", "parser", "api", "frontend")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
$BackendDir = Join-Path $ProjectRoot "backend"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  EasyTempInbox Deployment Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Deploy-EmailParser {
    Write-Host "[1/3] Deploying Email Parser Lambda..." -ForegroundColor Yellow
    
    $lambdaDir = Join-Path $BackendDir "lambda"
    Set-Location $lambdaDir
    
    # Clean old packages
    Write-Host "  - Cleaning old packages..."
    Get-ChildItem -Exclude email_parser.py,models,email_parser.zip -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    
    # Install dependencies for Linux
    Write-Host "  - Installing Linux dependencies..."
    pip install --platform manylinux2014_x86_64 --target . --implementation cp --python-version 3.12 --only-binary=:all: -r ..\requirements.txt --quiet
    
    # Copy models
    Write-Host "  - Copying models..."
    Remove-Item models -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -Path ..\models -Destination . -Recurse
    
    # Create zip
    Write-Host "  - Creating deployment package..."
    Remove-Item email_parser.zip -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path * -DestinationPath email_parser.zip -Force
    
    # Deploy to AWS
    Write-Host "  - Deploying to AWS Lambda..."
    aws lambda update-function-code --function-name easytempinbox-email-parser --zip-file fileb://email_parser.zip --no-cli-pager
    
    Write-Host "  [OK] Email Parser deployed!" -ForegroundColor Green
    Set-Location $ProjectRoot
}

function Deploy-Api {
    Write-Host "[2/3] Deploying API Lambda..." -ForegroundColor Yellow
    
    $apiDir = Join-Path $BackendDir "api"
    Set-Location $apiDir
    
    # Clean old packages
    Write-Host "  - Cleaning old packages..."
    Get-ChildItem -Exclude main.py,models,api.zip -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    
    # Install dependencies for Linux
    Write-Host "  - Installing Linux dependencies..."
    pip install --platform manylinux2014_x86_64 --target . --implementation cp --python-version 3.12 --only-binary=:all: -r ..\requirements.txt --quiet
    
    # Copy models
    Write-Host "  - Copying models..."
    Remove-Item models -Recurse -Force -ErrorAction SilentlyContinue
    Copy-Item -Path ..\models -Destination . -Recurse
    
    # Create zip
    Write-Host "  - Creating deployment package..."
    Remove-Item api.zip -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path * -DestinationPath api.zip -Force
    
    # Deploy to AWS
    Write-Host "  - Deploying to AWS Lambda..."
    aws lambda update-function-code --function-name easytempinbox-api --zip-file fileb://api.zip --no-cli-pager
    
    Write-Host "  [OK] API deployed!" -ForegroundColor Green
    Set-Location $ProjectRoot
}

function Deploy-Frontend {
    Write-Host "[3/3] Deploying Frontend..." -ForegroundColor Yellow
    
    $frontendDir = Join-Path $ProjectRoot "frontend"
    
    # Sync to S3
    Write-Host "  - Syncing to S3..."
    aws s3 sync $frontendDir s3://www.easytempinbox.com --delete --no-cli-pager
    
    Write-Host "  [OK] Frontend deployed!" -ForegroundColor Green
}

# Execute based on target
switch ($Target) {
    "all" {
        Deploy-EmailParser
        Write-Host ""
        Deploy-Api
        Write-Host ""
        Deploy-Frontend
    }
    "parser" {
        Deploy-EmailParser
    }
    "api" {
        Deploy-Api
    }
    "frontend" {
        Deploy-Frontend
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Website: https://www.easytempinbox.com" -ForegroundColor Cyan
Write-Host ""
