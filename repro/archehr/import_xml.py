"""Strict supplied-answer XML adapter; validate against the authorized release before real use."""

import argparse
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

from .run import SCHEMA, prepare, validate_inputs, write_json


def import_task4_xml(path: Path, *, name: str, split: str, release: str) -> dict:
    raw = path.read_bytes()
    if len(raw) > 20_000_000 or b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("oversized XML or DTD/entity declaration refused")
    root = ET.fromstring(raw)
    forbidden = {"citations", "citation", "relevance", "clinician_answer_sentences"}
    for node in root.iter():
        if node.tag in forbidden or forbidden.intersection(node.attrib):
            raise ValueError("annotated/key XML refused; use gold-free supplied-answer input")

    def text_at(case, tag):
        nodes = case.findall(tag)
        if len(nodes) != 1:
            raise ValueError(f"requires exactly one {tag}; no fallback to a reference key")
        return "".join(nodes[0].itertext()).strip()

    def sentences(case, tag):
        containers = case.findall(tag)
        if len(containers) != 1:
            raise ValueError(f"requires supplied {tag}; never reconstruct from a key")
        rows = []
        for node in containers[0]:
            if node.tag != "sentence" or set(node.attrib) != {"id"} or list(node):
                raise ValueError(
                    f"unsupported {tag} sentence schema; inspect release before adapting"
                )
            rows.append({"id": node.attrib["id"], "text": (node.text or "").strip()})
        return rows

    cases = root.findall("case")
    result = {
        "schema_version": SCHEMA,
        "dataset": {"name": name, "split": split, "release": release},
        "cases": [
            {
                "case_id": case.attrib.get("id"),
                "patient_question": text_at(case, "patient_narrative"),
                "clinician_question": text_at(case, "clinician_question"),
                "note_sentences": sentences(case, "note_excerpt_sentences"),
                "answer_sentences": sentences(case, "answer_sentences"),
            }
            for case in cases
        ],
    }
    validate_inputs(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--split", choices=["smoke", "development", "heldout"], required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        inputs = import_task4_xml(args.xml, name=args.name, split=args.split, release=args.release)
        prepare(inputs, args.out)
        write_json(
            args.out / "import_provenance.json",
            {
                "source_xml_sha256": hashlib.sha256(args.xml.read_bytes()).hexdigest(),
                "format_basis": "2026 participant parser; not verified on restricted organizer release",
                "no_key_read": True,
            },
        )
    except (ValueError, OSError, ET.ParseError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")
    print(f"Prepared {len(inputs['cases'])} cases at {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
