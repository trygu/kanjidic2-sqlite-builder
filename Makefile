.PHONY: venv install build test

venv:
	python -m venv .venv && . .venv/bin/activate && pip install -e .

install:
	pip install -e .

build:
	k2sqlite build --input data/kanjidic2.xml --db out/kanjidic2.sqlite

test:
	pytest
