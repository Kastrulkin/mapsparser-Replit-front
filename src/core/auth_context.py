"""Explicit identity context for application services, independent of Flask.

Resource membership remains a repository check. Keeping the session scope here
prevents callers from accidentally reducing a demo/impersonated session to an ID.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    session_kind: str = "standard"
    scope_business_id: str = ""
    is_superadmin: bool = False
    impersonating: bool = False

    @classmethod
    def from_session(cls, session):
        return cls(
            user_id=str(session.get("user_id") or session.get("id") or ""),
            session_kind=str(session.get("session_kind") or "standard"),
            scope_business_id=str(session.get("scope_business_id") or ""),
            is_superadmin=bool(session.get("is_superadmin")),
            impersonating=bool(session.get("impersonating") or session.get("impersonated_by")),
        )

    def permits_business(self, business_id):
        return bool(self.user_id) and (
            self.session_kind != "demo" or self.scope_business_id == str(business_id)
        )

    @property
    def permits_personalization_signal(self):
        return bool(self.user_id) and self.session_kind == "standard" and not self.is_superadmin and not self.impersonating
