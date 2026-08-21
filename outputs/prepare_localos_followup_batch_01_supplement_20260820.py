#!/usr/bin/env python3
"""Audit replacement candidates until batch 01 contains 20 safe drafts."""

from pathlib import Path

import prepare_localos_followup_batch_01_20260820


prepare_localos_followup_batch_01_20260820.FIRST_TOUCH_IDS = [
    "eec099a7-1dc8-40c2-a447-ec7c71981471",
    "0de0ab17-fbcc-4e4c-9092-02fdac747b28",
    "b4fd28c5-ed44-4b81-a83b-43ee961e2476",
    "655252e2-7645-49ef-910b-bcb109afd61b",
    "8ed9698b-9fbe-45a9-b08e-e7ef9e4e8c23",
    "ffa3939c-17f9-4dea-b166-a6b3f081eaf6",
    "a4c53e8a-1ace-435e-b78a-05e73f39be61",
    "f106ead4-dbaa-4e28-8029-5a08fedb9a9f",
    "6458edba-5e57-42a2-8e5a-1602b7f1b879",
    "702b914f-1ce4-4fa8-89a5-51498ab27856",
    "bc710318-7fed-4ba4-9c4b-54c005fb3a87",
    "e508043d-db67-49d8-895c-5485c8282d28",
    "1f304a37-6b58-45d8-9a25-0ba7baa0102c",
    "bf88fd9e-1066-4e74-9f53-2b6855c7f13e",
    "74c81164-e73c-41f1-a0b6-fd290856b72e",
    "2588f100-a8bc-4552-9efb-b9c524513140",
    "6d5f7b89-d70a-4a08-a272-e092f06f8a8e",
    "d40dbba7-4623-47a3-b0fb-e6222704bf2d",
    "db240633-d2f4-410c-93a1-8e4206e5742b",
    "a8b9c709-8df7-41a6-b68e-79ba7b90faa9",
    "3ab0a45b-8271-4a22-ae6b-1c0c38319644",
    "e3385891-c79c-48c7-bb2a-75fdff785251",
    "6ff2e1ff-2983-44be-9917-17bf7bd6de91",
    "7745e1f8-b13f-47df-bb76-a5959d6c2881",
    "c40f43d1-f3f7-4be4-83ff-6c4407709db4",
]
prepare_localos_followup_batch_01_20260820.OUTPUT_PATH = Path(
    "/app/debug_data/localos-followup-batch-01-supplement-review-20260820.json"
)


if __name__ == "__main__":
    prepare_localos_followup_batch_01_20260820.main()
