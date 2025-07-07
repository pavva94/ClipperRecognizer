# Object Matching Application - Azure Deployment Guide

This guide provides step-by-step instructions for deploying the Object Matching Application to Azure Container Instances.

## Prerequisites

1. **Azure CLI** - Install from [here](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
2. **Docker** - Install from [here](https://www.docker.com/products/docker-desktop)
3. **Azure Subscription** - Active Azure subscription

## Project Structure

```
object-matching-app/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── object_matching_api.py
│   └── object_matching.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── public/
│   │   └── index.html
│   └── src/
│       ├── App.js
│       ├── ObjectMatchingApp.jsx
│       ├── index.js
│       └── index.css
├── docker-compose.yml
├── deploy-azure.sh
├── azure-template.json
└── README.md
```

## Setup Instructions

### 1. Clone and Prepare the Project

```bash
# Create project directory
mkdir object-matching-app
cd object-matching-app

# Create backend directory
mkdir backend
cd backend

# Copy your API files here
# - object_matching_api.py (your main API file)
# - object_matching.py (your core logic)
# - requirements.txt
# - Dockerfile

cd ..

# Create frontend directory
mkdir frontend
cd frontend

# Create the frontend structure as described in the frontend files
```

### 2. Configure Backend

Place your `object_matching_api.py` and `object_matching.py` files in the `backend/` directory.

Create or update `backend/requirements.txt`:

```text
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6
pydantic==2.5.0
opencv-python==4.8.1.78
numpy==1.24.3
pillow==10.1.0
ultralytics==8.0.206
torch==2.1.0
torchvision==0.16.0
torchaudio==2.1.0
aiofiles==0.22.0
```

### 3. Configure Frontend

Create the frontend structure and files as described in the frontend artifact.

### 4. Local Testing (Optional)

Test locally using Docker Compose:

```bash
# Build and run locally
docker-compose up --build

# Access the application
# Backend: http://localhost:8000
# Frontend: http://localhost:3000
```

### 5. Deploy to Azure

#### Option A: Using the Deployment Script (Recommended)

```bash
# Make the script executable
chmod +x deploy-azure.sh

# Deploy the application
./deploy-azure.sh deploy

# Other useful commands:
./deploy-azure.sh logs     # View container logs
./deploy-azure.sh restart  # Restart containers
./deploy-azure.sh status   # Show deployment status
./deploy-azure.sh cleanup  # Delete all resources
```

#### Option B: Manual Azure CLI Commands

```bash
# Login to Azure
az login

# Create resource group
az group create --name object-matching-rg --location eastus

# Create container registry
az acr create --resource-group object-matching-rg --name objectmatchingregistry --sku Basic --admin-enabled true

# Build and push backend image
az acr build --registry objectmatchingregistry --image object-matching-backend:latest ./backend

# Build and push frontend image
az acr build --registry objectmatchingregistry --image object-matching-frontend:latest ./frontend

# Deploy using ARM template
az deployment group create --resource-group object-matching-rg --template-file azure-template.json
```

#### Option C: Using ARM Template

```bash
# Deploy using Azure Resource Manager template
az deployment group create \
  --resource-group object-matching-rg \
  --template-file azure-template.json \
  --parameters @azure-parameters.json
```

## Configuration Files

### Backend Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "object_matching_api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Frontend Dockerfile

```dockerfile
FROM node:18-alpine as build

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=build /app/build /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

### Docker Compose Configuration

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
    networks:
      - object-matching-network

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend
    environment:
      - REACT_APP_API_URL=http://backend:8000
    networks:
      - object-matching-network

networks:
  object-matching-network:
    driver: bridge
```

### Azure ARM Template (azure-template.json)

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "containerRegistryName": {
      "type": "string",
      "defaultValue": "objectmatchingregistry"
    },
    "location": {
      "type": "string",
      "defaultValue": "[resourceGroup().location]"
    }
  },
  "variables": {
    "containerRegistryLoginServer": "[concat(parameters('containerRegistryName'), '.azurecr.io')]",
    "backendImageName": "[concat(variables('containerRegistryLoginServer'), '/object-matching-backend:latest')]",
    "frontendImageName": "[concat(variables('containerRegistryLoginServer'), '/object-matching-frontend:latest')]"
  },
  "resources": [
    {
      "type": "Microsoft.ContainerInstance/containerGroups",
      "apiVersion": "2021-09-01",
      "name": "object-matching-containers",
      "location": "[parameters('location')]",
      "properties": {
        "containers": [
          {
            "name": "backend",
            "properties": {
              "image": "[variables('backendImageName')]",
              "ports": [
                {
                  "port": 8000,
                  "protocol": "TCP"
                }
              ],
              "resources": {
                "requests": {
                  "cpu": 1,
                  "memoryInGB": 2
                }
              },
              "environmentVariables": [
                {
                  "name": "PYTHONUNBUFFERED",
                  "value": "1"
                }
              ]
            }
          },
          {
            "name": "frontend",
            "properties": {
              "image": "[variables('frontendImageName')]",
              "ports": [
                {
                  "port": 80,
                  "protocol": "TCP"
                }
              ],
              "resources": {
                "requests": {
                  "cpu": 0.5,
                  "memoryInGB": 1
                }
              },
              "environmentVariables": [
                {
                  "name": "REACT_APP_API_URL",
                  "value": "http://localhost:8000"
                }
              ]
            }
          }
        ],
        "osType": "Linux",
        "ipAddress": {
          "type": "Public",
          "ports": [
            {
              "protocol": "TCP",
              "port": 80
            },
            {
              "protocol": "TCP",
              "port": 8000
            }
          ]
        },
        "imageRegistryCredentials": [
          {
            "server": "[variables('containerRegistryLoginServer')]",
            "username": "[parameters('containerRegistryName')]",
            "password": "[listCredentials(resourceId('Microsoft.ContainerRegistry/registries', parameters('containerRegistryName')), '2021-09-01').passwords[0].value]"
          }
        ]
      },
      "dependsOn": []
    }
  ],
  "outputs": {
    "applicationUrl": {
      "type": "string",
      "value": "[concat('http://', reference('object-matching-containers').ipAddress.ip)]"
    },
    "backendUrl": {
      "type": "string",
      "value": "[concat('http://', reference('object-matching-containers').ipAddress.ip, ':8000')]"
    }
  }
}
```

### Deployment Script (deploy-azure.sh)

```bash
#!/bin/bash

# Configuration
RESOURCE_GROUP="object-matching-rg"
REGISTRY_NAME="objectmatchingregistry"
LOCATION="eastus"
CONTAINER_GROUP="object-matching-containers"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Azure CLI is installed
check_prerequisites() {
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
}

# Login to Azure
azure_login() {
    log_info "Checking Azure login status..."
    if ! az account show &> /dev/null; then
        log_info "Please login to Azure..."
        az login
    fi
}

# Create resource group
create_resource_group() {
    log_info "Creating resource group: $RESOURCE_GROUP"
    az group create --name $RESOURCE_GROUP --location $LOCATION
}

# Create container registry
create_container_registry() {
    log_info "Creating container registry: $REGISTRY_NAME"
    az acr create --resource-group $RESOURCE_GROUP --name $REGISTRY_NAME --sku Basic --admin-enabled true
}

# Build and push images
build_and_push_images() {
    log_info "Building and pushing backend image..."
    az acr build --registry $REGISTRY_NAME --image object-matching-backend:latest ./backend
    
    log_info "Building and pushing frontend image..."
    az acr build --registry $REGISTRY_NAME --image object-matching-frontend:latest ./frontend
}

# Deploy containers
deploy_containers() {
    log_info "Deploying containers using ARM template..."
    az deployment group create \
        --resource-group $RESOURCE_GROUP \
        --template-file azure-template.json \
        --parameters containerRegistryName=$REGISTRY_NAME
}

# Get deployment status
get_status() {
    log_info "Getting deployment status..."
    az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP --query "provisioningState" -o tsv
    
    # Get public IP
    IP=$(az container show --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP --query "ipAddress.ip" -o tsv)
    if [ ! -z "$IP" ]; then
        log_info "Application URL: http://$IP"
        log_info "Backend API URL: http://$IP:8000"
    fi
}

# View logs
view_logs() {
    log_info "Viewing container logs..."
    echo "Backend logs:"
    az container logs --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP --container-name backend
    echo "Frontend logs:"
    az container logs --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP --container-name frontend
}

# Restart containers
restart_containers() {
    log_info "Restarting containers..."
    az container restart --resource-group $RESOURCE_GROUP --name $CONTAINER_GROUP
}

# Cleanup resources
cleanup_resources() {
    log_warn "This will delete all resources in the resource group: $RESOURCE_GROUP"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deleting resource group and all resources..."
        az group delete --name $RESOURCE_GROUP --yes --no-wait
        log_info "Cleanup initiated. Resources will be deleted in the background."
    else
        log_info "Cleanup cancelled."
    fi
}

# Main deployment function
deploy() {
    check_prerequisites
    azure_login
    create_resource_group
    create_container_registry
    build_and_push_images
    deploy_containers
    get_status
    log_info "Deployment completed successfully!"
}

# Main script logic
case "$1" in
    deploy)
        deploy
        ;;
    status)
        get_status
        ;;
    logs)
        view_logs
        ;;
    restart)
        restart_containers
        ;;
    cleanup)
        cleanup_resources
        ;;
    *)
        echo "Usage: $0 {deploy|status|logs|restart|cleanup}"
        echo "  deploy  - Deploy the application to Azure"
        echo "  status  - Show deployment status and URLs"
        echo "  logs    - View container logs"
        echo "  restart - Restart containers"
        echo "  cleanup - Delete all Azure resources"
        exit 1
        ;;
esac
```

### Frontend Nginx Configuration (nginx.conf)

```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    error_page 500 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
    }
}
```

## Post-Deployment

### 1. Verify Deployment

After deployment, verify that both containers are running:

```bash
# Check container status
az container show --resource-group object-matching-rg --name object-matching-containers

# View logs
az container logs --resource-group object-matching-rg --name object-matching-containers --container-name backend
az container logs --resource-group object-matching-rg --name object-matching-containers --container-name frontend
```

### 2. Access Your Application

Once deployed, you can access your application using the public IP address provided in the deployment output:

- **Frontend**: `http://[PUBLIC_IP]`
- **Backend API**: `http://[PUBLIC_IP]:8000`

### 3. Scaling and Management

To scale your application or make updates:

```bash
# Update the container group (after pushing new images)
az container create --resource-group object-matching-rg --file azure-template.json

# Scale resources by modifying the ARM template and redeploying
az deployment group create --resource-group object-matching-rg --template-file azure-template.json
```

## Troubleshooting

### Common Issues

1. **Container Registry Authentication**
   - Ensure admin user is enabled: `az acr update --name objectmatchingregistry --admin-enabled true`
   - Verify credentials: `az acr credential show --name objectmatchingregistry`

2. **Container Startup Issues**
   - Check container logs: `az container logs --resource-group object-matching-rg --name object-matching-containers --container-name backend`
   - Verify image tags and registry paths

3. **Network Connectivity**
   - Ensure ports are properly exposed in the container group
   - Check firewall rules and network security groups

4. **Resource Limits**
   - Monitor CPU and memory usage
   - Increase resource allocations in the ARM template if needed

### Monitoring and Logging

Enable monitoring for your container instances:

```bash
# Enable monitoring
az monitor diagnostic-settings create \
    --resource /subscriptions/[SUBSCRIPTION_ID]/resourceGroups/object-matching-rg/providers/Microsoft.ContainerInstance/containerGroups/object-matching-containers \
    --name container-diagnostics \
    --logs '[{"category": "ContainerInstanceLog", "enabled": true}]' \
    --workspace [LOG_ANALYTICS_WORKSPACE_ID]
```

## Cost Optimization

To minimize costs:

1. **Use appropriate resource sizes** - Start with minimal CPU/memory and scale up as needed
2. **Stop containers when not in use** - Use `az container stop` for development environments
3. **Use Azure Container Instances for development** - Consider Azure Kubernetes Service (AKS) for production
4. **Monitor usage** - Set up billing alerts and resource usage monitoring

## Security Considerations

1. **Enable HTTPS** - Use Azure Application Gateway or Azure Front Door for SSL termination
2. **Network security** - Implement network security groups and private endpoints
3. **Secret management** - Use Azure Key Vault for sensitive configuration
4. **Regular updates** - Keep base images and dependencies updated

## Next Steps

1. **Set up CI/CD** - Implement automated deployment using Azure DevOps or GitHub Actions
2. **Add monitoring** - Set up Application Insights for detailed monitoring
3. **Implement logging** - Add structured logging to your application
4. **Add authentication** - Implement Azure Active Directory integration if needed

This completes the Azure deployment guide for your Object Matching Application. The setup provides a production-ready deployment with proper scaling, monitoring, and management capabilities.