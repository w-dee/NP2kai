# SPDX-License-Identifier: MIT
ROOT := $(abspath ../../..)
OUT := $(ROOT)/.local/artic-fixture/artic.hdm
.PHONY: image test
image:
	python3 $(ROOT)/tools/guest/build_i286_time_artic.py --output $(OUT)
test:
	cd $(ROOT) && python3 -m unittest tools/guest/test_i286_time_artic.py
