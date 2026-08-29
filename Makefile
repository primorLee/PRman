PYTHON ?= python3.11
PYTHONPATH := src
CORE_PATHS := src/prman/__init__.py src/prman/__main__.py src/prman/assessment.py \
	src/prman/cli.py src/prman/decision.py src/prman/models.py src/prman/validation.py \
	src/prman/workflow.py src/prman/scorers tests/core skills/prman/scripts

.PHONY: check test coverage lint format-check type-check compile dist-check demo

check: lint format-check type-check compile coverage

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests/core -v

coverage:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m coverage erase
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m coverage run --branch -m unittest discover -s tests/core
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m coverage report

lint:
	ruff check $(CORE_PATHS)

format-check:
	ruff format --check $(CORE_PATHS)

type-check:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m mypy

compile:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m compileall -q $(CORE_PATHS)

dist-check:
	$(PYTHON) -m build

demo:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) skills/prman/scripts/assess.py \
		--input examples/assessment.json \
		--scorer-config configs/scorer/fixture.example.json \
		--allow-test-scorer
