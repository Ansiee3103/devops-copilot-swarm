# DevOps Copilot Swarm - PowerShell Deployment Script
$ErrorActionPreference = "Stop"

# Change directory to the project root directory
$PROJECT_ROOT = Split-Path $PSScriptRoot -Parent
Set-Location $PROJECT_ROOT

$ACCOUNT_ID = "006600132909"
$REGION = "ap-south-1"
$ECR_URI = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/devops-copilot-swarm"

Write-Host "[*] Fetching EC2 public IP..." -ForegroundColor Cyan
$EC2_IP = aws ec2 describe-instances `
    --filters "Name=tag:Name,Values=devops-swarm" "Name=instance-state-name,Values=running" `
    --region $REGION `
    --query "Reservations[0].Instances[0].PublicIpAddress" `
    --output text

if ($null -eq $EC2_IP -or $EC2_IP -eq "None" -or $EC2_IP -eq "") {
    Write-Error "[-] Error: No running EC2 instance found with the tag Name=devops-swarm"
    exit 1
}

Write-Host "[+] Deploying to AWS..." -ForegroundColor Green
Write-Host "   ECR: $ECR_URI"
Write-Host "   EC2: $EC2_IP"

# 1. Build local Docker image
Write-Host "[*] Building Docker image..." -ForegroundColor Cyan
docker build -f docker/Dockerfile -t devops-copilot-swarm .

# 2. Login to ECR
Write-Host "[*] Logging in to Amazon ECR..." -ForegroundColor Cyan
$loginPassword = aws ecr get-login-password --region $REGION
$loginPassword | docker login --username AWS --password-stdin $ECR_URI

# 3. Tag and Push
Write-Host "[*] Tagging and pushing image..." -ForegroundColor Cyan
docker tag devops-copilot-swarm:latest "${ECR_URI}:latest"
docker push "${ECR_URI}:latest"

# Try to get git SHA for unique tagging
try {
    $GIT_SHA = (git rev-parse --short HEAD 2>$null)
    if ($null -ne $GIT_SHA) {
        $GIT_SHA = $GIT_SHA.Trim()
        if ($GIT_SHA -ne "") {
            docker tag devops-copilot-swarm:latest "${ECR_URI}:${GIT_SHA}"
            docker push "${ECR_URI}:${GIT_SHA}"
            Write-Host "[+] Image pushed: ${ECR_URI}:${GIT_SHA}" -ForegroundColor Green
        }
    }
} catch {
    Write-Host "[!] Warning: Could not tag with Git SHA, skipped." -ForegroundColor Yellow
}

# 4. SSH into EC2 and recreate container service
Write-Host "[*] Connecting to EC2 and restarting containers..." -ForegroundColor Cyan
$sshCommand = "aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI && cd /app && docker-compose -f docker-compose.prod.yml pull && docker-compose -f docker-compose.prod.yml up -d --force-recreate"

ssh -i devops-swarm-key.pem -o StrictHostKeyChecking=no "ubuntu@$EC2_IP" $sshCommand

Write-Host "[+] Deployment Complete!" -ForegroundColor Green
