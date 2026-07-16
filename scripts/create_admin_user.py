#!/usr/bin/env python3
"""Create or update a superadmin user in PrismRAG PostgreSQL."""
import argparse
import uuid

import bcrypt
import psycopg2

LOCAL_DSN = "postgresql://prismrag:prismrag@localhost:5432/prismrag"

EMAIL     = "insightits.info@gmail.com"
PASSWORD  = "Insight123456"
FULL_NAME = "Amin Parva"
PLAN      = "enterprise"
ROLE      = "superadmin"


def run(dsn: str) -> None:
    pw_hash   = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    user_id   = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())

    conn = psycopg2.connect(dsn)
    cur  = conn.cursor()

    cur.execute("SELECT id FROM prismrag.user_account WHERE email = %s", (EMAIL,))
    existing = cur.fetchone()

    if existing:
        cur.execute(
            "UPDATE prismrag.user_account "
            "SET password_hash=%s, plan=%s, role=%s, is_active=TRUE, updated_at=now() "
            "WHERE email=%s",
            (pw_hash, PLAN, ROLE, EMAIL),
        )
        print(f"[UPDATED] {EMAIL}  role={ROLE}  plan={PLAN}")
    else:
        cur.execute(
            "INSERT INTO prismrag.user_account (id, email, password_hash, full_name, plan, role, is_active) "
            "VALUES (%s,%s,%s,%s,%s,%s,TRUE)",
            (user_id, EMAIL, pw_hash, FULL_NAME, PLAN, ROLE),
        )
        cur.execute(
            "INSERT INTO prismrag.tenant (id, name, owner_email) VALUES (%s,%s,%s)",
            (tenant_id, "Insight IT Solutions", EMAIL),
        )
        cur.execute(
            "INSERT INTO prismrag.tenant_member (tenant_id, user_id, role) VALUES (%s,%s,'owner')",
            (tenant_id, user_id),
        )
        print(f"[CREATED] {EMAIL}  id={user_id}  role={ROLE}  plan={PLAN}")

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=LOCAL_DSN,
                        help="PostgreSQL DSN (default: local Docker DB)")
    args = parser.parse_args()
    run(args.dsn)
