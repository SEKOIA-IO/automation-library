from beyondtrust_modules.syslog_helpers import extract_when_timestamp, iter_reassembled_records, parse_syslog_line


class TestParseSyslogLine:
    def test_single_part_line(self):
        line = (
            "Mar 10 11:55:00 test BG[24183]: 1427:01:01:"
            "site=test.beyondtrustcloud.com;when=1773161700;who=JOHN DOE (john.doe@example.org);"
            "who_ip=1.2.3.4;event=setting_changed;old_api=0;new_api=1"
        )
        record = parse_syslog_line(line)
        assert record is not None
        assert record.date_str == "Mar 10 11:55:00"
        assert record.tenant_id == "test"
        assert record.appname == "BG"
        assert record.pid == 24183
        assert record.number == 1427
        assert record.part_number == 1
        assert record.total_parts == 1
        assert record.payload.startswith("site=test.beyondtrustcloud.com")
        assert "event=setting_changed" in record.payload

    def test_multi_part_line(self):
        line = "Mar 16 03:10:36 test BG[77178]: 1427:03:05:some_payload_part_3"
        record = parse_syslog_line(line)
        assert record is not None
        assert record.pid == 77178
        assert record.number == 1427
        assert record.part_number == 3
        assert record.total_parts == 5
        assert record.payload == "some_payload_part_3"

    def test_invalid_line(self):
        assert parse_syslog_line("") is None
        assert parse_syslog_line("not a syslog line") is None
        assert parse_syslog_line("Mar 10 11:55:00 test BG: missing brackets") is None

    def test_single_digit_day(self):
        line = "Mar  3 11:55:00 test BG[100]: 1:01:01:payload"
        record = parse_syslog_line(line)
        assert record is not None
        assert record.date_str == "Mar  3 11:55:00"
        assert record.pid == 100


class TestIterReassembledRecords:
    def test_single_part_records(self):
        lines = [
            "Mar 10 11:55:00 test BG[24183]: 1427:01:01:"
            "site=test.beyondtrustcloud.com;when=1773161700;event=setting_changed;old_api=0;new_api=1",
            "Mar 10 11:55:01 test BG[24182]: 1427:01:01:"
            "site=test.beyondtrustcloud.com;when=1773161701;event=setting_changed;old_api=1;new_api=0",
        ]
        result = list(iter_reassembled_records(lines))
        assert len(result) == 2
        assert result[0].startswith("site=test.beyondtrustcloud.com;when=1773161700")
        assert result[1].startswith("site=test.beyondtrustcloud.com;when=1773161701")

    def test_multi_part_records(self):
        lines = [
            "Mar 16 03:10:36 test BG[77178]: 1427:01:03:site=test.beyondtrustcloud.com;when=1773648636;",
            "Mar 16 03:10:36 test BG[77178]: 1427:02:03:event=user_changed;",
            "Mar 16 03:10:36 test BG[77178]: 1427:03:03:old_username=jane.doe@example.com",
        ]
        result = list(iter_reassembled_records(lines))
        assert len(result) == 1
        expected = (
            "site=test.beyondtrustcloud.com;when=1773648636;" "event=user_changed;" "old_username=jane.doe@example.com"
        )
        assert result[0] == expected

    def test_multi_part_records_out_of_order(self):
        lines = [
            "Mar 16 03:10:36 test BG[77178]: 1427:03:03:part_3",
            "Mar 16 03:10:36 test BG[77178]: 1427:01:03:part_1",
            "Mar 16 03:10:36 test BG[77178]: 1427:02:03:part_2",
        ]
        result = list(iter_reassembled_records(lines))
        assert len(result) == 1
        assert result[0] == "part_1part_2part_3"

    def test_mixed_records(self):
        lines = [
            "Mar 10 11:55:00 test BG[24183]: 1427:01:01:"
            "site=test.beyondtrustcloud.com;when=1773161700;event=setting_changed",
            "Mar 16 03:10:36 test BG[77178]: 1428:01:02:first_part;",
            "Mar 16 03:10:36 test BG[77178]: 1428:02:02:second_part",
        ]
        result = list(iter_reassembled_records(lines))
        assert len(result) == 2

    def test_invalid_lines_skipped(self):
        lines = [
            "not a syslog line",
            "Mar 10 11:55:00 test BG[24183]: 1427:01:01:valid_payload",
            "",
        ]
        result = list(iter_reassembled_records(lines))
        assert len(result) == 1
        assert result[0] == "valid_payload"

    def test_empty_input(self):
        assert list(iter_reassembled_records([])) == []

    def test_single_part_yielded_immediately(self):
        """Single-part records should be yielded without buffering."""
        yielded = []
        lines = [
            "Mar 10 11:55:00 test BG[24183]: 1427:01:01:first_event",
            "Mar 10 11:55:01 test BG[24184]: 1428:01:01:second_event",
        ]
        for payload in iter_reassembled_records(lines):
            yielded.append(payload)

        assert yielded == ["first_event", "second_event"]

    def test_incomplete_records_flushed(self):
        """Incomplete multi-part records should be flushed at the end."""
        lines = [
            "Mar 16 03:10:36 test BG[77178]: 1427:01:03:part_1;",
            "Mar 16 03:10:36 test BG[77178]: 1427:02:03:part_2",
            # Part 3 is missing
        ]
        result = list(iter_reassembled_records(lines))
        assert len(result) == 1
        assert result[0] == "part_1;part_2"

    def test_accepts_generator_input(self):
        """Should accept a generator (lazy iterable), not just a list."""

        def line_generator():
            yield "Mar 10 11:55:00 test BG[24183]: 1427:01:01:payload_from_generator"

        result = list(iter_reassembled_records(line_generator()))
        assert result == ["payload_from_generator"]


class TestExtractWhenTimestamp:
    def test_extract_timestamp(self):
        payload = "site=test.beyondtrustcloud.com;when=1773161700;event=setting_changed"
        assert extract_when_timestamp(payload) == 1773161700

    def test_extract_at_start(self):
        payload = "when=1773161700;event=setting_changed"
        assert extract_when_timestamp(payload) == 1773161700

    def test_extract_at_end(self):
        payload = "site=test.beyondtrustcloud.com;when=1773161700"
        assert extract_when_timestamp(payload) == 1773161700

    def test_missing_when(self):
        payload = "site=test.beyondtrustcloud.com;event=setting_changed"
        assert extract_when_timestamp(payload) is None

    def test_empty_payload(self):
        assert extract_when_timestamp("") is None
