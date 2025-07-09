include ../../common/Makefile

FLAG += -pthread
RUNSUF = | sort

.PHONY: log
log: SHELL := /bin/bash
log: commands.log
	bash -ic 'set -o history && history > commands.log'

commands.log:
	echo 'HISTTIMEFORMAT="%F %T "' >> ~/.bashrc
	@echo "Close and reopen all terminals to apply the changes"
