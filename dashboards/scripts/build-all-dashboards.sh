#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory and related paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARDS_DIR="$(dirname "$SCRIPT_DIR")"
CONFIGS_DIR="$DASHBOARDS_DIR/configs"
TEMPLATES_DIR="$DASHBOARDS_DIR/templates"

# Dashboard configurations as "key|display name" pairs (avoid associative arrays)
DASHBOARDS=(
    "sqs-queue-monitoring|SQS Queue Monitoring"
)

echo -e "${YELLOW}Building all dashboard templates...${NC}"

# Create templates directory if it doesn't exist
mkdir -p "$TEMPLATES_DIR"

# Track success/failure
success_count=0
total_count=${#DASHBOARDS[@]}

for entry in "${DASHBOARDS[@]}"; do
    IFS='|' read -r dashboard_key dashboard_name <<< "$entry"
    config_file="$CONFIGS_DIR/${dashboard_key}.json"
    template_file="$TEMPLATES_DIR/${dashboard_key}.yaml"
    
    echo -e "Building: ${YELLOW}$dashboard_name${NC}"
    
    if [[ ! -f "$config_file" ]]; then
        echo -e "${RED}⚠ Warning: Config file not found: $config_file${NC}"
        echo -e "   Creating placeholder config..."
        
        # Create placeholder config
        mkdir -p "$CONFIGS_DIR"
        cat > "$config_file" << 'EOF'
{
  "widgets": [
    {
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 24,
      "height": 1,
      "properties": {
        "markdown": "# Placeholder Dashboard\n\nThis dashboard needs to be configured."
      }
    }
  ]
}
EOF
        echo -e "${YELLOW}   Placeholder created. Edit $config_file to customize.${NC}"
    fi
    
    # Validate JSON
    if ! jq empty "$config_file" 2>/dev/null; then
        echo -e "${RED}✗ Error: Invalid JSON in $config_file${NC}"
        continue
    fi
    
    # Read dashboard JSON
    DASHBOARD_JSON=$(cat "$config_file" | jq -c .)
    
    # Create CloudFormation template
    cat > "$template_file" << EOF
AWSTemplateFormatVersion: '2010-09-09'
Description: '$dashboard_name Dashboard'

Parameters:
  Environment:
    Type: String
    Default: staging
    Description: Environment name (dev, staging, production)
    AllowedValues:
      - dev
      - staging
      - production
  
  DashboardName:
    Type: String
    Default: ${dashboard_key}
    Description: Dashboard name prefix

Resources:
  Dashboard:
    Type: AWS::CloudWatch::Dashboard
    Properties:
      DashboardName: !Sub '\${DashboardName}-\${Environment}'
      DashboardBody: |
        ${DASHBOARD_JSON}

Outputs:
  DashboardURL:
    Description: 'CloudWatch Dashboard URL'
    Value: !Sub 'https://\${AWS::Region}.console.aws.amazon.com/cloudwatch/home?region=\${AWS::Region}#dashboards:name=\${Dashboard}'
    Export:
      Name: !Sub '\${AWS::StackName}-DashboardURL'
  
  DashboardName:
    Description: 'Dashboard Name'
    Value: !Ref Dashboard
    Export:
      Name: !Sub '\${AWS::StackName}-DashboardName'
  
  DashboardArn:
    Description: 'Dashboard ARN'
    Value: !Sub 'arn:aws:cloudwatch::\${AWS::AccountId}:dashboard/\${Dashboard}'
    Export:
      Name: !Sub '\${AWS::StackName}-DashboardArn'
EOF

    echo -e "${GREEN}✓ Created: $(basename "$template_file")${NC}"
    ((success_count++))
done

echo ""
echo -e "${GREEN}Dashboard build complete: $success_count/$total_count templates built${NC}"

if [[ $success_count -lt $total_count ]]; then
    echo -e "${YELLOW}Some templates had issues. Check the output above.${NC}"
    exit 1
fi
