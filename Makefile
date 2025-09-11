.PHONY: help build deploy clean dashboard-build dashboard-deploy sam-build sam-deploy test lint

# Default environment
ENVIRONMENT ?= staging
REGION ?= us-east-1
STACK_NAME ?= webhook-$(ENVIRONMENT)

# Colors for output
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target
help:
	@echo "$(GREEN)Available targets:$(NC)"
	@echo "  $(YELLOW)build$(NC)                 - Build everything (SAM + dashboards)"
	@echo "  $(YELLOW)deploy$(NC)                - Deploy everything"
	@echo "  $(YELLOW)sam-build$(NC)             - Build SAM application only"
	@echo "  $(YELLOW)sam-deploy$(NC)            - Deploy SAM application only"
	@echo "  $(YELLOW)dashboard-build$(NC)       - Build dashboard templates"
	@echo "  $(YELLOW)dashboard-deploy$(NC)      - Deploy all dashboards"
	@echo "  $(YELLOW)deploy-dashboard-<name>$(NC) - Deploy single dashboard"
	@echo "  $(YELLOW)sync-dashboards$(NC)       - Sync dashboards from console"
	@echo "  $(YELLOW)test$(NC)                  - Run tests"
	@echo "  $(YELLOW)clean$(NC)                 - Clean build artifacts"
	@echo ""
	@echo "$(GREEN)Environment variables:$(NC)"
	@echo "  ENVIRONMENT=$(ENVIRONMENT)"
	@echo "  REGION=$(REGION)"
	@echo "  STACK_NAME=$(STACK_NAME)"

# Build everything
build: dashboard-build sam-build
	@echo "$(GREEN)✓ Build complete$(NC)"

# Deploy everything
deploy: build sam-deploy dashboard-deploy
	@echo "$(GREEN)✓ Deployment complete$(NC)"

# SAM targets
sam-build:
	@echo "$(YELLOW)Building SAM application...$(NC)"
	sam build -t infra/template.yaml 

sam-deploy: sam-build
	@echo "$(YELLOW)Deploying SAM application...$(NC)"
	sam deploy \
		--stack-name $(STACK_NAME) \
		--parameter-overrides Stage=$(ENVIRONMENT) \
		--region $(REGION) \
		--no-fail-on-empty-changeset

# Dashboard targets
dashboard-build:
	@echo "$(YELLOW)Building dashboard templates...$(NC)"
	./dashboards/scripts/build-all-dashboards.sh

dashboard-deploy: dashboard-build
	@echo "$(YELLOW)Deploying dashboards...$(NC)"
	./dashboards/scripts/deploy-all-dashboards.sh $(ENVIRONMENT) $(REGION)

# Deploy single dashboard
deploy-dashboard-%:
	@echo "$(YELLOW)Deploying dashboard: $*$(NC)"
	./dashboards/deploy-single-dashboard.sh $* $(ENVIRONMENT) $(REGION)

# Sync dashboards from console
sync-dashboards:
	@echo "$(YELLOW)Syncing dashboards from console...$(NC)"
	./dashboards/scripts/sync-from-console.sh $(ENVIRONMENT) $(REGION)
	@echo "$(GREEN)✓ Dashboards synced. Review changes and commit to git.$(NC)"

# Development targets
test:
	@echo "$(YELLOW)Running tests...$(NC)"
	python -m pytest tests/ -v

lint:
	@echo "$(YELLOW)Running linter...$(NC)"
	flake8 src/ tests/
	cfn-lint template.yaml

# Utility targets
clean:
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	rm -rf .aws-sam/
	rm -f dashboards/templates/*.yaml
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Environment-specific shortcuts
deploy-dev:
	$(MAKE) deploy ENVIRONMENT=dev

deploy-staging:
	$(MAKE) deploy ENVIRONMENT=staging

deploy-prod:
	$(MAKE) deploy ENVIRONMENT=production

# Quick development workflow
dev: clean build test deploy-dev
	@echo "$(GREEN)✓ Development deployment complete$(NC)"

# Show current configuration
config:
	@echo "$(GREEN)Current configuration:$(NC)"
	@echo "  Stage: $(ENVIRONMENT)"
	@echo "  Region: $(REGION)"
	@echo "  Stack Name: $(STACK_NAME)"
	@echo "  AWS Profile: $${AWS_PROFILE:-default}"
