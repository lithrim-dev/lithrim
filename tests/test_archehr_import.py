import pytest

from repro.archehr.import_xml import import_task4_xml

XML = b"""<dataset><case id="1">
<patient_narrative>When will it arrive?</patient_narrative>
<clinician_question>What delivery window is stated?</clinician_question>
<note_excerpt_sentences><sentence id="1">Delivery takes 12 days.</sentence></note_excerpt_sentences>
<answer_sentences><sentence id="1">It takes 12 days.</sentence></answer_sentences>
</case></dataset>"""


def test_imports_only_supplied_answer_input(tmp_path):
    path = tmp_path / "input.xml"
    path.write_bytes(XML)
    result = import_task4_xml(path, name="fixture", split="smoke", release="1")
    assert result["cases"][0]["answer_sentences"] == [{"id": "1", "text": "It takes 12 days."}]


@pytest.mark.parametrize(
    "xml",
    [
        XML.replace(b' id="1">It', b' id="1" citations="1">It'),
        XML.replace(b"<answer_sentences>", b"<missing>").replace(
            b"</answer_sentences>", b"</missing>"
        ),
        b'<!DOCTYPE dataset [<!ENTITY value "text">]>' + XML,
    ],
)
def test_annotated_or_unsupplied_answers_refused(tmp_path, xml):
    path = tmp_path / "input.xml"
    path.write_bytes(xml)
    with pytest.raises(ValueError):
        import_task4_xml(path, name="fixture", split="smoke", release="1")
