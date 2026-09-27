# SPDX-License-Identifier: MIT
ROOT := ../../..
PYTHON ?= python3
OUT ?= $(ROOT)/.local/n4-gdc/build
CLASS ?= 24
MODE ?= 1

.PHONY: all test
all:
	$(PYTHON) $(ROOT)/tools/guest/build_i286_time_gdc.py --scan-class $(CLASS) --mode $(MODE) --output $(OUT)/n4-$(CLASS)-$(MODE).hdm

test:
	$(PYTHON) $(ROOT)/tools/guest/test_gdc_contract.py
	$(PYTHON) -O $(ROOT)/tools/guest/test_gdc_contract.py
