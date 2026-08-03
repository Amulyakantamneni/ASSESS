# app/middleware/admin_auth.py
# Simple session-cookie admin auth (single shared admin login, no full user
# account system — matches the v1 scope agreed in the plan).

from fastapi import Request, HTTPException


def require_admin(request: Request):
    if not request.session.get("is_admin"):
        raise HTTPException(status_code=401, detail="Admin login required.")
