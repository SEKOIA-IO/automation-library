from sophos_module.helper import extract_info, strip_null_values, translate_fields


def test_translate_fields():
    assert translate_fields({"name": "name", "source": "source", "created_at": "created_at"}) == {
        "name": "name",
        "suser": "source",
        "rt": "created_at",
    }


def test_strip_null_values():
    assert strip_null_values({"name1": "value1", "name2": None, "name3": "value3"}) == {
        "name1": "value1",
        "name3": "value3",
    }


def test_extract_info():
    assert extract_info(
        {
            "type": "Event::Endpoint::Threat::CleanedUp",
            "name": "Threat 'EICAR' in 'myfile.com' ",
        }
    ) == {
        "type": "Event::Endpoint::Threat::CleanedUp",
        "name": "EICAR",
        "filePath": "myfile.com",
        "detection_identity_name": "EICAR",
    }

    assert extract_info(
        {
            "type": "Event::Endpoint::DataLossPreventionUserAllowed",
            "name": "An \u2033allow transfer on acceptance by user\u2033 action was taken.  "
            "Username: WIN10CLOUD2\\Sophos  Rule names: \u2032test\u2032  User action: File open  "
            "Application Name: Google Chrome  Data Control action: Allow  "
            "File type: Plain text (ASCII/UTF-8)  File size: 36  "
            "Source path: C:\\Users\\Sophos\\Desktop\\test.txt",
        }
    ) == {
        "type": "Event::Endpoint::DataLossPreventionUserAllowed",
        "name": "allow transfer on acceptance by user",
        "user": "WIN10CLOUD2\\Sophos",
        "rule": "test",
        "user_action": "File open",
        "app_name": "Google Chrome",
        "action": "Allow",
        "file_type": "Plain text (ASCII/UTF-8)",
        "file_size": "36",
        "file_path": "C:\\Users\\Sophos\\Desktop\\test.txt",
    }
