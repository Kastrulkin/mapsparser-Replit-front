import io
import zipfile

from services.agent_source_ingestion import build_agent_source_from_upload


class UploadedDocument:
    filename = "source.docx"
    mimetype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


def test_docx_rejects_excessive_uncompressed_archive_before_extraction():
    document_xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>"
        + ("A" * (12 * 1024 * 1024))
        + "</w:t></w:r></w:p></w:body></w:document>"
    )
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)

    source, error = build_agent_source_from_upload(UploadedDocument(archive_bytes.getvalue()))

    assert source == {}
    assert error["code"] == "ARCHIVE_TOO_LARGE"
