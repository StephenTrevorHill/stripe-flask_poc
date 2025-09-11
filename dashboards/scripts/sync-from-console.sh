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

# Get script directory and related paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARDS_DIR="$(dirname "$SCRIPT_DIR")"
CONFIGS_DIR="$DASHBOARDS_DIR/configs"

# Dashboard mappings as "consoleName|configFile" pairs (avoid associative arrays)
CONSOLE_DASHBOARDS=(
    "SQS-Queue-Monitoring|sqs-queue-monitoring.json"
)

echo -e "${YELLOW}Syncing dashboards from console${NC}"
echo -e "Environment: ${GREEN}$ENVIRONMENT${NC}"
echo -e "Region: ${GREEN}$REGION${NC}"
echo ""

# Create configs directory if it doesn't exist
mkdir -p "$CONFIGS_DIR"

# Track sync results
success_count=0
failed_count=0
total_count=${#CONSOLE_DASHBOARDS[@]}

for entry in "${CONSOLE_DASHBOARDS[@]}"; do
    IFS='|' read -r console_name config_file <<< "$entry"
    output_path="$CONFIGS_DIR/$config_file"
    backup_path="$CONFIGS_DIR/${config_file}.backup"
    # Append environment suffix to the console dashboard name
    console_name="${console_name}-${ENVIRONMENT}"
    echo -e "Syncing: ${YELLOW}$console_name${NC} -> $config_file"
    echo -e "output path: $output_path"
    echo -e "backup path: $backup_path"
    
    # Backup existing config if it exists
    if [[ -f "$output_path" ]]; then
        echo "copying $output_path to $backup_path"
        cp "$output_path" "$backup_path"
        echo -e "  ${YELLOW}Backed up existing config to: ${config_file}.backup${NC}"
    fi
    
    # Try to export the dashboard
    if aws cloudwatch get-dashboard \
        --dashboard-name "$console_name" \
        --region "$REGION" \
        --query 'DashboardBody' \
        --output text 2>/dev/null | jq . > "$output_path"; then
        
        echo -e "${GREEN}✓ Synced: $config_file${NC}"
        
        # Show diff if backup exists
        if [[ -f "$backup_path" ]]; then
            if ! diff -q "$backup_path" "$output_path" >/dev/null 2>&1; then
                echo -e "  ${YELLOW}Changes detected in $config_file${NC}"
            else
                echo -e "  ${GREEN}No changes in $config_file${NC}"
                rm "$backup_path"  # Remove backup if no changes
            fi
        fi
        
        ((success_count++))
    else
        echo -e "${RED}⚠ Dashboard not found in console: $console_name${NC}"
        echo -e "  ${YELLOW}This might be normal if the dashboard hasn't been deployed yet.${NC}"
        
        # Restore backup if sync failed and backup exists
        if [[ -f "$backup_path" ]]; then
            mv "$backup_path" "$output_path"
            echo -e "  ${GREEN}Restored from backup${NC}"
        fi
        
        ((failed_count++))
    fi
    
    echo ""
done

# Summary
echo -e "${GREEN}Sync Summary:${NC}"
echo -e "  Synced: ${GREEN}$success_count${NC}"
echo -e "  Not found: ${YELLOW}$failed_count${NC}"
echo -e "  Total: $total_count"
echo ""

if [[ $success_count -gt 0 ]]; then
    echo -e "${GREEN}Sync complete!${NC}"
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "  1. Review changes: ${GREEN}git diff${NC}"
    echo -e "  2. Test locally: ${GREEN}make dashboard-build${NC}"
    echo -e "  3. Commit changes: ${GREEN}git add . && git commit -m 'Update dashboard configs'${NC}"
else
    echo -e "${YELLOW}No dashboards were synced. Make sure they exist in the console.${NC}"
fi
