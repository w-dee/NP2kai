# SPDX-License-Identifier: MIT
ROOT := $(abspath ../../..)
OUT := $(ROOT)/.local/n2-fixture/n2.hdm
.PHONY: image verify test qualify
image:
	python3 $(ROOT)/tools/guest/build_i286_time_n2.py --output $(OUT) --check-reference
verify: image
	python3 $(ROOT)/tools/guest/verify_i286_time_n2.py --kind image $(OUT)
test:
	cd $(ROOT) && python3 -m unittest tools/guest/test_i286_time_n2.py
qualify:
	python3 $(ROOT)/tools/guest/run_i286_time_n2.py
