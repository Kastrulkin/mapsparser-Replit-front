import io

from pypdf import PdfWriter

from services.agent_source_ingestion import build_agent_source_from_upload


class UploadedPdf:
    filename = "source.pdf"
    mimetype = "application/pdf"

    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


def _text_pdf(text):
    stream = f"BT /F1 12 Tf 20 20 Td ({text}) Tj ET".encode()
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
        b"5 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = []
    for item in objects:
        offsets.append(len(output))
        output.extend(item)
    xref_offset = len(output)
    output.extend(b"xref\n0 6\n0000000000 65535 f \n")
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets))
    output.extend(f"trailer << /Root 1 0 R /Size 6 >>\nstartxref\n{xref_offset}\n%%EOF\n".encode())
    return bytes(output)


def test_pdf_source_accepts_normal_pdf_and_rejects_encrypted_or_tiny_malformed_input():
    normal_source, normal_error = build_agent_source_from_upload(UploadedPdf(_text_pdf("normal input")))

    encrypted_writer = PdfWriter()
    encrypted_writer.add_blank_page(width=72, height=72)
    encrypted_writer.encrypt("test-password")
    encrypted = io.BytesIO()
    encrypted_writer.write(encrypted)
    encrypted_source, encrypted_error = build_agent_source_from_upload(UploadedPdf(encrypted.getvalue()))
    malformed_source, malformed_error = build_agent_source_from_upload(UploadedPdf(b"%PDF-1.4\n%%EOF\n"))

    assert normal_error == {}
    assert normal_source["extraction_method"] == "pypdf"
    assert "normal input" in normal_source["content_text"]
    assert encrypted_source == {}
    assert encrypted_error["code"] == "EXTRACTION_FAILED"
    assert malformed_source == {}
    assert malformed_error["code"] == "EXTRACTION_FAILED"
