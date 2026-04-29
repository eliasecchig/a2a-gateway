from __future__ import annotations


class TestExtImports:
    def test_simple_channel_importable(self):
        from gateway.ext import SimpleChannel

        assert SimpleChannel is not None

    def test_inbound_message_importable(self):
        from gateway.ext import InboundMessage

        assert InboundMessage is not None

    def test_outbound_message_importable(self):
        from gateway.ext import OutboundMessage

        assert OutboundMessage is not None

    def test_attachment_importable(self):
        from gateway.ext import Attachment

        assert Attachment is not None

    def test_all_exports_listed(self):
        import gateway.ext

        assert set(gateway.ext.__all__) == {
            "SimpleChannel",
            "InboundMessage",
            "OutboundMessage",
            "Attachment",
        }

    def test_simple_channel_is_canonical(self):
        from gateway.core.simple_channel import SimpleChannel as Canonical
        from gateway.ext import SimpleChannel

        assert SimpleChannel is Canonical
