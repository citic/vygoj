VENV=.venv
ACT=. $(VENV)/bin/activate
MAIN=src/main.py
DEPS=flask
SHELL:=/bin/bash
HOST=localhost # 0.0.0.0 to allow external connections
PORT=2358

.PHONY: clean install run

default: run

run: export FLASK_APP=$(MAIN)
run: export FLASK_DEBUG=1
run: $(VENV)
	$(ACT) && flask run -h $(HOST) -p $(PORT)

install: $(VENV)

$(VENV):
	python3 -m venv $(VENV)
	$(ACT) && pip install $(DEPS)

clean:
	rm -rf $(VENV)
