"""
app.py

Gradio interface for FitFindr.

Run with:
    python app.py

Then open the localhost URL shown in your terminal (usually http://localhost:7860).
"""

import gradio as gr

from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def _format_listing(item: dict) -> str:
    """Format a listing dict into readable text for the UI."""
    brand = item.get("brand") or "Unknown brand"
    colors = ", ".join(item.get("colors", []))
    tags = ", ".join(item.get("style_tags", []))
    return (
        f"{item['title']}\n"
        f"${item['price']:.2f} on {item['platform']}\n"
        f"Size: {item['size']} | Condition: {item['condition']}\n"
        f"Brand: {brand}\n"
        f"Colors: {colors}\n"
        f"Style: {tags}\n\n"
        f"{item['description']}"
    )


def _wardrobe_label(wardrobe_choice: str, wardrobe: dict) -> str:
    """Describe which wardrobe mode is active for the outfit step."""
    if wardrobe_choice == "Example wardrobe":
        count = len(wardrobe.get("items", []))
        return f"Example wardrobe ({count} items) — outfit uses your saved pieces"
    return "Empty wardrobe — outfit uses general styling advice only"


def handle_query(user_query: str, wardrobe_choice: str) -> tuple[str, str, str, str]:
    """
    Called by Gradio when the user submits a query.

    Returns:
        (status_message, listing_text, outfit_suggestion, fit_card)
    """
    if not user_query or not user_query.strip():
        return (
            "Please enter a search query.",
            "",
            "",
            "",
        )

    wardrobe = (
        get_example_wardrobe()
        if wardrobe_choice == "Example wardrobe"
        else get_empty_wardrobe()
    )

    try:
        session = run_agent(user_query.strip(), wardrobe)
    except Exception:
        return (
            "Something went wrong while running the agent. "
            "Check your GROQ_API_KEY in .env and try again.",
            "",
            "",
            "",
        )

    if session["error"]:
        return (
            session["error"],
            "",
            "",
            "",
        )

    listing_text = _format_listing(session["selected_item"])
    wardrobe_note = _wardrobe_label(wardrobe_choice, wardrobe)
    return (
        f"Found a match. {wardrobe_note}.",
        listing_text,
        session["outfit_suggestion"] or "",
        session["fit_card"] or "",
    )



DARK_GREEN = "#1a3c34"
DARK_GREEN_LIGHT = "#244a40"
LIGHT_PINK = "#f4c2c2"
LIGHT_PINK_SOFT = "#f8d4d4"

CUSTOM_CSS = f"""
.gradio-container {{
    background-color: {DARK_GREEN} !important;
    color: {LIGHT_PINK} !important;
}}
#fitfindr-header {{
    text-align: center;
    margin-bottom: 0.5rem;
    color: {LIGHT_PINK} !important;
}}
#fitfindr-header h1 {{
    color: {LIGHT_PINK_SOFT} !important;
}}
#status-box textarea {{
    font-weight: 500;
    border-radius: 8px;
    background-color: {DARK_GREEN_LIGHT} !important;
    color: {LIGHT_PINK} !important;
    border: 1px solid {LIGHT_PINK} !important;
}}
.output-panel textarea {{
    font-size: 0.95rem;
    line-height: 1.5;
    background-color: {DARK_GREEN_LIGHT} !important;
    color: {LIGHT_PINK} !important;
    border: 1px solid {LIGHT_PINK} !important;
}}
footer {{
    display: none !important;
}}
.block, .form, .panel {{
    background-color: {DARK_GREEN} !important;
    border-color: {LIGHT_PINK} !important;
}}
label, .label-wrap, span {{
    color: {LIGHT_PINK_SOFT} !important;
}}
textarea, input {{
    background-color: {DARK_GREEN_LIGHT} !important;
    color: {LIGHT_PINK} !important;
    border-color: {LIGHT_PINK} !important;
}}
.primary {{
    background: {LIGHT_PINK} !important;
    color: {DARK_GREEN} !important;
    border: none !important;
}}
.primary:hover {{
    background: {LIGHT_PINK_SOFT} !important;
}}
.secondary {{
    background: transparent !important;
    color: {LIGHT_PINK} !important;
    border: 1px solid {LIGHT_PINK} !important;
}}
.secondary:hover {{
    background: {DARK_GREEN_LIGHT} !important;
}}
"""


def build_interface():
    theme = (
        gr.themes.Base()
        .set(
            body_background_fill=DARK_GREEN,
            body_background_fill_dark=DARK_GREEN,
            background_fill_primary=DARK_GREEN_LIGHT,
            background_fill_secondary=DARK_GREEN,
            border_color_primary=LIGHT_PINK,
            color_accent=LIGHT_PINK,
            button_primary_background_fill=LIGHT_PINK,
            button_primary_text_color=DARK_GREEN,
            button_secondary_background_fill="transparent",
            button_secondary_text_color=LIGHT_PINK,
            block_background_fill=DARK_GREEN_LIGHT,
            block_label_text_color=LIGHT_PINK_SOFT,
            body_text_color=LIGHT_PINK,
            input_background_fill=DARK_GREEN_LIGHT,
        )
    )

    with gr.Blocks(title="FitFindr", theme=theme, css=CUSTOM_CSS) as demo:
        gr.Markdown(
            """
# FitFindr
The place to create and maintain your dream wardrobe.
Search secondhand finds, build outfits from what you already own, and save looks you love.
            """,
            elem_id="fitfindr-header",
        )

        with gr.Row():
            query_input = gr.Textbox(
                label="What are you looking for?",
                placeholder="e.g. vintage graphic tee under $30, size M",
                lines=2,
                scale=3,
            )
            wardrobe_choice = gr.Radio(
                choices=["Example wardrobe", "Empty wardrobe (new user)"],
                value="Example wardrobe",
                label="Wardrobe (affects outfit suggestions only)",
                scale=1,
            )

        with gr.Row():
            submit_btn = gr.Button("Find it", variant="primary", scale=3)
            clear_btn = gr.Button("Clear", scale=1)

        status_output = gr.Textbox(
            label="Status",
            lines=1,
            interactive=False,
            elem_id="status-box",
        )

        with gr.Row():
            with gr.Column():
                listing_output = gr.Textbox(
                    label="Top listing found",
                    lines=10,
                    interactive=False,
                    elem_classes=["output-panel"],
                )
            with gr.Column():
                outfit_output = gr.Textbox(
                    label="Outfit idea",
                    lines=10,
                    interactive=False,
                    elem_classes=["output-panel"],
                )
            with gr.Column():
                fitcard_output = gr.Textbox(
                    label="Your fit card",
                    lines=10,
                    interactive=False,
                    elem_classes=["output-panel"],
                )

        gr.Examples(
            examples=[
                ["vintage graphic tee under $30", "Example wardrobe"],
                ["vintage graphic tee under $30", "Empty wardrobe (new user)"],
                ["90s track jacket in size M", "Example wardrobe"],
                ["flowy midi skirt under $40", "Example wardrobe"],
                ["black combat boots size 8", "Example wardrobe"],
                ["designer ballgown size XXS under $5", "Example wardrobe"],
            ],
            inputs=[query_input, wardrobe_choice],
            label="Try these queries",
        )

        outputs = [status_output, listing_output, outfit_output, fitcard_output]

        submit_btn.click(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
            show_progress=True,
        )
        query_input.submit(
            fn=handle_query,
            inputs=[query_input, wardrobe_choice],
            outputs=outputs,
            show_progress=True,
        )
        clear_btn.click(
            fn=lambda: ("", "", "", "", "", "Example wardrobe"),
            outputs=[
                query_input,
                status_output,
                listing_output,
                outfit_output,
                fitcard_output,
                wardrobe_choice,
            ],
        )

    return demo


if __name__ == "__main__":
    demo = build_interface()
    demo.launch()
