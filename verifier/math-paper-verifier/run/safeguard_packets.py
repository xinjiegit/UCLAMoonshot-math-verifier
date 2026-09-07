"""Bounded, lossless partitioning of an already captured advisory packet."""
from __future__ import annotations

import hashlib
import json


def encoded(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def partition(packet: dict, max_chars: int, max_parts: int = 8) -> list[dict]:
    if max_chars <= 0 or max_parts <= 0:
        raise ValueError("Review packet limits must be positive")
    full = encoded(packet)
    if len(full) <= max_chars:
        return [packet]
    fingerprint = hashlib.sha256(full.encode()).hexdigest()
    base = {"run": packet["run"], "documents": {}, "activity": [],
            "integrity_gate": {k: v for k, v in packet["integrity_gate"].items()
                               if k != "diagnostics"},
            "limitations": packet["limitations"] + [
                "This is one part of a larger review. Other parts are reviewed separately; "
                "cross-part relationships may not be visible. Do not infer missing activity "
                "or inconsistencies merely from this partition."],
            "partition": {"input_sha256": fingerprint, "index": max_parts,
                          "total": max_parts}}
    items = list(packet["activity"])
    # Repeat compact source context; otherwise retain documents as labeled records.
    with_docs = dict(base, documents=packet["documents"])
    if len(encoded(with_docs)) <= max_chars // 2:
        base = with_docs
    else:
        items = [{"artifact": name, "location": "complete document",
                  "record": value} for name, value in packet["documents"].items()] + items
    if "diagnostics" in packet["integrity_gate"]:
        items.append({"artifact": "integrity_gate", "location": "diagnostics",
                      "record": packet["integrity_gate"]["diagnostics"]})
    if len(encoded(base)) + 512 >= max_chars:
        raise ValueError("Review metadata cannot fit --max-input-chars; no evidence was dropped")

    def fits(records: list[dict]) -> bool:
        return len(encoded(dict(base, activity=records))) <= max_chars

    chunks: list[list[dict]] = [[]]

    def append(record: dict) -> None:
        if not fits(chunks[-1] + [record]):
            chunks.append([])
        if len(chunks) > max_parts:
            raise ValueError(f"Review needs more than --max-review-parts={max_parts}; "
                             "no reviewers were dispatched and no evidence was dropped")
        chunks[-1].append(record)

    for number, item in enumerate(items):
        if fits([item]):
            append(item)
            continue
        # An individual native export/tool input can exceed one context. Preserve
        # every character, its offset and hash rather than silently clipping it.
        raw = encoded(item)
        offset = 0
        while offset < len(raw):
            def fragment(end: int) -> dict:
                return {"artifact": item["artifact"], "location": item["location"],
                        "record": {"fragment_of_record": number,
                                   "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                                   "start": offset, "end": end, "total_chars": len(raw),
                                   "serialized_fragment": raw[offset:end]}}
            low, high = offset, len(raw)
            while low < high:
                mid = (low + high + 1) // 2
                if fits([fragment(mid)]):
                    low = mid
                else:
                    high = mid - 1
            if low == offset:
                raise ValueError("A review fragment cannot fit --max-input-chars")
            append(fragment(low))
            offset = low
    result = []
    for index, records in enumerate(chunks, 1):
        part = dict(base, activity=records, partition={"input_sha256": fingerprint,
                                                     "index": index, "total": len(chunks)})
        if len(encoded(part)) > max_chars:
            raise ValueError("Partition exceeds its input budget")
        result.append(part)
    return result
