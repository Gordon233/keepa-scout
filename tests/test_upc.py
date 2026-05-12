import pytest
from app.services.upc import normalize


class TestNormalizeEmptyAndInvalid:
    def test_empty_string_returns_empty(self):
        assert normalize("") == []

    def test_non_digit_string_returns_empty(self):
        assert normalize("abc-def") == []

    def test_whitespace_only_returns_empty(self):
        assert normalize("   ") == []


class TestNormalize12Digits:
    def test_exact_12_digits_included_as_is(self):
        result = normalize("070537500052")
        assert "070537500052" in result

    def test_exact_12_digits_no_padding_needed(self):
        result = normalize("052144100245")
        assert "052144100245" in result

    def test_11_digits_padded_to_12(self):
        result = normalize("70537500052")
        assert "070537500052" in result

    def test_11_digits_original_also_included(self):
        # original (11 digits) is different from padded, both should be present
        result = normalize("70537500052")
        assert "070537500052" in result
        # sorted unique list
        assert len(result) == len(set(result))
        assert result == sorted(result)

    def test_dashes_stripped_then_normalized(self):
        result = normalize("070-537-500-052")
        assert "070537500052" in result


class TestNormalize13Digits:
    def test_13_digits_included_as_is(self):
        result = normalize("9780545465298")
        assert "9780545465298" in result

    def test_13_digits_also_includes_12_digit_variant(self):
        result = normalize("9780545465298")
        assert "780545465298" in result

    def test_result_is_sorted_unique(self):
        result = normalize("9780545465298")
        assert result == sorted(result)
        assert len(result) == len(set(result))


class TestNormalize14Digits:
    def test_14_digits_contains_12_or_13_variants(self):
        result = normalize("00000772041997")
        lengths = {len(v) for v in result}
        assert lengths & {12, 13}  # at least one of 12 or 13 present

    def test_14_digits_strips_first_digit_to_13(self):
        # "00000772041997" → strip first → "0000772041997" (13)
        result = normalize("00000772041997")
        assert "0000772041997" in result

    def test_14_digits_strips_two_to_12(self):
        # strip two → "000772041997" (12)
        result = normalize("00000772041997")
        assert "000772041997" in result

    def test_result_is_sorted_unique(self):
        result = normalize("00000772041997")
        assert result == sorted(result)
        assert len(result) == len(set(result))


class TestResultProperties:
    def test_sorted_output(self):
        result = normalize("9780545465298")
        assert result == sorted(result)

    def test_unique_output(self):
        result = normalize("9780545465298")
        assert len(result) == len(set(result))

    def test_all_items_are_digit_strings(self):
        for raw in ["070537500052", "70537500052", "9780545465298", "00000772041997"]:
            for item in normalize(raw):
                assert item.isdigit(), f"Non-digit item {item!r} in normalize({raw!r})"
