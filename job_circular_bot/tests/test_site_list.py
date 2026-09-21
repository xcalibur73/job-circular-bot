"""The site list is what the user edits, so its parsing rules are pinned down
by tests."""

import site_list


def test_plain_url_becomes_an_entry_with_the_domain_as_name():
    parsed = site_list.parse_site_line("https://example.com/careers\n")

    assert parsed == {
        "url": "https://example.com/careers",
        "name": "example.com",
        "force_js": False,
    }


def test_comments_and_blank_lines_are_ignored():
    assert site_list.parse_site_line("# a comment") is None
    assert site_list.parse_site_line("   ") is None
    assert site_list.parse_site_line("") is None


def test_js_flag_forces_the_browser():
    parsed = site_list.parse_site_line("https://example.com/jobs |js")

    assert parsed["force_js"] is True


def test_name_flag_sets_the_display_name():
    parsed = site_list.parse_site_line("https://example.com/careers |name=Acme Ltd")

    assert parsed["name"] == "Acme Ltd"
    assert parsed["force_js"] is False


def test_flags_can_be_combined():
    parsed = site_list.parse_site_line("https://example.com/jobs |js |name=Acme Ltd")

    assert parsed["force_js"] is True
    assert parsed["name"] == "Acme Ltd"


def test_non_url_lines_are_rejected():
    assert site_list.parse_site_line("not a url") is None
    assert site_list.parse_site_line("ftp://example.com/jobs") is None


def test_load_site_lines_reads_a_file(tmp_path):
    path = tmp_path / "sites.txt"
    path.write_text(
        "# my sites\n"
        "https://example.com/careers\n"
        "\n"
        "https://example.com/jobs |js |name=Acme\n",
        encoding="utf-8",
    )

    entries = site_list.load_site_lines(path)

    assert [entry["name"] for entry in entries] == ["example.com", "Acme"]
    assert entries[1]["force_js"] is True


def test_load_site_lines_returns_empty_for_a_missing_file(tmp_path):
    assert site_list.load_site_lines(tmp_path / "nope.txt") == []
