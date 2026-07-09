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

.PHONY: develop test
develop: ensure-uv ## Build and install the native extension in editable mode.
	@echo "==> Building native extension"
	$(UV) run maturin develop

test: develop ## Run pytest.
	@echo "==> Running pytest"
	$(PYTEST)

.PHONY: ruff-format ruff-format-check ruff-check lint ty typecheck cargo-fmt cargo-check cargo-clippy check
ruff-format: ensure-uv ## Format Python files with Ruff.
	@echo "==> Formatting Python files with Ruff"
	$(UV) run ruff format python tests examples

ruff-format-check: ensure-uv ## Check Python formatting with Ruff.
	@echo "==> Checking Python formatting with Ruff"
	$(UV) run ruff format --check python tests examples

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
	cargo fmt --all -- --check

cargo-check: ## Check Rust crate.
	@echo "==> Checking Rust crate"
	cargo check

cargo-clippy: ## Run Rust Clippy checks.
	@echo "==> Running Rust Clippy checks"
	cargo clippy --all-targets --all-features -- -D warnings

check: ruff-format-check ruff-check ty test cargo-fmt cargo-clippy ## Run format, lint, type checks, tests, and Rust checks.
