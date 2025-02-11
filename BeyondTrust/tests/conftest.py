from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def sessions_list_xml():
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<session_summary_list xmlns="http://www.beyondtrust.com/sra/namespaces/API/reporting">
<session_summary lsid="e9e99aeb9ad54fb381634498502c5a1b" has_recording="0"  />
<session_summary lsid="219ca41dc71940a5a69687b49736d97b" has_recording="0"  />
</session_summary_list>"""


@pytest.fixture
def sessions_list_xml_with_one():
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<session_summary_list xmlns="http://www.beyondtrust.com/sra/namespaces/API/reporting">
<session_summary lsid="e9e99aeb9ad54fb381634498502c5a1b" has_recording="0"  />
</session_summary_list>"""


@pytest.fixture
def session_xml():
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<session_list xmlns="http://www.beyondtrust.com/sra/namespaces/API/reporting" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<session lsid="e9e99aeb9ad54fb381634498502c5a1b">
    <session_type>support</session_type>
    <lseq>8</lseq>
    <start_time timestamp="1733239565">2024-12-03T15:26:05+00:00</start_time>
    <end_time timestamp="1733240467">2024-12-03T15:41:07+00:00</end_time>
    <duration>00:15:02</duration>
    <external_key></external_key>
    <custom_attributes></custom_attributes>
    <session_chat_view_url>https://sekoia-pra.beyondtrustcloud.com/session_download?lsid=l%3De9e99aeb9ad54fb381634498502c5a1b%3Bh%3D3a68ddba411dd2aeae0c68139afd991944d42f0d%3Bt%3Dsd%3Bm%3Dchat&amp;dl_action=chat&amp;view=1</session_chat_view_url>
    <session_chat_download_url>https://sekoia-pra.beyondtrustcloud.com/session_download?lsid=l%3De9e99aeb9ad54fb381634498502c5a1b%3Bh%3D3a68ddba411dd2aeae0c68139afd991944d42f0d%3Bt%3Dsd%3Bm%3Dchat&amp;dl_action=chat</session_chat_download_url>
    <file_transfer_count>2</file_transfer_count>
    <file_move_count>0</file_move_count>
    <file_delete_count>1</file_delete_count>
    <primary_customer gsnumber="22">Sekoia.io integration</primary_customer>
    <jump_group type="shared" id="1">Sekoia.io integration</jump_group>

    <primary_rep gsnumber="21" id="1">Admin</primary_rep>
    <customer_list>
    <customer gsnumber="22">
    <username>Sekoia.io integration</username>
    <public_ip>4.231.237.19:61606</public_ip>
    <private_ip>10.0.0.4</private_ip>
    <hostname>Windows2022</hostname>
    <os>Windows Server 2022 Datacenter Azure Edition (21H2)</os>
</customer>
    </customer_list>
    <rep_list>
    <representative gsnumber="21" id="1">
    <username>admin</username>
    <display_name>Admin</display_name>
    <public_display_name>Admin</public_display_name>
    <private_display_name>Admin</private_display_name>
        <public_ip>[2a01:e34:ec57:b230:f188:56c5:7089:d987]:56722</public_ip>
    <private_ip>Unknown</private_ip>
    <os>Unknown</os>
    <session_owner>1</session_owner>
        <seconds_involved>901</seconds_involved>
</representative>
    </rep_list>
<session_details>
<event timestamp="1733239565" event_type="Session Start" >

    </event>
<event timestamp="1733239565" event_type="Conference Owner Changed" >

    <destination type="system" gsnumber="0">Pre-start Conference</destination>
    <data>
            <value name="owner" value="Pre-start Conference" />
        </data>
</event>
</session_details>
</session>
</session_list>
"""
