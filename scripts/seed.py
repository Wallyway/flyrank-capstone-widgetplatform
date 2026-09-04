"""Demo data: two tenants, so tenant isolation is something you can try by hand.

Safe to run twice: tenants and widgets are only created if missing. A new API
key is issued each run and printed once, since only its hash is stored.
"""

from app import config
from app.core.db import build_pool, run_migrations
from app.core.ids import hash_key, new_api_key, new_widget_id
from app.repositories.tenants import TenantsRepository
from app.repositories.widgets import WidgetsRepository

TENANTS = [
    {
        "name": "Acme Analytics",
        "widgets": [
            {
                "id": "wgt_demo_signup",
                "type": "signup_form",
                "title": "Join the Acme beta",
                "description": "Weekly product notes. One click to leave, always.",
                "button_text": "Request access",
                "fields": [
                    {"name": "email", "label": "Email", "type": "email", "required": True},
                    {"name": "name", "label": "Name", "type": "text", "required": False, "max_length": 80},
                    {
                        "name": "role",
                        "label": "What do you do?",
                        "type": "select",
                        "required": False,
                        "options": ["Engineering", "Design", "Product", "Something else"],
                    },
                ],
                "options": {"theme": "auto", "layout": "inline", "success_message": "You're on the list."},
            },
            {
                "id": "wgt_demo_contact",
                "type": "contact_form",
                "title": "Talk to us",
                "description": "We answer every message within one business day.",
                "button_text": "Send message",
                "fields": [
                    {"name": "email", "label": "Email", "type": "email", "required": True},
                    {"name": "message", "label": "Message", "type": "textarea", "required": True, "max_length": 1000},
                ],
                "options": {"theme": "auto", "layout": "popover", "success_message": "Message received."},
            },
        ],
    },
    {
        "name": "Globex Industrial",
        "widgets": [
            {
                "id": "wgt_demo_globex",
                "type": "cta",
                "title": "Book a Globex demo",
                "description": "Thirty minutes, your data, no slides.",
                "button_text": "Book a slot",
                "fields": [
                    {"name": "email", "label": "Work email", "type": "email", "required": True},
                    {"name": "company", "label": "Company", "type": "text", "required": True, "max_length": 120},
                ],
                "options": {"theme": "auto", "layout": "inline", "success_message": "We'll be in touch."},
            }
        ],
    },
]


def seed():
    pool = build_pool(config.DATABASE_URL)
    applied = run_migrations(pool)
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")

    tenants = TenantsRepository(pool)
    widgets = WidgetsRepository(pool)

    print()
    for spec in TENANTS:
        tenant = tenants.find_by_name(spec["name"]) or tenants.create_tenant(spec["name"])

        key = new_api_key()
        tenants.add_api_key(tenant["id"], hash_key(key), label="seed")

        # Demo widgets keep a fixed id so the test page can carry the real embed
        # snippet. Widgets created through the API still get a random one.
        created = []
        for widget_spec in spec["widgets"]:
            widget_id = widget_spec.get("id") or new_widget_id()
            existing = widgets.get_for_tenant(widget_id, tenant["id"])
            created.append(existing or widgets.create(widget_id, tenant["id"], widget_spec))

        print(f"{spec['name']}  (tenant {tenant['id']})")
        print(f"  API key: {key}")
        for widget in created:
            print(f"  {widget['id']:<20} {widget['type']:<13} {widget['title']}")
        print()

    print("Try it:")
    print("  curl -H 'Authorization: Bearer <key above>' http://localhost:8000/api/widgets")
    print("  open http://localhost:5500   (the customer site, on a second origin)")
    print()
    print("The keys above are shown once. Only their sha256 hash is stored.")


if __name__ == "__main__":
    seed()
