.PHONY: install test smoke api ui e2e report clean stand stand-down stand-test

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

stand:
	./scripts/stand-up.sh

stand-down:
	./scripts/stand-down.sh

stand-test:
	BASE_URL=http://localhost:4200 API_BASE_URL=http://localhost:8091 \
	MOCK_CONTACT_API=false TIMEOUT_MS=10000 pytest -m ""
