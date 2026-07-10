"""Importers that bring EXTERNAL labeled cases onto the bench as second-class rows.

A bench-native case is admissible only with a by-construction ``injection_recipe`` (the
recipe IS the label justification — see ``packager.package_case`` + CLAUDE.md invariant
#2). Imported cases carry no such recipe: they are pre-labeled scenarios authored
elsewhere. They are therefore SECOND-CLASS — graded against their provided ``expected_*``
labels, never held to the strict by-construction lint, and kept in a SEPARATE
``examples/imported_demo_*.jsonl`` corpus marked ``ground_truth_basis="imported_demo"``.

Taxonomy discipline still holds: every flag is linted against the frozen snapshot.
"""
