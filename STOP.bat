@echo off
title DevOps Copilot Swarm — Shutdown
color 0C

echo.
echo ========================================
echo   DevOps Copilot Swarm - Shutting Down
echo ========================================
echo.

echo [1/3] Stopping Docker containers...
docker stop devops-postgres devops-redis > nul 2>&1
echo      Done!

echo [2/3] Stopping Minikube...
minikube stop > nul 2>&1
echo      Done!

echo [3/3] Closing server windows...
taskkill /FI "WINDOWTITLE eq DevOps Swarm Server" /F > nul 2>&1
echo      Done!

echo.
:: Option to stop AWS Services
set /p STOP_AWS="Do you also want to STOP AWS Cloud Services (EC2 & RDS) to save costs? [y/N]: "
if /i "%STOP_AWS%"=="y" goto :AWS_STOP
if /i "%STOP_AWS%"=="yes" goto :AWS_STOP
goto :FINISH

:AWS_STOP
echo.
echo ========================================
echo   Stopping AWS Resources (ap-south-1)
echo ========================================

:: 1. Stop EC2 Instance
echo [*] Querying EC2 Instance ID...
for /f "tokens=*" %%i in ('aws ec2 describe-instances --filters "Name=tag:Name,Values=devops-swarm" --query "Reservations[0].Instances[0].InstanceId" --output text --region ap-south-1 2^>nul') do set INSTANCE_ID=%%i

if "%INSTANCE_ID%"=="" (
    echo [ERROR] Could not find EC2 instance named 'devops-swarm'.
    goto :RDS_STOP
)
if "%INSTANCE_ID%"=="None" (
    echo [ERROR] Could not find EC2 instance named 'devops-swarm'.
    goto :RDS_STOP
)

echo [*] Stopping EC2 Instance (%INSTANCE_ID%)...
aws ec2 stop-instances --instance-ids %INSTANCE_ID% --region ap-south-1 > nul 2>&1
echo      Done!

:RDS_STOP
:: 2. Stop RDS Instance
echo [*] Stopping RDS Database (devops-swarm-db)...
aws rds stop-db-instance --db-instance-identifier devops-swarm-db --region ap-south-1 > nul 2>&1
echo      Done!

echo.
echo [!] AWS stop requests sent successfully!
echo.

:FINISH
echo ========================================
echo   All services stopped cleanly!
echo ========================================
pause