"""19.0.1.1.0: a buyer's ``psid`` held the id on their comments, not their
Messenger id. It moves to ``commenter_id``; ``psid`` is filled again the
next time they tap a button in Messenger."""


def migrate(cr, version):
    cr.execute("ALTER TABLE andrho_live_buyer ADD COLUMN IF NOT EXISTS commenter_id varchar")
    cr.execute("""
        UPDATE andrho_live_buyer SET commenter_id = psid, psid = NULL
        WHERE commenter_id IS NULL AND psid IS NOT NULL
    """)
