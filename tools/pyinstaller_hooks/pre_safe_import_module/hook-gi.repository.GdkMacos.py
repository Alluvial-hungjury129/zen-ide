"""Pre-safe-import hook for gi.repository.GdkMacos — marks it as a runtime module."""


def pre_safe_import_module(api):
    api.add_runtime_module(api.module_name)
