# Manual Deployment Guide for Object Matching Application

## Prerequisites

Before starting, ensure you have:
- Azure CLI installed and configured
- Docker installed and running
- Azure subscription with appropriate permissions
- Your project structure with `backend/` and `frontend/` directories

## Step 1: Login to Azure

```bash
# Login to Azure
az login

# Verify your subscription
az account show

# Set subscription if needed
az account set --subscription "your-subscription-id"
```

## Step 2: Create Resource Group

```bash
# Set your variables
$RESOURCE_GROUP="object-matching-rg"
$LOCATION="eastus"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION
```

## Step 3: Create Container Registry

```bash
$CONTAINER_REGISTRY="objectmatchingregistry"

# Create container registry
az acr create   --resource-group $RESOURCE_GROUP   --name $CONTAINER_REGISTRY   --sku Basic   --admin-enabled true

# Get registry credentials
$REGISTRY_USERNAME=$(az acr credential show --name $CONTAINER_REGISTRY --query username -o tsv)
$REGISTRY_PASSWORD=$(az acr credential show --name $CONTAINER_REGISTRY --query passwords[0].value -o tsv)

echo "Registry Username: $REGISTRY_USERNAME"
echo "Registry Password: $REGISTRY_PASSWORD"
```

## Step 4: Create Storage Account and File Share

```bash
$STORAGE_ACCOUNT="objectmatchingstorage"
$STORAGE_SHARE="objectmatchingshare"

# Create storage account
az storage account create   --resource-group $RESOURCE_GROUP   --name $STORAGE_ACCOUNT   --location $LOCATION   --sku Standard_LRS   --kind StorageV2

# Get storage account key
$STORAGE_KEY=$(az storage account keys list  --resource-group $RESOURCE_GROUP  --account-name $STORAGE_ACCOUNT  --query '[0].value' -o tsv)

# Create file share
az storage share create   --account-name $STORAGE_ACCOUNT   --account-key $STORAGE_KEY   --name $STORAGE_SHARE   --quota 10

echo "Storage Key: $STORAGE_KEY"
```

## Step 5: Build and Push Backend Image

```bash
$BACKEND_IMAGE="objectmatchingregistry.azurecr.io/object-matching-backend:latest"

# Navigate to your project root directory
cd /path/to/your/project

# Build backend image
docker build -t $BACKEND_IMAGE ./backend

# Login to container registry
docker login objectmatchingregistry.azurecr.io --username $REGISTRY_USERNAME  # copy the password

# Push backend image
docker push $BACKEND_IMAGE
```

## Step 6: Build and Push Frontend Image

```bash
$FRONTEND_IMAGE="objectmatchingregistry.azurecr.io/object-matching-frontend:latest"

# Build frontend image
docker build -t $FRONTEND_IMAGE ./frontend

# Push frontend image
docker push $FRONTEND_IMAGE
```

## Step 7: Deploy Backend Container

```bash
$BACKEND_CONTAINER="object-matching-backend"

# Create backend container instance
az container create   --resource-group $RESOURCE_GROUP   --name $BACKEND_CONTAINER   --image $BACKEND_IMAGE   --cpu 2   --memory 4   --registry-login-server objectmatchingregistry.azurecr.io   --registry-username $REGISTRY_USERNAME   --registry-password $REGISTRY_PASSWORD   --dns-name-label $BACKEND_CONTAINER   --ports 8000   --environment-variables PYTHONPATH=/app UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000   --azure-file-volume-account-name $STORAGE_ACCOUNT   --azure-file-volume-account-key $STORAGE_KEY   --azure-file-volume-share-name $STORAGE_SHARE   --azure-file-volume-mount-path /app/data   --restart-policy Always --os-type linux

# Or if is already running delete it and recreate
az container delete --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --yes

# Get backend FQDN
$BACKEND_FQDN=$(az container show --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --query ipAddress.fqdn -o tsv)

echo "Backend URL: http://$BACKEND_FQDN:8000"
echo "Backend API Docs: http://$BACKEND_FQDN:8000/docs"
```

## Step 8: Deploy Frontend Container

```bash
$FRONTEND_CONTAINER="object-matching-frontend"

# Create frontend container instance
az container create  --resource-group $RESOURCE_GROUP  --name $FRONTEND_CONTAINER  --image $FRONTEND_IMAGE  --cpu 1  --memory 2  --registry-login-server objectmatchingregistry.azurecr.io  --registry-username $REGISTRY_USERNAME  --registry-password $REGISTRY_PASSWORD  --dns-name-label $FRONTEND_CONTAINER  --ports 3000  --environment-variables REACT_APP_API_URL=http://$BACKEND_FQDN:8000  --restart-policy Always --os-type linux

# Or if is already running delete it and recreate
az container delete --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER --yes


# Get frontend FQDN
$FRONTEND_FQDN=$(az container show --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER --query ipAddress.fqdn -o tsv)

echo "Frontend URL: http://$FRONTEND_FQDN:3000"
```

## Step 9: Verify Deployment

```bash
# Check container status
az container show --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --query instanceView.state -o tsv
az container show --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER --query instanceView.state -o tsv

# View container logs
az container logs --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER
az container logs --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER
```

## Troubleshooting Commands

### View Live Logs
```bash
# Backend logs
az container logs --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --follow

# Frontend logs
az container logs --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER --follow
```

### Restart Containers
```bash
# Restart backend
az container restart --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER

# Restart frontend
az container restart --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER
```

### Check Container Details
```bash
# Get detailed info
az container show --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER
az container show --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER
```

## Common Issues and Solutions

### 1. Registry Name Conflicts
If you get an error about registry name already existing:
```bash
# Check if registry exists globally
az acr show --name $CONTAINER_REGISTRY

# Use a different registry name
$CONTAINER_REGISTRY="objectmatchingregistry$(date +%s)"
```

### 2. Storage Account Name Conflicts
```bash
# Use a different storage account name
$STORAGE_ACCOUNT="objectmatchingstorage$(date +%s)"
```

### 3. Container Start Issues
```bash
# Check container events
az container show --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --query instanceView.events

# Check if images are accessible
az acr repository show --name $CONTAINER_REGISTRY --image object-matching-backend:latest
```

### 4. Network Connectivity Issues
```bash
# Test backend connectivity
curl http://$BACKEND_FQDN:8000/health

# Check if ports are open
az container show --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --query ipAddress.ports
```

## Cleanup (When Done Testing)

```bash
# Delete the entire resource group
az group delete --name $RESOURCE_GROUP --yes --no-wait

# Or delete individual resources
az container delete --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --yes
az container delete --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER --yes
az acr delete --name $CONTAINER_REGISTRY --resource-group $RESOURCE_GROUP --yes
az storage account delete --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --yes
```

## Environment Variables Summary

For reference, here are all the variables used:

```bash
$RESOURCE_GROUP="object-matching-rg"
$LOCATION="eastus"
$CONTAINER_REGISTRY="objectmatchingregistry"
$STORAGE_ACCOUNT="objectmatchingstorage"
$STORAGE_SHARE="objectmatchingshare"
$BACKEND_CONTAINER="object-matching-backend"
$FRONTEND_CONTAINER="object-matching-frontend"
$BACKEND_IMAGE="objectmatchingregistry.azurecr.io/object-matching-backend:latest"
$FRONTEND_IMAGE="objectmatchingregistry.azurecr.io/object-matching-frontend:latest"
```

## Next Steps

1. Test your application by accessing the frontend URL
2. Verify the backend API is working by checking the `/docs` endpoint
3. Monitor logs for any issues
4. Consider setting up monitoring and alerting for production use
5. Configure custom domains and SSL certificates if needed

Remember to replace the placeholder values with your actual project paths and preferred naming conventions.