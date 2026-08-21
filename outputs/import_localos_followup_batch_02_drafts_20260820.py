#!/usr/bin/env python3
"""Import batch two as unapproved drafts, with no send-queue records."""

import runpy


module = runpy.run_path("/app/debug_data/import_localos_followup_batch_01_drafts_20260820.py")
module["FINAL_PATH"] = __import__("pathlib").Path("/app/debug_data/localos-followup-batch-02-final-20260820.json")
module["main"].__globals__["FINAL_PATH"] = module["FINAL_PATH"]
module["main"]()
