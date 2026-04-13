PYTHON ?= python3

.PHONY: lint clean baseline qos full-demo

lint:
	$(PYTHON) -m py_compile controller/qos_priority_controller.py
	$(PYTHON) -m py_compile topology/orange_qos_topology.py
	$(PYTHON) -m py_compile scripts/sdn_qos_experiment.py
	$(PYTHON) -m py_compile scripts/compare_latency.py

clean:
	sudo mn -c
	rm -rf artifacts

baseline:
	bash scripts/run_demo.sh baseline

qos:
	bash scripts/run_demo.sh qos

full-demo:
	bash scripts/run_demo.sh all
