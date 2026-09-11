# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
import json

from insta.topics import classify, compile_topics, load_profile

TOPICS = [
    {"id": "waste", "name": "Waste", "keywords": ["ricicl", "api "]},
    {"id": "food", "name": "Food", "keywords": ["vegan"]},
]


def test_prefix_keyword_matches_word_start():
    compiled = compile_topics(TOPICS)
    assert classify("Il riciclo e i materiali riciclabili", compiled) == ["waste"]


def test_prefix_keyword_does_not_match_inside_a_word():
    compiled = compile_topics(TOPICS)
    assert classify("un'apice e un fermare", compiled) == []


def test_trailing_space_means_whole_word():
    compiled = compile_topics(TOPICS)
    assert classify("le api sono importanti", compiled) == ["waste"]
    assert classify("un apiario", compiled) == []


def test_matching_is_case_insensitive_and_multi_label():
    compiled = compile_topics(TOPICS)
    assert classify("RICICLO per Vegani", compiled) == ["waste", "food"]


def test_no_topics_yields_no_labels():
    assert classify("anything", compile_topics([])) == []


def test_load_profile_reads_file(tmp_path):
    (tmp_path / "profile.json").write_text(json.dumps({"about": "hi", "topics": TOPICS}))
    assert load_profile(tmp_path)["about"] == "hi"


def test_load_profile_defaults_when_missing(tmp_path):
    assert load_profile(tmp_path) == {"about": "", "topics": []}
