from temporalos.verticals.base import VerticalPack, VerticalPackRegistry, get_vertical_registry
from temporalos.verticals.sales import SalesPack
from temporalos.verticals.ux_research import UXResearchPack
from temporalos.verticals.customer_success import CustomerSuccessPack
from temporalos.verticals.real_estate import RealEstatePack

__all__ = [
    "VerticalPack", "VerticalPackRegistry", "get_vertical_registry",
    "SalesPack", "UXResearchPack", "CustomerSuccessPack", "RealEstatePack",
]


def _build_registry() -> VerticalPackRegistry:
    r = VerticalPackRegistry()
    for pack in [SalesPack(), UXResearchPack(), CustomerSuccessPack(), RealEstatePack()]:
        r.register(pack)
    return r


_REGISTRY: VerticalPackRegistry | None = None


def get_default_vertical_registry() -> VerticalPackRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY
