@echo off
title DevOps Copilot Swarm — Startup
color 0A

echo.
echo ========================================
echo   DevOps Copilot Swarm - Starting Up
echo ========================================
echo.

:: Option to start AWS Services
set /p START_AWS="Do you also want to start AWS Cloud Services (EC2 & RDS)? [y/N]: "
if /i "%START_AWS%"=="y" goto :AWS_START
if /i "%START_AWS%"=="yes" goto :AWS_START
goto :LOCAL_START

:AWS_START
echo.
echo ========================================
echo   Starting AWS Resources (ap-south-1)
echo ========================================

:: 1. Start EC2 Instance
echo [*] Querying EC2 Instance ID...
for /f "tokens=*" %%i in ('aws ec2 describe-instances --filters "Name=tag:Name,Values=devops-swarm" --query "Reservations[0].Instances[0].InstanceId" --output text --region ap-south-1 2^>nul') do set INSTANCE_ID=%%i

if "%INSTANCE_ID%"=="" (
    echo [ERROR] Could not find EC2 instance named 'devops-swarm'.
    goto :RDS_START
)
if "%INSTANCE_ID%"=="None" (
    echo [ERROR] Could not find EC2 instance named 'devops-swarm'.
    goto :RDS_START
)

echo [*] Starting EC2 Instance (%INSTANCE_ID%)...
aws ec2 start-instances --instance-ids %INSTANCE_ID% --region ap-south-1 > nul 2>&1
echo      Done!

:RDS_START
:: 2. Start RDS Instance
echo [*] Starting RDS Database (devops-swarm-db)...
aws rds start-db-instance --db-instance-identifier devops-swarm-db --region ap-south-1 > nul 2>&1
echo      Done!

echo.
echo [!] Waiting for AWS resources to initialize...
echo     (This may take 1-2 minutes. Monitoring the IP/Endpoint retrieval below.)
timeout /t 15 /nobreak > nul

echo [*] Querying EC2 Public IP...
for /f "tokens=*" %%i in ('aws ec2 describe-instances --filters "Name=tag:Name,Values=devops-swarm" --query "Reservations[0].Instances[0].PublicIpAddress" --output text --region ap-south-1 2^>nul') do set EC2_IP=%%i

echo [*] Querying RDS DB Endpoint...
for /f "tokens=*" %%i in ('aws rds describe-db-instances --db-instance-identifier devops-swarm-db --query "DBInstances[0].Endpoint.Address" --output text --region ap-south-1 2^>nul') do set RDS_ENDPOINT=%%i

echo.
echo ========================================
echo   AWS Cloud Resource Status
echo ========================================
echo   EC2 Public IP   : %EC2_IP%
echo   RDS Endpoint    : %RDS_ENDPOINT%
echo ========================================
echo.

:LOCAL_START
:: Step 1 — Start Docker Desktop
echo [1/6] Starting Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
timeout /t 15 /nobreak > nul
echo      Done!

:: Step 2 — Start PostgreSQL
echo [2/6] Starting PostgreSQL...
docker start devops-postgres > nul 2>&1
timeout /t 5 /nobreak > nul
echo      Done!

:: Step 3 — Start Redis
echo [3/6] Starting Redis...
docker start devops-redis > nul 2>&1
timeout /t 3 /nobreak > nul
echo      Done!

:: Step 4 — Start Minikube
echo [4/6] Starting Minikube...
minikube start > nul 2>&1
timeout /t 10 /nobreak > nul
echo      Done!

:: Step 5 — Activate venv and start server
echo [5/6] Starting Backend Server...
start "DevOps Swarm Server" cmd /k "cd /d D:\devops-copilot-swarm && venv\Scripts\activate && python run.py"
timeout /t 8 /nobreak > nul
echo      Done!

:: Step 6 — Open Dashboard
echo [6/6] Opening Dashboard...
timeout /t 3 /nobreak > nul
start http://localhost:8080/dashboard/index.html
echo      Done!

echo.
echo ========================================
echo   All Systems Running!
echo ========================================
echo.
echo   Local Dashboard : http://localhost:8080/dashboard/index.html
echo   Local API Docs  : http://localhost:8080/docs
echo   Local Health    : http://localhost:8080/health
if not "%EC2_IP%"="" (
    if not "%EC2_IP%"=="None" (
        echo.
        echo   AWS EC2 Host    : http://%EC2_IP%/dashboard/index.html
        echo   AWS API Health  : http://%EC2_IP%/health
    )
)
echo ===========================================
echo.
pause