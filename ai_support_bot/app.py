import os
from pprint import pformat

import gradio as gr
from dotenv import load_dotenv

from memory_utils import load_memory, save_memory, add_turn_to_memory
from ticket_utils import (
    create_ticket,
    load_tickets,
    save_tickets,
    extract_order_id,
    classify_issue_type,
    extract_ticket_id,
    get_ticket_by_id,
)
from rag_utils import answer_with_rag

load_dotenv()



def fill_refund():
    return "My refund for order 987654 is delayed. Please check."

def fill_cancel():
    return "I want to cancel my order 123456."

def fill_delivery():
    return "The package is marked delivered but I never received it. Order 777777."

def fill_login():
    return "I forgot my password and cannot login."


def handle_customer_message(user_message: str, auto_create_ticket: bool = True):
    """
    - If user mentions a Ticket ID -> lookup in tickets.json
    - Else normal RAG answer + optional ticket creation from order id
    """

    ticket_id = extract_ticket_id(user_message)
    if ticket_id:
        existing = get_ticket_by_id(ticket_id)
        if existing:
            reply = (
                f"Here are the details for your ticket **{ticket_id}**:\n\n"
                f"- **Issue type:** {existing['issue_type']}\n"
                f"- **Order ID:** {existing['order_id']}\n"
                f"- **Status:** {existing['status']}\n"
                f"- **Created at:** {existing['created_at']}\n"
                f"- **Summary:** {existing['summary']}\n\n"
                "If you want, I can help you follow up on this issue or update the status."
            )
            add_turn_to_memory(user_message, reply)
            return {
                "reply": reply,
                "order_id": existing["order_id"],
                "issue_type": existing["issue_type"],
                "ticket": existing,
                "context_used": None,
            }
        else:
            reply = (
                f"I couldn't find any ticket with ID **{ticket_id}** in the system. "
                "Please double-check the ticket ID, or tell me what issue you're facing so I can open a new ticket."
            )
            add_turn_to_memory(user_message, reply)
            return {
                "reply": reply,
                "order_id": None,
                "issue_type": "Ticket Lookup",
                "ticket": None,
                "context_used": None,
            }

    
    rag = answer_with_rag(user_message)
    base_answer = rag["answer"]

    order_id = extract_order_id(user_message)
    issue_type = classify_issue_type(user_message)
    ticket = None
    extra_msg = ""

    if auto_create_ticket and order_id:
        summary = f"{issue_type} - {user_message[:120]}..."
        ticket = create_ticket(order_id, issue_type, user_message, summary)
        extra_msg = (
            f"\n\n✅ I have created a support ticket for you.\n"
            f"Ticket ID: **{ticket['ticket_id']}**\n"
            f"Issue Type: {ticket['issue_type']}\n"
            f"Status: {ticket['status']}"
        )
    elif not order_id:
        extra_msg = (
            "\n\nℹ️ I could not detect an Order ID in your message. "
            "Share your Order ID if you want me to create a ticket."
        )

    final_reply = base_answer + extra_msg
    add_turn_to_memory(user_message, final_reply)

    return {
        "reply": final_reply,
        "order_id": order_id,
        "issue_type": issue_type,
        "ticket": ticket,
        "context_used": rag["context"],
    }


custom_css = """
:root {
    --bg-main: #020617;
    --bg-card: rgba(15, 23, 42, 0.96);
    --bg-card-soft: rgba(17, 24, 39, 0.96);
    --border-soft: rgba(148, 163, 184, 0.45);
    --accent: #38bdf8;
    --accent-soft: rgba(56, 189, 248, 0.12);
    --accent-strong: #0ea5e9;
    --text-main: #e5e7eb;
    --text-subtle: #9ca3af;
}

body {
    background: radial-gradient(circle at top, #020617 0, #020617 45%, #020617 100%);
    color: var(--text-main);
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text",
        "Segoe UI", sans-serif;
}

/* Container */
#support-container {
    max-width: 1120px;
    margin: 12px auto 32px auto;
}

/* Header card */
.header-card {
    background: radial-gradient(circle at top left, #0b1120 0, #020617 55%);
    border-radius: 20px;
    padding: 18px 20px 16px 20px;
    border: 1px solid var(--border-soft);
    box-shadow: 0 22px 45px rgba(15, 23, 42, 0.9);
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.header-title {
    font-size: 1.45rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    display: flex;
    align-items: center;
    gap: 10px;
}

.header-title span.logo {
    width: 32px;
    height: 32px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: radial-gradient(circle at top left, #22c55e, #16a34a, #0f766e);
    box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.6);
    font-size: 1.1rem;
}

.header-subtitle {
    font-size: 0.9rem;
    color: var(--text-subtle);
}

.badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 2px;
}

.badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 0.75rem;
    color: var(--accent-strong);
    background: var(--accent-soft);
    border-radius: 999px;
    padding: 5px 11px;
    border: 1px solid rgba(56, 189, 248, 0.55);
}

.badge span.icon {
    font-size: 0.9rem;
}

/* Chat + side cards */
.chat-card,
.tools-card {
    background: var(--bg-card);
    border-radius: 20px;
    border: 1px solid var(--border-soft);
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.85);
    padding: 12px 14px 14px 14px;
}

/* Chatbot container background */
.gradio-container .chatbot,
.gradio-container .gr-chatbot {
    background: radial-gradient(circle at top left, #020617, #020617 55%, #020617 100%) !important;
    border-radius: 16px !important;
    border: 1px solid rgba(55, 65, 81, 0.85) !important;
}

/* Messages */
.gr-chatbot .message.user,
.gradio-container .message.user {
    background: linear-gradient(135deg, #2563eb, #38bdf8) !important;
    color: #e5e7eb !important;
    border-radius: 16px 16px 4px 16px !important;
    box-shadow: 0 10px 24px rgba(37, 99, 235, 0.55);
}

.gr-chatbot .message.bot,
.gradio-container .message.bot {
    background: linear-gradient(135deg, #020617, #020617) !important;
    border-radius: 16px 16px 16px 4px !important;
    border: 1px solid rgba(55, 65, 81, 0.9);
}

/* Input area */
textarea {
    background: rgba(15, 23, 42, 0.98) !important;
    border-radius: 999px !important;
    border: 1px solid rgba(75, 85, 99, 0.85) !important;
    color: var(--text-main) !important;
    min-height: 44px !important;
}

button {
    border-radius: 999px !important;
    font-weight: 500 !important;
}

/* Primary button */
button.primary,
button[data-testid="button-primary"] {
    background: linear-gradient(135deg, #22c55e, #16a34a) !important;
    border: none !important;
}

button.primary:hover,
button[data-testid="button-primary"]:hover {
    filter: brightness(1.05);
}

/* Tools / side panel */
.tools-card h3,
.tools-card .gr-markdown h3 {
    font-size: 0.95rem;
    font-weight: 600;
    margin-bottom: 4px;
}

.tools-card .gr-markdown {
    font-size: 0.8rem;
}

/* Footer */
.footer-note {
    font-size: 0.75rem;
    color: var(--text-subtle);
    text-align: right;
    margin-top: 10px;
}

/* Quick actions */
.quick-row {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 6px;
}

.quick-chip {
    font-size: 0.75rem;
    border-radius: 999px !important;
    border: 1px solid rgba(148, 163, 184, 0.7) !important;
    background: rgba(15, 23, 42, 0.95) !important;
    padding-inline: 10px !important;
}
.quick-chip:hover {
    border-color: var(--accent-strong) !important;
}
"""


css_html = f"<style>{custom_css}</style>"


def gr_respond(message, history):
    if history is None:
        history = []

    result = handle_customer_message(message)
    reply = result["reply"]

    ticket = result.get("ticket")
    if ticket:
        ticket_preview = (
            f"**Latest Ticket**  \n"
            f"ID: `{ticket['ticket_id']}`  \n"
            f"Order: `{ticket['order_id']}`  \n"
            f"Type: `{ticket['issue_type']}`  \n"
            f"Status: `{ticket['status']}`  \n"
            f"Created: `{ticket['created_at']}`"
        )
    else:
        ticket_preview = "No ticket created for this message."

    tickets = load_tickets()
    tickets_text = f"You currently have **{len(tickets)}** support ticket(s) in the system."

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": reply},
    ]

    return "", history, ticket_preview, tickets_text


def clear_memory_and_chat():
    save_memory([])
    save_tickets([])
    return [], "No tickets yet.", "You currently have **0** support ticket(s) in the system."


with gr.Blocks() as demo:
    gr.HTML(css_html)

    with gr.Column(elem_id="support-container"):
        
        gr.HTML("""
        <div class="header-card">
            <div class="header-title">
                <span class="logo">🛎️</span>
                <span>AI Customer Support Assistant</span>
            </div>
            <div class="header-subtitle">
                Ask about refunds, cancellations, delivery, or login issues.<br>
                Answers are based on internal policies, with automatic support ticket creation using order IDs.
            </div>
            <div class="badge-row">
                <div class="badge"><span class="icon">📚</span>RAG over policies</div>
                <div class="badge"><span class="icon">🎟️</span>Auto support tickets</div>
                <div class="badge"><span class="icon">🧠</span>Conversation memory</div>
            </div>
        </div>
        """)

        with gr.Row():
            
            with gr.Column(scale=3):
                gr.HTML("<div class='chat-card'>")

                chatbot = gr.Chatbot(
                    label="Support Chat",
                    height=420,
                )

                msg = gr.Textbox(
                    placeholder="Type your issue here... (e.g., 'My refund for order 987654 is delayed')",
                    show_label=False,
                )
                send_btn = gr.Button("Send", variant="primary")
                clear_btn = gr.Button("🧹 Clear Chat + Memory", variant="secondary")

                with gr.Row(elem_classes=["quick-row"]):
                    quick_refund = gr.Button("💰 Refund issue", elem_classes=["quick-chip"])
                    quick_cancel = gr.Button("❌ Cancel order", elem_classes=["quick-chip"])
                    quick_delivery = gr.Button("📦 Delivery problem", elem_classes=["quick-chip"])
                    quick_login = gr.Button("🔐 Login / password", elem_classes=["quick-chip"])

                gr.HTML("</div>")

            
            with gr.Column(scale=2):
                gr.HTML("<div class='tools-card'>")

                gr.Markdown("### 🎟️ Ticket Preview")
                ticket_preview_box = gr.Markdown("No tickets yet.")

                gr.Markdown("---")
                gr.Markdown("### 📂 Ticket Status")
                ticket_log_box = gr.Markdown(
                    "You currently have **0** support ticket(s) in the system."
                )

                gr.Markdown("""
                ---
                ### 📝 Tips  
                - Include an **order id** to auto-create a ticket  
                - Try:  
                  - `My refund for order 987654 is delayed.`  
                  - `I want to cancel my order 123456.`  
                  - `Package marked delivered but not received. Order 777777.`  
                """)

                gr.HTML("</div>")

        gr.Markdown(
            "<div class='footer-note'>Built with Groq + RAG + Gradio 6.0.2 • Demo only</div>"
        )

    
    msg.submit(
        gr_respond,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot, ticket_preview_box, ticket_log_box],
    )
    send_btn.click(
        gr_respond,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot, ticket_preview_box, ticket_log_box],
    )
    clear_btn.click(
        clear_memory_and_chat,
        inputs=[],
        outputs=[chatbot, ticket_preview_box, ticket_log_box],
    )

    quick_refund.click(fill_refund, inputs=None, outputs=msg)
    quick_cancel.click(fill_cancel, inputs=None, outputs=msg)
    quick_delivery.click(fill_delivery, inputs=None, outputs=msg)
    quick_login.click(fill_login, inputs=None, outputs=msg)

if __name__ == "__main__":
    demo.launch()
