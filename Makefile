SHELL := /bin/bash

# -----------------------------------------------------------------------------
# Usage
#
#   make <target> [args]
#
#   c              Stage all and commit with message "clean up"
#   d              Show unstaged diff
#   f              Stage all and create a fixup commit for HEAD
#   n              Stage all and commit with message "new feature"
#   p [msg]        Stage all, commit (default message: "wip"), and push
#                    e.g.  make p "fix login bug"
#   r              Sync the automated-test scaffold's uv env, then run its test suite
#   s              Show git status
#   squash         Interactive rebase with autosquash against origin/main
#   t              Stage all and commit with message "temporary commit"
#   test           Run the test suite
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Standard commands
# Single-letter targets are intentional — these commands are typed constantly.
# Every keystroke saved compounds. Shift is effort. Brevity is the convention.
# -----------------------------------------------------------------------------

.PHONY: c d f n p s squash t

c:
	git add .
	git commit -am "clean up"

d:
	git diff

f:
	git add .
	git commit --fixup HEAD

n:
	git add .
	git commit -am "new feature"

# Capture extra words after 'p' as the commit message (e.g. make p "my message").
# .DEFAULT absorbs the extra goal at execution time, avoiding eval which parses
# the string as makefile syntax and breaks on words like "include" or "define".
ifeq ($(firstword $(MAKECMDGOALS)),p)
  _P_MSG := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
  ifneq ($(_P_MSG),)
.DEFAULT:
	@:
  endif
endif

p:
	git add .
	git commit -am "$(if $(_P_MSG),$(_P_MSG),wip)"
	git push

s:
	git status

squash:
	git rebase -i --autosquash origin/main

t:
	git add .
	git commit -am "temporary commit"


# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Custom user-defined commands
# Add your own targets below this line.
# -----------------------------------------------------------------------------

.PHONY: r test

# Runs the automated-test scaffold's non-hardware suite (source/tests/automated) -
# validates that pre_test.py's fixture-health checks (importable deps, changelog
# version sync, etc.) and any hardware-independent test stubs pass. Hardware-marked
# tests (test_example_ssh.py and anything real feature tests add) are excluded:
# this repo has no target device attached to run them against.
test:
	@$(MAKE) -C source/tests/automated swtest

# "Re-initialize" here means (re)creating the scaffold's uv-managed venv from
# pyproject.toml/uv.lock - dojo itself has no project name to prompt for, unlike
# a project cloned from this template.
r:
	@$(MAKE) -C source/tests/automated sync
	@$(MAKE) test
