# SPDX-License-Identifier: MIT
PYTHON ?= python3
OUTPUT ?= ../../../.local/pit-pic.hdm
MODE ?= 2
PROFILE ?= 1

.PHONY: all
all:
	$(PYTHON) ../../../tools/guest/build_i286_time_pit_pic.py --output $(OUTPUT) --mode $(MODE) --profile $(PROFILE)
