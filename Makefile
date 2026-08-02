UV ?= uv
PYTEST ?= $(UV) run --group test pytest -n auto --dist worksteal
TY ?= $(UV) run --group test ty
STUBTEST ?= $(UV) run python3 -m mypy.stubtest
ZENSICAL ?= $(UV) run --group docs zensical
TWINE ?= $(UV) run --no-project --with twine==6.2.0 twine
VERIFY_DISTRIBUTIONS ?= python3 .github/scripts/verify-distributions.py

DIST_DIR ?= $(CURDIR)/dist
DIST_SMOKE_PYTHON ?= 3.10

.DEFAULT_GOAL := help

##@ General

.PHONY: help
help: ## Show available make targets.
	@echo "Available make targets:"
	@awk 'BEGIN { FS = ":.*## " } \
		/^##@ / { printf "\n%s:\n", substr($$0, 5); next } \
		/^[A-Za-z0-9_.-]+:.*## / { printf "  %-22s %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)

##@ Environment

.PHONY: ensure-uv
ensure-uv: ## Ensure uv is available in PATH.
	@$(UV) --version >/dev/null 2>&1 || { \
		echo "Error: '$(UV)' is not available."; \
		echo "Install uv and ensure it is in PATH, or override UV."; \
		exit 1; \
	}

.PHONY: sync sync-all sync-build
sync: sync-all ## Alias for sync-all.

sync-all: ensure-uv ## Sync all dependency groups and extras.
	@echo "==> Syncing all extras and dependency groups"
	@$(UV) sync --locked --all-extras --all-groups

sync-build: ensure-uv ## Sync dependencies needed to build release artifacts.
	@echo "==> Syncing build dependencies"
	@$(UV) sync --locked --group dev

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

##@ Distribution

.PHONY: clean-dist verify-artifacts build-artifacts
clean-dist: ## Remove local distribution artifacts.
	@echo "==> Removing distribution artifacts from $(DIST_DIR)"
	@dist_dir="$(abspath $(DIST_DIR))"; \
		if [ -z "$$dist_dir" ] || [ "$$dist_dir" = "/" ] || [ "$$dist_dir" = "$(CURDIR)" ]; then \
			echo "Error: refusing to remove unsafe DIST_DIR '$$dist_dir'."; \
			exit 1; \
		fi; \
		rm -rf -- "$$dist_dir"

verify-artifacts: ensure-uv ## Verify archives and isolated wheel/sdist installs.
	@echo "==> Verifying built distributions"
	@$(VERIFY_DISTRIBUTIONS) "$(DIST_DIR)" \
		--expected-version "$$($(UV) version --short)" \
		--python "$(DIST_SMOKE_PYTHON)" \
		--uv "$(UV)"

build-artifacts: sync-build clean-dist ## Build and verify a local wheel and sdist.
	@echo "==> Building wheel and sdist into $(DIST_DIR)"
	@$(UV) run --group dev maturin build --release --locked \
		--out "$(DIST_DIR)" --compatibility pypi
	@$(UV) run --group dev maturin sdist --out "$(DIST_DIR)"
	@$(TWINE) check "$(DIST_DIR)"/*
	@$(MAKE) verify-artifacts DIST_DIR="$(DIST_DIR)"
	@echo "==> Artifact checksums"
	@sh -c 'if command -v sha256sum >/dev/null 2>&1; then sha256sum "$(DIST_DIR)"/*; else shasum -a 256 "$(DIST_DIR)"/*; fi'

##@ Testing

.PHONY: develop test
develop: ensure-uv ## Build and install the native extension in editable mode.
	@echo "==> Building native extension"
	$(UV) run maturin develop

test: develop ## Run pytest.
	@echo "==> Running pytest"
	$(PYTEST)

##@ Documentation

.PHONY: docs docs-serve docs-build docs-deploy docs-list
docs: docs-serve ## Preview the documentation site locally.

docs-serve: ensure-uv ## Preview the documentation site locally.
	@echo "==> Serving documentation"
	$(ZENSICAL) serve

docs-build: ensure-uv ## Build documentation and fail on warnings.
	@echo "==> Building documentation"
	$(ZENSICAL) build --clean --strict

docs-deploy: ensure-uv ## Stage versioned docs locally (for example VERSION=0.3.0).
	@test -n "$(VERSION)" || { echo "Error: VERSION is required."; exit 1; }
	@echo "==> Staging documentation version $(VERSION)"
	$(UV) run --group docs mike deploy --update-aliases "$(VERSION)" latest

docs-list: ensure-uv ## List versioned documentation deployments.
	$(UV) run --group docs mike list

##@ Code quality

.PHONY: ruff-format ruff-format-check ruff-check lint ty stubtest typecheck cargo-fmt cargo-check cargo-clippy check
ruff-format: ensure-uv ## Format Python files with Ruff.
	@echo "==> Formatting Python files with Ruff"
	$(UV) run ruff format python tests examples .github/scripts

ruff-format-check: ensure-uv ## Check Python formatting with Ruff.
	@echo "==> Checking Python formatting with Ruff"
	$(UV) run ruff format --check python tests examples .github/scripts

ruff-check: ensure-uv ## Run Ruff lint checks.
	@echo "==> Running Ruff checks"
	$(UV) run ruff check python tests examples .github/scripts pyproject.toml

lint: ruff-check ## Alias for ruff-check.

ty: ensure-uv ## Run ty type checking.
	@echo "==> Running ty"
	$(TY) check python tests examples .github/scripts

stubtest: develop ## Check native stubs against the extension's runtime API.
	@echo "==> Checking native stub/runtime parity"
	$(STUBTEST) --strict-type-check-only takumi_py._core

typecheck: ty stubtest ## Run static checks and native stub/runtime parity checks.

cargo-fmt: ## Check Rust formatting.
	@echo "==> Checking Rust formatting"
	cargo fmt --all -- --check

cargo-check: ## Check Rust crate.
	@echo "==> Checking Rust crate"
	cargo check

cargo-clippy: ## Run Rust Clippy checks.
	@echo "==> Running Rust Clippy checks"
	cargo clippy --all-targets --all-features -- -D warnings

check: ruff-format-check ruff-check typecheck test cargo-fmt cargo-clippy ## Run format, lint, type checks, tests, and Rust checks.
