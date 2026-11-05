# Licence-free targets (no VISSIM needed)
.PHONY: test replay figures sumo audit all

test:            ## unit + characterisation tests
	python -m pytest -q

replay:          ## replay the unmodified legacy controller against a fake VISSIM
	python analysis/replay_legacy_controller.py

sumo:            ## build + run the recovered SUMO packages (needs eclipse-sumo)
	python sumo/run_scenarios.py

figures:         ## regenerate figures/ from data/
	python analysis/make_figures.py

audit:           ## needs the PRIVATE raw archives in data/raw/ (see data/raw/README.md)
	python analysis/audit_exports.py --raw data/raw/results
	python analysis/audit_inpx.py --raw results=data/raw/results --raw ug_results=data/raw/ug_results

all: replay figures test
