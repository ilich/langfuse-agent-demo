# Monorepo entry point: each target runs in every app under apps/.
APPS := server

.PHONY: install run test format

install test format:
	@for app in $(APPS); do $(MAKE) -C apps/$$app $@ || exit 1; done

server:
	$(MAKE) -C apps/server run
