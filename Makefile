PY ?= python3
export PYTHONPATH := src

.PHONY: test avaliar
test:
	$(PY) -m pytest -q

avaliar:
	$(PY) -m vigia avaliar
