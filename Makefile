UV ?= uv
PYTEST ?= $(UV) run pytest
TY ?= $(UV) run ty

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available make targets.
	@echo "Available make targets:"
	@awk 'BEGIN { FS = ":.*## " } /^[A-Za-z0-9_.-]+:.*## / { printf "  %-22s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.PHONY: ensure-uv
ensure-uv: ## Ensure uv is available in PATH.
	@$(UV) --version >/dev/null 2>&1 || { \
		echo "Error: '$(UV)' is not available."; \
		echo "Install uv and ensure it is in PATH, or override UV."; \
		exit 1; \
	}

.PHONY: sync sync-all
sync: sync-all ## Alias for sync-all.

sync-all: ensure-uv ## Sync all dependency groups and extras.
	@echo "==> Syncing all extras and dependency groups"
	@$(UV) sync --locked --all-extras --all-groups

.PHONY: install-prek
install-prek: ensure-uv ## Install prek and git hooks.
	@echo "==> Installing prek"
	@$(UV) tool install prek
	@echo "==> Installing git hooks with prek"
	@$(UV) tool run prek install
	@$(UV) tool run prek install --hook-type commit-msg

.PHONY: prepare
prepare: sync-all install-prek ## Prepare local dev environment.
	@echo "==> Environment prepared"

.PHONY: test
test: ensure-uv ## Run pytest.
	@echo "==> Running pytest"
	$(PYTEST)

.PHONY: ruff-format ruff-check lint ty typecheck cargo-fmt cargo-check check
ruff-format: ensure-uv ## Format Python files with Ruff.
	@echo "==> Formatting Python files with Ruff"
	$(UV) run ruff format python tests examples

ruff-check: ensure-uv ## Run Ruff lint checks.
	@echo "==> Running Ruff checks"
	$(UV) run ruff check python tests examples pyproject.toml

lint: ruff-check ## Alias for ruff-check.

ty: ensure-uv ## Run ty type checking.
	@echo "==> Running ty"
	$(TY) check python tests examples

typecheck: ty ## Alias for ty.

cargo-fmt: ## Check Rust formatting.
	@echo "==> Checking Rust formatting"
	cargo fmt --check

cargo-check: ## Check Rust crate.
	@echo "==> Checking Rust crate"
	cargo check

check: ruff-format ruff-check ty test cargo-fmt cargo-check ## Run format, lint, type checks, tests, and Rust checks.
