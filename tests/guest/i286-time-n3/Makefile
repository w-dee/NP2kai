# SPDX-License-Identifier: MIT
ROOT := $(abspath ../../..)
OUT := $(ROOT)/.local/n3-fixture/n3.hdm
.PHONY: image verify test qualify reproducibility-check
image:
	python3 $(ROOT)/tools/guest/build_i286_time_n3.py --output $(OUT) --check-reference
verify: image
	python3 $(ROOT)/tools/guest/verify_i286_time_n3.py --kind image $(OUT)
test:
	python3 $(ROOT)/tools/guest/test_i286_time_n3.py -v
qualify:
	python3 $(ROOT)/tools/guest/run_i286_time_n3.py
reproducibility-check:
	python3 $(ROOT)/tools/guest/check_i286_time_n3_reproducibility.py
