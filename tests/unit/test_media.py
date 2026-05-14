from __future__ import annotations

import base64

from gateway.core.media import extract_file_parts


class TestExtractFileParts:
    def test_file_with_url(self):
        result = {
            "artifacts": [
                {
                    "parts": [
                        {
                            "url": "https://example.com/f.png",
                            "mediaType": "image/png",
                            "filename": "f.png",
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

    def test_file_with_base64_raw(self):
        raw = b"hello binary"
        encoded = base64.b64encode(raw).decode()
        result = {
            "artifacts": [
                {
                    "parts": [
                        {"raw": encoded, "mediaType": "application/pdf"},
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
                            "url": "https://example.com/report.pdf",
                            "mediaType": "application/pdf",
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
                        {"text": "Here is your file"},
                        {
                            "url": "https://example.com/f.png",
                            "mediaType": "image/png",
                        },
                    ]
                }
            ]
        }
        atts = extract_file_parts(result)
        assert len(atts) == 1

    def test_no_file_parts_empty_list(self):
        result = {"artifacts": [{"parts": [{"text": "just text"}]}]}
        assert extract_file_parts(result) == []

    def test_empty_result(self):
        assert extract_file_parts({}) == []

    def test_part_without_url_or_raw_skipped(self):
        result = {"artifacts": [{"parts": [{"mediaType": "image/png"}]}]}
        assert extract_file_parts(result) == []
