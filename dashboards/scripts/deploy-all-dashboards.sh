#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=${1:-staging}
REGION=${2:-us-east-1}
DRY_RUN=${3:-false}

# Get script directory and related paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARDS_DIR="$(dirname "$SCRIPT_DIR")"
TEMPLATES_DIR="$DASHBOARDS_DIR/templates"

# Dashboard configurations as "key|display name" pairs (must match build script)
DASHBOARDS=(
    "SQS-Queue-Monitoring|SQS Queue Monitoring"
)

# Validate inputs
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|production)$ ]]; then
    echo -e "${RED}Error: Environment must be dev, staging, or production${NC}"
    echo "Usage: $0 <environment> [region] [dry-run]"
    exit 1
fi

echo -e "${YELLOW}Deploying all dashboards${NC}"
echo -e "Environment: ${GREEN}$ENVIRONMENT${NC}"
echo -e "Region: ${GREEN}$REGION${NC}"
echo -e "Dry run: ${GREEN}$DRY_RUN${NC}"
echo ""

# Build all templates first
echo -e "${YELLOW}Building templates first...${NC}"
"$SCRIPT_DIR/build-all-dashboards.sh"
echo ""

# Track deployment results
success_count=0
failed_count=0
skipped_count=0
total_count=${#DASHBOARDS[@]}

# Deploy each dashboard
for entry in "${DASHBOARDS[@]}"; do
    IFS='|' read -r dashboard_key dashboard_name <<< "$entry"
    template_file="$TEMPLATES_DIR/${dashboard_key}.yaml"
    stack_name="${dashboard_key}-${ENVIRONMENT}"
    
    echo -e "Deploying: ${YELLOW}$dashboard_name${NC} (${stack_name})"
    
    if [[ ! -f "$template_file" ]]; then
        echo -e "${RED}✗ Template file not found: $template_file${NC}"
        ((failed_count++))
        continue
    fi
    
    # Dry run mode
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}  [DRY RUN] Would deploy: $stack_name${NC}"
        ((skipped_count++))
        continue
    fi
    
    # Deploy the stack
    if aws cloudformation deploy \
        --template-file "$template_file" \
        --stack-name "$stack_name" \
        --parameter-overrides \
            Environment="$ENVIRONMENT" \
            DashboardName="$dashboard_key" \
        --region "$REGION" \
        --no-fail-on-empty-changeset \
        --capabilities CAPABILITY_IAM 2>/dev/null; then
        
        echo -e "${GREEN}✓ Deployed: $stack_name${NC}"
        
        # Get dashboard URL
        dashboard_url=$(aws cloudformation describe-stacks \
            --stack-name "$stack_name" \
            --region "$REGION" \
            --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
            --output text 2>/dev/null || echo "URL not available")
        
        if [[ "$dashboard_url" != "URL not available" ]]; then
            echo -e "  ${GREEN}Dashboard URL: $dashboard_url${NC}"
        fi
        
        ((success_count++))
    else
        echo -e "${RED}✗ Failed to deploy: $stack_name${NC}"
        ((failed_count++))
    fi
    
    echo ""
done

# Summary
echo -e "${GREEN}Deployment Summary:${NC}"
echo -e "  Successful: ${GREEN}$success_count${NC}"
echo -e "  Failed: ${RED}$failed_count${NC}"
echo -e "  Skipped: ${YELLOW}$skipped_count${NC}"
echo -e "  Total: $total_count"

if [[ $failed_count -gt 0 ]]; then
    echo -e "${RED}Some deployments failed. Check the output above.${NC}"
    exit 1
elif [[ $success_count -gt 0 ]]; then
    echo -e "${GREEN}All dashboards deployed successfully!${NC}"
fi
