#!/bin/bash

# Azure Container Instance Deployment Script for Object Matching Application
# This script deploys both backend and frontend as separate container instances

set -e

# Configuration variables
RESOURCE_GROUP="object-matching-rg"
LOCATION="eastus"
CONTAINER_REGISTRY="objectmatchingregistry"
BACKEND_IMAGE="objectmatchingregistry.azurecr.io/object-matching-backend:latest"
FRONTEND_IMAGE="objectmatchingregistry.azurecr.io/object-matching-frontend:latest"
BACKEND_CONTAINER="object-matching-backend"
FRONTEND_CONTAINER="object-matching-frontend"
STORAGE_ACCOUNT="objectmatchingstorage"
STORAGE_SHARE="objectmatchingshare"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to check if Azure CLI is installed
check_azure_cli() {
    if ! command -v az &> /dev/null; then
        print_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    print_status "Azure CLI is installed"
}

# Function to check if user is logged in
check_azure_login() {
    if ! az account show &> /dev/null; then
        print_error "Please login to Azure CLI first: az login"
        sleep 60
        exit 1
    fi
    print_status "User is logged in to Azure"
}

# Function to create resource group
create_resource_group() {
    print_header "Creating Resource Group"

    if az group show --name $RESOURCE_GROUP &> /dev/null; then
        print_warning "Resource group $RESOURCE_GROUP already exists"
    else
        print_status "Creating resource group: $RESOURCE_GROUP"
        az group create --name $RESOURCE_GROUP --location $LOCATION
        print_status "Resource group created successfully"
    fi
}

# Function to check existing container registry and handle conflicts
check_existing_registry() {
    print_header "Checking Container Registry"

    # Check if registry exists globally (without specifying resource group)
    if az acr show --name $CONTAINER_REGISTRY &> /dev/null; then
        # Get the actual resource group where the registry exists
        ACTUAL_RG=$(az acr show --name $CONTAINER_REGISTRY --query resourceGroup -o tsv)

        if [ "$ACTUAL_RG" != "$RESOURCE_GROUP" ]; then
            print_warning "Container registry $CONTAINER_REGISTRY exists in resource group: $ACTUAL_RG"
            print_warning "Expected resource group: $RESOURCE_GROUP"

            read -p "Do you want to use the existing registry in $ACTUAL_RG? (y/N): " -n 1 -r
            echo

            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_status "Using existing registry in $ACTUAL_RG"
                # Update the resource group for registry operations
                REGISTRY_RESOURCE_GROUP=$ACTUAL_RG
            else
                print_error "Please either:"
                print_error "1. Delete the existing registry: az acr delete --name $CONTAINER_REGISTRY --resource-group $ACTUAL_RG"
                print_error "2. Use a different registry name in the script"
                exit 1
            fi
        else
            print_status "Container registry exists in correct resource group"
            REGISTRY_RESOURCE_GROUP=$RESOURCE_GROUP
        fi
    else
        print_status "Container registry does not exist, will create new one"
        REGISTRY_RESOURCE_GROUP=$RESOURCE_GROUP
    fi
}

# Function to create container registry
create_container_registry() {
    print_header "Creating Container Registry"

    if az acr show --name $CONTAINER_REGISTRY --resource-group $REGISTRY_RESOURCE_GROUP &> /dev/null; then
        print_warning "Container registry $CONTAINER_REGISTRY already exists"
    else
        print_status "Creating container registry: $CONTAINER_REGISTRY"
        az acr create --resource-group $REGISTRY_RESOURCE_GROUP --name $CONTAINER_REGISTRY --sku Basic --admin-enabled true
        print_status "Container registry created successfully"
    fi

    # Get registry credentials
    REGISTRY_USERNAME=$(az acr credential show --name $CONTAINER_REGISTRY --query username -o tsv)
    REGISTRY_PASSWORD=$(az acr credential show --name $CONTAINER_REGISTRY --query passwords[0].value -o tsv)

    print_status "Registry credentials obtained"
}

# Function to create storage account and file share
create_storage() {
    print_header "Creating Storage Account"

    if az storage account show --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP &> /dev/null; then
        print_warning "Storage account $STORAGE_ACCOUNT already exists"
    else
        print_status "Creating storage account: $STORAGE_ACCOUNT"
        az storage account create \
            --resource-group $RESOURCE_GROUP \
            --name $STORAGE_ACCOUNT \
            --location $LOCATION \
            --sku Standard_LRS \
            --kind StorageV2
        print_status "Storage account created successfully"
    fi

    # Get storage account key
    STORAGE_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT --query '[0].value' -o tsv)

    # Create file share
    print_status "Creating file share: $STORAGE_SHARE"
    az storage share create \
        --account-name $STORAGE_ACCOUNT \
        --account-key $STORAGE_KEY \
        --name $STORAGE_SHARE \
        --quota 10 \
        --output none 2>/dev/null || print_warning "File share may already exist"

    print_status "File share ready"
}

# Function to build and push backend image
build_push_backend() {
    print_header "Building and Pushing Backend Image"

    if [ ! -d "backend" ]; then
        print_error "Backend directory not found. Please run this script from the project root."
        sleep 60
        exit 1
    fi

    print_status "Building backend image..."
    docker build -t $BACKEND_IMAGE ./backend

    print_status "Logging into container registry..."
    echo $REGISTRY_PASSWORD | docker login objectmatchingregistry.azurecr.io --username $REGISTRY_USERNAME --password-stdin

    print_status "Pushing backend image..."
    docker push $BACKEND_IMAGE

    print_status "Backend image pushed successfully"
}

# Function to build and push frontend image
build_push_frontend() {
    print_header "Building and Pushing Frontend Image"

    if [ ! -d "frontend" ]; then
        print_error "Frontend directory not found. Please run this script from the project root."
        sleep 60
        exit 1
    fi

    print_status "Building frontend image..."
    docker build -t $FRONTEND_IMAGE ./frontend

    print_status "Pushing frontend image..."
    docker push $FRONTEND_IMAGE

    print_status "Frontend image pushed successfully"
}

# Function to deploy backend container
deploy_backend() {
    print_header "Deploying Backend Container"

    print_status "Creating backend container instance..."
    az container create \
        --resource-group $RESOURCE_GROUP \
        --name $BACKEND_CONTAINER \
        --image $BACKEND_IMAGE \
        --cpu 2 \
        --memory 4 \
        --registry-login-server objectmatchingregistry.azurecr.io \
        --registry-username $REGISTRY_USERNAME \
        --registry-password $REGISTRY_PASSWORD \
        --dns-name-label $BACKEND_CONTAINER \
        --ports 8000 \
        --environment-variables PYTHONPATH=/app UVICORN_HOST=0.0.0.0 UVICORN_PORT=8000 \
        --azure-file-volume-account-name $STORAGE_ACCOUNT \
        --azure-file-volume-account-key $STORAGE_KEY \
        --azure-file-volume-share-name $STORAGE_SHARE \
        --azure-file-volume-mount-path /app/data \
        --restart-policy Always

    # Get backend FQDN
    BACKEND_FQDN=$(az container show --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --query ipAddress.fqdn -o tsv)

    print_status "Backend container deployed successfully"
    print_status "Backend URL: http://$BACKEND_FQDN:8000"
}

# Function to deploy frontend container
deploy_frontend() {
    print_header "Deploying Frontend Container"

    print_status "Creating frontend container instance..."
    az container create \
        --resource-group $RESOURCE_GROUP \
        --name $FRONTEND_CONTAINER \
        --image $FRONTEND_IMAGE \
        --cpu 1 \
        --memory 2 \
        --registry-login-server objectmatchingregistry.azurecr.io \
        --registry-username $REGISTRY_USERNAME \
        --registry-password $REGISTRY_PASSWORD \
        --dns-name-label $FRONTEND_CONTAINER \
        --ports 3000 \
        --environment-variables REACT_APP_API_URL=http://$BACKEND_FQDN:8000 \
        --restart-policy Always

    # Get frontend FQDN
    FRONTEND_FQDN=$(az container show --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER --query ipAddress.fqdn -o tsv)

    print_status "Frontend container deployed successfully"
    print_status "Frontend URL: http://$FRONTEND_FQDN:3000"
}

# Function to show deployment status
show_deployment_info() {
    print_header "Deployment Information"

    echo "Resource Group: $RESOURCE_GROUP"
    echo "Location: $LOCATION"
    echo "Container Registry: objectmatchingregistry.azurecr.io"
    echo "Registry Resource Group: $REGISTRY_RESOURCE_GROUP"
    echo "Storage Account: $STORAGE_ACCOUNT"
    echo ""
    echo "Backend Container: $BACKEND_CONTAINER"
    echo "Backend URL: http://$BACKEND_FQDN:8000"
    echo "Backend API Docs: http://$BACKEND_FQDN:8000/docs"
    echo ""
    echo "Frontend Container: $FRONTEND_CONTAINER"
    echo "Frontend URL: http://$FRONTEND_FQDN:3000"
    echo ""
    echo "Storage File Share: $STORAGE_SHARE"
    echo ""
    print_status "Deployment completed successfully!"
}

# Function to clean up resources
cleanup() {
    print_header "Cleaning Up Resources"

    read -p "Are you sure you want to delete the resource group $RESOURCE_GROUP and all its resources? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_status "Deleting resource group: $RESOURCE_GROUP"
        az group delete --name $RESOURCE_GROUP --yes --no-wait
        print_status "Resource group deletion initiated"

        # Ask about registry cleanup if it's in a different resource group
        if [ "$REGISTRY_RESOURCE_GROUP" != "$RESOURCE_GROUP" ]; then
            read -p "Do you also want to delete the container registry in $REGISTRY_RESOURCE_GROUP? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                print_status "Deleting container registry: $CONTAINER_REGISTRY"
                az acr delete --name $CONTAINER_REGISTRY --resource-group $REGISTRY_RESOURCE_GROUP --yes
                print_status "Container registry deleted"
            fi
        fi
    else
        print_status "Cleanup cancelled"
    fi
}

# Function to show logs
show_logs() {
    print_header "Container Logs"

    echo "1. Backend logs"
    echo "2. Frontend logs"
    echo "3. Both"
    read -p "Select option (1-3): " -n 1 -r
    echo

    case $REPLY in
        1)
            print_status "Showing backend logs..."
            az container logs --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER --follow
            ;;
        2)
            print_status "Showing frontend logs..."
            az container logs --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER --follow
            ;;
        3)
            print_status "Showing both logs..."
            az container logs --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER &
            az container logs --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER &
            wait
            ;;
        *)
            print_error "Invalid option"
            sleep 60
            ;;
    esac
}

# Function to restart containers
restart_containers() {
    print_header "Restarting Containers"

    print_status "Restarting backend container..."
    az container restart --resource-group $RESOURCE_GROUP --name $BACKEND_CONTAINER

    print_status "Restarting frontend container..."
    az container restart --resource-group $RESOURCE_GROUP --name $FRONTEND_CONTAINER

    print_status "Containers restarted successfully"
}

# Function to force cleanup of orphaned resources
force_cleanup() {
    print_header "Force Cleanup of Orphaned Resources"

    print_warning "This will attempt to find and delete orphaned resources"
    read -p "Are you sure you want to proceed? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Find and delete orphaned container registry
        print_status "Searching for orphaned container registry..."
        ORPHANED_REGISTRY=$(az acr list --query "[?name=='$CONTAINER_REGISTRY'].{name:name,resourceGroup:resourceGroup}" -o tsv)

        if [ ! -z "$ORPHANED_REGISTRY" ]; then
            print_status "Found orphaned registry: $ORPHANED_REGISTRY"
            az acr delete --name $CONTAINER_REGISTRY --resource-group $(echo $ORPHANED_REGISTRY | cut -f2) --yes
            print_status "Orphaned registry deleted"
        else
            print_status "No orphaned registry found"
        fi

        # Ensure resource group is completely clean
        if az group show --name $RESOURCE_GROUP &> /dev/null; then
            print_status "Deleting resource group: $RESOURCE_GROUP"
            az group delete --name $RESOURCE_GROUP --yes --no-wait
        fi
    fi
}

# Main execution
main() {
    print_header "Object Matching Application Deployment"

    case "${1:-deploy}" in
        "deploy")
            check_azure_cli
            check_azure_login
            create_resource_group
            check_existing_registry
            create_container_registry
            create_storage
            build_push_backend
            build_push_frontend
            deploy_backend
            deploy_frontend
            show_deployment_info
            ;;
        "cleanup")
            cleanup
            ;;
        "force-cleanup")
            force_cleanup
            ;;
        "logs")
            show_logs
            ;;
        "restart")
            restart_containers
            ;;
        "status")
            show_deployment_info
            ;;
        *)
            echo "Usage: $0 {deploy|cleanup|force-cleanup|logs|restart|status}"
            echo ""
            echo "Commands:"
            echo "  deploy       - Deploy the application (default)"
            echo "  cleanup      - Delete all resources"
            echo "  force-cleanup - Force cleanup of orphaned resources"
            echo "  logs         - Show container logs"
            echo "  restart      - Restart containers"
            echo "  status       - Show deployment status"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"