"""Lazy DB model imports to avoid circular dependencies."""


def get_user_model():
    from .db.models import User
    return User


def get_tenant_model():
    from .db.models import Tenant
    return Tenant
