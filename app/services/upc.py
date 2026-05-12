import re


def normalize(raw_input: str) -> list[str]:
    """
    Takes a dirty UPC input and returns a sorted list of unique candidate
    variants to try against Keepa's /product?code= endpoint.

    Steps:
    1. Strip whitespace, remove all non-digit characters.
    2. If empty → return [].
    3. Generate variants based on digit count:
       - ≤12 digits: pad with leading zeros to 12. Include both original and
                     padded if they differ.
       - 13 digits:  include as-is + strip first digit (→ 12 digits).
       - 14 digits:  include as-is + strip first digit (→ 13) + strip first
                     two digits (→ 12).
       - >14 digits: strip leading zeros, then recursively normalize.
    4. Return sorted list of unique variants.
    """
    digits = re.sub(r"\D", "", raw_input.strip())

    if not digits:
        return []

    return _generate_variants(digits)


def _generate_variants(digits: str) -> list[str]:
    length = len(digits)

    if length <= 12:
        padded = digits.zfill(12)
        variants = {padded}
        if digits != padded:
            variants.add(digits)
        return sorted(variants)

    if length == 13:
        return sorted({digits, digits[1:]})

    if length == 14:
        return sorted({digits, digits[1:], digits[2:]})

    # >14 digits: strip leading zeros and recurse
    stripped = digits.lstrip("0")
    if not stripped:
        # all zeros edge case — treat as zero-padded 12-digit string
        return ["000000000000"]
    return _generate_variants(stripped)
