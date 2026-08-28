PYTHON ?= python3.11
PYTHONPATH := src
CORE_PATHS := src/prman/__init__.py src/prman/__main__.py src/prman/assessment.py \
	src/prman/cli.py src/prman/decision.py src/prman/models.py src/prman/validation.py \
	src/prman/scorers tests/core skills/prman/scripts

.PHONY: check test lint format-check compile demo

check: lint format-check compile test

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests/core -v

lint:
	ruff check $(CORE_PATHS)

format-check:
	ruff format --check $(CORE_PATHS)

compile:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m compileall -q $(CORE_PATHS)

demo:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) skills/prman/scripts/assess.py \
		--input examples/assessment.json \
		--scorer-config configs/scorer/fixture.example.json \
		--allow-test-scorer
