.PHONY: install run test format

install:
	npm install

# Needs the server (apps/server, `make run`) on port 8000; /orders and /health are proxied to it.
run:
	npm run dev

# Type-check and lint first; make stops on the first failure, so the tests only run if they pass.
test:
	npm run typecheck
	npm run lint
	npm test

format:
	npx oxlint --fix
