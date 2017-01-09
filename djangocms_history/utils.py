from cms.plugin_pool import plugin_pool

from django.utils.lru_cache import lru_cache


@lru_cache()
def get_plugin_fields(plugin_type):
    klass = get_plugin_class(plugin_type)
    opts = klass.model._meta.concrete_model._meta
    fields = opts.local_fields + opts.local_many_to_many
    return [field.name for field in fields]


@lru_cache()
def get_plugin_class(plugin_type):
    return plugin_pool.get_plugin(plugin_type)


@lru_cache()
def get_plugin_model(plugin_type):
    return get_plugin_class(plugin_type).model
