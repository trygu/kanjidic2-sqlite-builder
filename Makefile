.PHONY: venv install build artifacts test clean

venv:
	python -m venv .venv && . .venv/bin/activate && pip install -e .

install:
	pip install -e .

build:
	k2sqlite build --input data/kanjidic2.xml --db output/kanjidic2.sqlite

artifacts: build
	k2sqlite artifacts --db output/kanjidic2.sqlite --output-dir output

test:
	pytest

clean:
	rm -rf output/*.sqlite output/*.json
