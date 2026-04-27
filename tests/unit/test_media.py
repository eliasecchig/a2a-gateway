from __future__ import annotations

import base64

from gateway.core.media import extract_file_parts


class TestExtractFileParts:
    def test_file_with_uri(self):
        result = {
            "artifacts": [
                {
                    "parts": [
                        {
                            "kind": "file",
                            "file": {
                                "uri": "https://example.com/f.png",
                                "mimeType": "image/png",
                                "name": "f.png",
                            },
                        },
                    ]
                }
            ]
        }
        atts = extract_file_parts(result)
        assert len(atts) == 1
        assert atts[0].url == "https://example.com/f.png"
        assert atts[0].mime_type == "image/png"
        assert atts[0].filename == "f.png"

    def test_file_with_base64_bytes(self):
        raw = b"hello binary"
        encoded = base64.b64encode(raw).decode()
        result = {
            "artifacts": [
                {
                    "parts": [
                        {
                            "kind": "file",
                            "file": {"bytes": encoded, "mimeType": "application/pdf"},
                        },
                    ]
                }
            ]
        }
        atts = extract_file_parts(result)
        assert len(atts) == 1
        assert atts[0].data == raw
        assert atts[0].size == len(raw)
        assert atts[0].mime_type == "application/pdf"

    def test_file_from_status_message(self):
        result = {
            "status": {
                "message": {
                    "parts": [
                        {
                            "kind": "file",
                            "file": {
                                "uri": "https://example.com/report.pdf",
                                "mimeType": "application/pdf",
                            },
                        },
                    ]
                }
            }
        }
        atts = extract_file_parts(result)
        assert len(atts) == 1
        assert atts[0].url == "https://example.com/report.pdf"

    def test_mixed_text_and_file_parts(self):
        result = {
            "artifacts": [
                {
                    "parts": [
                        {"kind": "text", "text": "Here is your file"},
                        {
                            "kind": "file",
                            "file": {
                                "uri": "https://example.com/f.png",
                                "mimeType": "image/png",
                            },
                        },
                    ]
                }
            ]
        }
        atts = extract_file_parts(result)
        assert len(atts) == 1

    def test_no_file_parts_empty_list(self):
        result = {"artifacts": [{"parts": [{"kind": "text", "text": "just text"}]}]}
        assert extract_file_parts(result) == []

    def test_empty_result(self):
        assert extract_file_parts({}) == []

    def test_malformed_file_info_still_extracted(self):
        result = {"artifacts": [{"parts": [{"kind": "file", "file": {}}]}]}
        atts = extract_file_parts(result)
        assert len(atts) == 1
        assert atts[0].mime_type == "application/octet-stream"
        assert atts[0].url is None
        assert atts[0].data is None
