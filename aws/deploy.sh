#!/bin/bash
set -e

ACCOUNT_ID="006600132909"
REGION="ap-south-1"
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/devops-copilot-swarm"

echo "🔍 Fetching EC2 public IP..."
EC2_IP=$(aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=devops-swarm" "Name=instance-state-name,Values=running" \
    --region $REGION \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

if [ "$EC2_IP" = "None" ] || [ -z "$EC2_IP" ]; then
    echo "❌ Error: No running EC2 instance found with the tag Name=devops-swarm"
    exit 1
fi

echo "🚀 Deploying to AWS..."
echo "   ECR: $ECR_URI"
echo "   EC2: $EC2_IP"

# 1. Build local Docker image
echo "📦 Building Docker image..."
docker build -f docker/Dockerfile -t devops-copilot-swarm .

# 2. Login to ECR
echo "🔑 Logging in to Amazon ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# 3. Tag and Push
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
docker tag devops-copilot-swarm:latest $ECR_URI:latest
docker tag devops-copilot-swarm:latest $ECR_URI:$GIT_SHA
docker push $ECR_URI:latest
docker push $ECR_URI:$GIT_SHA
echo "✅ Image pushed: $ECR_URI:$GIT_SHA"

# 4. SSH into EC2 and recreate container service
echo "🚢 Connecting to EC2 and restarting containers..."
ssh -i devops-swarm-key.pem -o StrictHostKeyChecking=no ubuntu@$EC2_IP << ENDSSH
    aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI
    
    cd /app
    docker-compose -f docker-compose.prod.yml pull
    docker-compose -f docker-compose.prod.yml up -d --force-recreate
    
    echo "✅ Docker deployment completed successfully!"
ENDSSH

echo "🎉 Deployment Complete!"
