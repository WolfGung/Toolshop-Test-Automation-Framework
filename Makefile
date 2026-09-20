.PHONY: install test smoke api ui e2e report clean

install:
	pip install -r requirements.txt
	playwright install chromium

test:
	pytest

smoke:
	pytest -m smoke

api:
	pytest -m api

ui:
	pytest -m ui

e2e:
	pytest -m e2e

report:
	allure serve allure-results

clean:
	rm -rf allure-results allure-report .pytest_cache
