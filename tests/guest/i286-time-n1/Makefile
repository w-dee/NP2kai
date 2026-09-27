# SPDX-License-Identifier: MIT
ROOT := $(abspath ../../..)
OUT := $(ROOT)/.local/n1-fixture/n1.hdm
.PHONY: image verify test qualify
image:
	python3 $(ROOT)/tools/guest/build_i286_time_n1.py --output $(OUT) --check-reference
verify: image
	python3 $(ROOT)/tools/guest/verify_i286_time_n1.py --kind image $(OUT)
test:
	cd $(ROOT) && python3 -m unittest tools/guest/test_i286_time_n1.py
qualify:
	python3 $(ROOT)/tools/guest/run_i286_time_n1.py
