from nextron_valhalla_modules.ecs_field_maps import RAW_TO_ECS, RAW_TO_ECS_BY_PRODUCT, mapping_for_product


def test_windows_process_access_keeps_source_and_target_apart():
    """C1: Sekoia's parser keeps the access *source* in ``process.*`` and
    the target under ``action.properties.*`` (Sysmon 10 fixture)."""
    win = RAW_TO_ECS_BY_PRODUCT["windows"]
    assert win["SourceImage"] == "process.executable"
    assert win["Image"] == "process.executable"
    assert win["TargetImage"] == "action.properties.TargetImage"
    assert win["TargetProcessId"] == "action.properties.TargetProcessId"
    assert win["TargetProcessGUID"] == "action.properties.TargetProcessGUID"


def test_sigmahq_pipelines_load_without_caseless_suffix():
    """Sekoia's ECS schema doesn't expose `.caseless` sub-fields; the merge
    strips the suffix. Confirm no runtime target still carries it."""
    for target in RAW_TO_ECS.values():
        assert not target.endswith(".caseless"), target


def test_macos_and_windows_maps_differ():
    """S9: macOS rules map ``ProcessName`` → ``process.name``, Windows ones
    to ``process.executable``."""
    mac = RAW_TO_ECS_BY_PRODUCT["macos"]
    win = RAW_TO_ECS_BY_PRODUCT["windows"]
    assert mac["ProcessName"] == "process.name"
    assert mac["FileName"] == "file.name"
    assert win["ProcessName"] == "process.executable"
    assert win["FileName"] == "file.path"


def test_product_match_is_case_insensitive():
    assert mapping_for_product("Windows") is RAW_TO_ECS_BY_PRODUCT["windows"]
    assert mapping_for_product("okta") is RAW_TO_ECS
    assert mapping_for_product(None) is RAW_TO_ECS
