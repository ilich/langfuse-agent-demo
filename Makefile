# Monorepo entry point: each target runs in every app under apps/.
APPS := server client

.PHONY: install test format server client

install test format:
	@for app in $(APPS); do $(MAKE) -C apps/$$app $@ || exit 1; done

# Start the API server (http://localhost:8000).
server:
	$(MAKE) -C apps/server run

# Start the chat UI (http://localhost:5173); run it next to `make server`.
client:
	$(MAKE) -C apps/client run
