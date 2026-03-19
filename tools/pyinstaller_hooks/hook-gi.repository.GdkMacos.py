"""PyInstaller hook for gi.repository.GdkMacos (macOS GDK backend)."""

from PyInstaller.utils.hooks.gi import GiModuleInfo


def hook(hook_api):
    module_info = GiModuleInfo("GdkMacos", "4.0", hook_api=hook_api)
    if not module_info.available:
        return

    binaries, datas, hiddenimports = module_info.collect_typelib_data()

    hook_api.add_datas(datas)
    hook_api.add_binaries(binaries)
    hook_api.add_imports(*hiddenimports)
