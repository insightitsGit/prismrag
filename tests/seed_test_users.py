"""
Seed test users for all three roles: user, admin, superadmin.
Creates accounts in the database + prints credentials to stdout.

Usage (local):
    PRISMRAG_DB_DSN=postgresql://... python tests/seed_test_users.py

Usage (Azure — via psql or a one-off Container App job):
    python tests/seed_test_users.py --env azure

The script is idempotent: safe to run multiple times.
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from prismrag.auth.auth import hash_password
from prismrag.db import get_conn, release_conn


TEST_USERS = [
    {
        "email":    "test-user@prismrag-test.internal",
        "password": "TestUser!2026#",
        "role":     "user",
        "plan":     "starter",
        "full_name": "Test User",
        "company":  "Test Corp",
    },
    {
        "email":    "test-admin@prismrag-test.internal",
        "password": "TestAdmin!2026#",
        "role":     "admin",
        "plan":     "professional",
        "full_name": "Test Admin",
        "company":  "Test Corp",
    },
    {
        "email":    "test-superadmin@prismrag-test.internal",
        "password": "TestSuperAdmin!2026#",
        "role":     "superadmin",
        "plan":     "enterprise",
        "full_name": "Test Superadmin",
        "company":  "Insight IT Solutions",
    },
]


def seed(env_label: str = "local") -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        print(f"\n{'='*60}")
        print(f"  PrismRAG Test Credentials ({env_label.upper()})")
        print(f"{'='*60}")

        for u in TEST_USERS:
            email = u["email"]
            cur.execute(
                "SELECT id, role FROM prismrag.user_account WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()

            if row:
                user_id = row[0]
                # Update role + plan in case they changed
                cur.execute(
                    "UPDATE prismrag.user_account SET role = %s, plan = %s WHERE id = %s",
                    (u["role"], u["plan"], user_id),
                )
                action = "updated"
            else:
                user_id = str(uuid.uuid4())
                pw_hash = hash_password(u["password"])
                cur.execute(
                    """
                    INSERT INTO prismrag.user_account
                        (id, email, password_hash, full_name, company, plan, role,
                         email_verified, is_active, subscription_status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, TRUE, 'active')
                    """,
                    (
                        user_id, email, pw_hash,
                        u["full_name"], u["company"],
                        u["plan"], u["role"],
                    ),
                )
                action = "created"

            # Ensure tenant exists
            cur.execute(
                "SELECT id FROM prismrag.tenant WHERE owner_email = %s",
                (email,),
            )
            t_row = cur.fetchone()
            if not t_row:
                tenant_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO prismrag.tenant (id, name, owner_email, data_region)
                    VALUES (%s, %s, %s, 'eastus2')
                    """,
                    (tenant_id, f"{u['company']} Workspace", email),
                )
                # Also add as tenant_member
                try:
                    cur.execute(
                        """
                        INSERT INTO prismrag.tenant_member (tenant_id, user_id, role)
                        VALUES (%s, %s, 'owner')
                        ON CONFLICT (tenant_id, user_id) DO NOTHING
                        """,
                        (tenant_id, user_id),
                    )
                except Exception:
                    conn.rollback()

            print(f"\n  Role: {u['role'].upper()}")
            print(f"  Email:    {email}")
            print(f"  Password: {u['password']}")
            print(f"  Plan:     {u['plan']}")
            print(f"  Status:   {action}")

        conn.commit()
        print(f"\n{'='*60}")
        print("  IMPORTANT: These are test accounts — do not use in production!")
        print(f"{'='*60}\n")

    except Exception as exc:
        conn.rollback()
        print(f"Error seeding test users: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        release_conn(conn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="local", help="Label for display (local|azure)")
    args = parser.parse_args()
    seed(args.env)
