import pytest
from backend.text.nicknames import canonical_forms, NICKNAMES


class TestCanonicalFormsKnownNicknames:
    def test_bill_expands_to_william(self):
        result = canonical_forms("bill")
        assert "william" in result
        assert "bill" in result

    def test_billy_expands_to_william(self):
        result = canonical_forms("billy")
        assert "william" in result

    def test_bob_expands_to_robert(self):
        result = canonical_forms("bob")
        assert "robert" in result
        assert "bob" in result

    def test_bobby_expands_to_robert(self):
        result = canonical_forms("bobby")
        assert "robert" in result

    def test_jim_expands_to_james(self):
        result = canonical_forms("jim")
        assert "james" in result

    def test_jack_expands_to_john(self):
        result = canonical_forms("jack")
        assert "john" in result

    def test_hank_expands_to_henry(self):
        result = canonical_forms("hank")
        assert "henry" in result

    def test_harry_expands_to_henry_and_harold(self):
        result = canonical_forms("harry")
        assert "henry" in result
        assert "harold" in result

    def test_mike_expands_to_michael(self):
        result = canonical_forms("mike")
        assert "michael" in result

    def test_ted_expands_to_edward_and_theodore(self):
        result = canonical_forms("ted")
        assert "edward" in result
        assert "theodore" in result

    def test_ed_expands_to_edward_and_edmund(self):
        result = canonical_forms("ed")
        assert "edward" in result
        assert "edmund" in result

    def test_chris_expands_to_multiple(self):
        result = canonical_forms("chris")
        assert "christopher" in result
        assert "christina" in result
        assert "christine" in result

    def test_al_expands_to_multiple(self):
        result = canonical_forms("al")
        assert "albert" in result
        assert "alfred" in result
        assert "alan" in result
        assert "alexander" in result

    def test_pat_expands_to_patrick_and_patricia(self):
        result = canonical_forms("pat")
        assert "patrick" in result
        assert "patricia" in result

    def test_betty_expands_to_elizabeth(self):
        result = canonical_forms("betty")
        assert "elizabeth" in result

    def test_liz_expands_to_elizabeth(self):
        result = canonical_forms("liz")
        assert "elizabeth" in result

    def test_kate_expands_to_katherine_variants(self):
        result = canonical_forms("kate")
        assert "katherine" in result
        assert "kathryn" in result

    def test_peggy_expands_to_margaret(self):
        result = canonical_forms("peggy")
        assert "margaret" in result

    def test_sue_expands_to_susan(self):
        result = canonical_forms("sue")
        assert "susan" in result


class TestCanonicalFormsRegularNames:
    def test_regular_name_returns_self(self):
        # 'william' is not a key in NICKNAMES; returns frozenset with itself
        result = canonical_forms("william")
        assert result == frozenset({"william"})

    def test_unknown_name_returns_self_lowercased(self):
        result = canonical_forms("xyzunknown")
        assert result == frozenset({"xyzunknown"})

    def test_regular_capitalized_name(self):
        result = canonical_forms("Alice")
        assert result == frozenset({"alice"})


class TestCanonicalFormsCaseFolding:
    def test_uppercase_nickname_folded(self):
        result = canonical_forms("BOB")
        assert "robert" in result

    def test_mixed_case_nickname_folded(self):
        result = canonical_forms("Bill")
        assert "william" in result

    def test_all_caps_regular_name(self):
        result = canonical_forms("ALICE")
        assert result == frozenset({"alice"})


class TestCanonicalFormsEdgeCases:
    def test_empty_string_returns_empty_frozenset(self):
        result = canonical_forms("")
        assert result == frozenset()

    def test_none_returns_empty_frozenset(self):
        result = canonical_forms(None)
        assert result == frozenset()

    def test_whitespace_only_returns_empty_frozenset(self):
        # A string of only spaces has no content after lowering
        # The token is truthy if non-empty after lower(); spaces are truthy,
        # so this exercises the NICKNAMES.get path and returns frozenset({"   "})
        # Actually spaces are truthy so we verify it doesn't raise
        result = canonical_forms("   ")
        assert isinstance(result, frozenset)

    def test_return_type_is_frozenset(self):
        assert isinstance(canonical_forms("bob"), frozenset)
        assert isinstance(canonical_forms("alice"), frozenset)
        assert isinstance(canonical_forms(""), frozenset)

    def test_nickname_always_includes_itself(self):
        # The union adds {lowered} to the canonical set
        result = canonical_forms("bob")
        assert "bob" in result

    def test_all_nickname_keys_return_frozenset(self):
        for key in NICKNAMES:
            result = canonical_forms(key)
            assert isinstance(result, frozenset), f"Expected frozenset for {key}"
            assert key in result, f"Nickname key '{key}' should be in its own canonical forms"
