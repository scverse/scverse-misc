from collections.abc import Mapping
from importlib.metadata import Distribution, distributions

from packaging.requirements import Requirement
from packaging.utils import NormalizedName, canonicalize_name

__all__ = ["req_fulfilled"]

# https://gist.github.com/notatallshaw/8030b223a1c96d489a1358181e78fdd9


def req_fulfilled(*requirements: str | Requirement) -> bool:
    dists = {canonicalize_name(d.name): d for d in distributions()}
    checking = set[Requirement]()
    for req in requirements:
        if isinstance(req, str):
            req = Requirement(req)
        if not _req_fulfilled(req, dists, checking):
            return False
    return True


def _req_fulfilled(req: Requirement, dists: Mapping[NormalizedName, Distribution], checking: set[Requirement]) -> bool:
    checking.add(req)  # TODO: maybe more sophisticated?
    if req.marker is not None and not req.marker.evaluate(context="requirement"):
        return True
    if not (dist := dists.get(canonicalize_name(req.name))) or dist.version not in req.specifier:
        return False
    if not req.extras:
        return True
    extras = set[str](dist.metadata.get_all("Provides-Extra") or ())
    for extra in req.extras & extras:
        if not all(
            _req_fulfilled(r, dists, checking)
            for r in map(Requirement, dist.metadata.get_all("Requires-Dist") or ())
            if r not in checking
            if r.marker is not None
            if r.marker.evaluate({"extra": extra}, context="requirement")
            # no need to check mandatory dependencies
            if not r.marker.evaluate(context="requirement")
        ):
            return False
    return True
