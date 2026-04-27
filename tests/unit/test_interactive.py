# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

from gateway.core.interactive import (
    FallbackTextRenderer,
    SlackBlockKitRenderer,
    get_interactive_renderer,
)
from gateway.core.interactive_callbacks import (
    InteractionCallback,
    InteractionRouter,
)
from gateway.core.types import (
    Button,
    Card,
    OutboundMessage,
    Select,
    SelectOption,
)


class TestInteractiveTypes:
    def test_button_defaults(self):
        btn = Button(label="Click", action_id="btn_1")
        assert btn.label == "Click"
        assert btn.value == ""
        assert btn.style == "default"

    def test_select_with_options(self):
        sel = Select(
            action_id="sel_1",
            placeholder="Pick one",
            options=[
                SelectOption(label="A", value="a"),
                SelectOption(label="B", value="b"),
            ],
        )
        assert len(sel.options) == 2

    def test_card_with_buttons(self):
        card = Card(
            title="Test Card",
            subtitle="Sub",
            buttons=[Button(label="OK", action_id="ok")],
        )
        assert card.title == "Test Card"
        assert len(card.buttons) == 1

    def test_outbound_message_interactive_default_empty(self):
        msg = OutboundMessage(channel="test", recipient_id="u1", text="hi")
        assert msg.interactive == []

    def test_outbound_message_with_interactive(self):
        btn = Button(label="Go", action_id="go_1")
        msg = OutboundMessage(
            channel="test",
            recipient_id="u1",
            text="Choose:",
            interactive=[btn],
        )
        assert len(msg.interactive) == 1


class TestSlackBlockKitRenderer:
    def test_render_button(self):
        renderer = SlackBlockKitRenderer()
        result = renderer.render([Button(label="Click", action_id="btn_1", value="v1")])
        blocks = result["blocks"]
        assert len(blocks) == 1
        assert blocks[0]["type"] == "actions"
        el = blocks[0]["elements"][0]
        assert el["type"] == "button"
        assert el["text"]["text"] == "Click"
        assert el["action_id"] == "btn_1"

    def test_render_select(self):
        renderer = SlackBlockKitRenderer()
        result = renderer.render(
            [
                Select(
                    action_id="sel_1",
                    placeholder="Pick",
                    options=[
                        SelectOption(label="A", value="a"),
                        SelectOption(label="B", value="b"),
                    ],
                )
            ]
        )
        blocks = result["blocks"]
        assert len(blocks) == 1
        el = blocks[0]["elements"][0]
        assert el["type"] == "static_select"
        assert len(el["options"]) == 2

    def test_render_card(self):
        renderer = SlackBlockKitRenderer()
        result = renderer.render(
            [
                Card(
                    title="My Card",
                    subtitle="Details here",
                    buttons=[
                        Button(label="OK", action_id="ok"),
                    ],
                )
            ]
        )
        blocks = result["blocks"]
        assert blocks[0]["type"] == "header"
        assert blocks[0]["text"]["text"] == "My Card"
        assert blocks[1]["type"] == "section"
        assert blocks[2]["type"] == "actions"

    def test_render_card_with_image(self):
        renderer = SlackBlockKitRenderer()
        result = renderer.render(
            [
                Card(
                    title="Photo",
                    image_url="https://example.com/img.png",
                )
            ]
        )
        blocks = result["blocks"]
        image_blocks = [b for b in blocks if b["type"] == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0]["image_url"] == "https://example.com/img.png"


class TestFallbackRenderer:
    def test_render_button_as_text(self):
        renderer = FallbackTextRenderer()
        result = renderer.render([Button(label="Click Me", action_id="btn_1")])
        assert "[Click Me]" in result["text"]

    def test_render_select_as_text(self):
        renderer = FallbackTextRenderer()
        result = renderer.render(
            [
                Select(
                    action_id="sel_1",
                    placeholder="Pick",
                    options=[
                        SelectOption(label="A", value="a"),
                        SelectOption(label="B", value="b"),
                    ],
                )
            ]
        )
        assert "Pick" in result["text"]
        assert "A" in result["text"]

    def test_render_card_as_text(self):
        renderer = FallbackTextRenderer()
        result = renderer.render(
            [
                Card(
                    title="Title",
                    body="Body text",
                    buttons=[Button(label="Go", action_id="go")],
                )
            ]
        )
        text = result["text"]
        assert "**Title**" in text
        assert "Body text" in text
        assert "[Go]" in text


class TestGetInteractiveRenderer:
    def test_slack_uses_block_kit(self):
        renderer = get_interactive_renderer("slack")
        assert isinstance(renderer, SlackBlockKitRenderer)

    def test_unknown_uses_fallback(self):
        renderer = get_interactive_renderer("unknown_channel")
        assert isinstance(renderer, FallbackTextRenderer)

    def test_whatsapp_uses_fallback(self):
        renderer = get_interactive_renderer("whatsapp")
        assert isinstance(renderer, FallbackTextRenderer)


class TestInteractionCallback:
    def test_callback_fields(self):
        cb = InteractionCallback(
            action_id="btn_1",
            value="clicked",
            user_id="u1",
            channel="slack",
            conversation_id="conv1",
        )
        assert cb.action_id == "btn_1"
        assert cb.value == "clicked"

    async def test_interaction_router_with_handler(self):
        received = []

        async def handler(cb):
            received.append(cb)

        router = InteractionRouter(on_interaction=handler)
        cb = InteractionCallback(
            action_id="btn_1",
            value="v",
            user_id="u1",
            channel="slack",
            conversation_id="c1",
        )
        await router.handle(cb)
        assert len(received) == 1

    async def test_interaction_router_without_handler(self):
        router = InteractionRouter()
        cb = InteractionCallback(
            action_id="btn_1",
            value="v",
            user_id="u1",
            channel="slack",
            conversation_id="c1",
        )
        await router.handle(cb)
