.PHONY: install test smoke api ui e2e report clean stand stand-down stand-test

install:
	pip install -r requirements.txt
	playwright install chromium

test:
	rm -rf allure-results && pytest

smoke:
	rm -rf allure-results && pytest -m smoke

api:
	rm -rf allure-results && pytest -m api

ui:
	rm -rf allure-results && pytest -m ui

e2e:
	rm -rf allure-results && pytest -m e2e

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
	rm -rf allure-results && MOCK_CONTACT_API=false TIMEOUT_MS=10000 pytest -m ""
