from __future__ import annotations

import hashlib
from functools import lru_cache

from cms.models import CMSPlugin
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool


def get_session_key_hash(session_key: str) -> str:
    """Return a fixed-length identifier for a session key."""
    return hashlib.sha256(session_key.encode()).hexdigest()


@lru_cache()
def get_plugin_fields(plugin_type: str) -> list[str]:
    klass = get_plugin_class(plugin_type)
    opts = klass.model._meta.concrete_model._meta
    fields = opts.local_fields + opts.local_many_to_many
    return [field.name for field in fields]


@lru_cache()
def get_plugin_class(plugin_type: str) -> type[CMSPluginBase]:
    return plugin_pool.get_plugin(plugin_type)


@lru_cache()
def get_plugin_model(plugin_type: str) -> type[CMSPlugin]:
    return get_plugin_class(plugin_type).model


@lru_cache()
def plugin_has_m2m(plugin_type: str) -> bool:
    opts = get_plugin_class(plugin_type).model._meta.concrete_model._meta
    return bool(opts.local_many_to_many)
