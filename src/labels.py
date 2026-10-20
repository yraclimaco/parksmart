"""Basic label formatting; alias verification is a separate step."""

import re
import pandas as pd

# Add placeholders only after reviewing the source documentation.
DEFAULT_MISSING = frozenset({"", "n/a", "na", "null", "none", "nan"})


def format_label(value, missing_placeholders=DEFAULT_MISSING):
    """Normalize whitespace and word case while retaining uppercase codes.

    Numeric labels, including zero, remain strings for later review.
    Existing uppercase tokens are preserved conservatively (for example TDLLN).
    Other words are capitalized across slash/parenthesis boundaries.
    Attached duration units (2hr, 30min) use lowercase notation.
    Uppercase words are not automatically distinguished from acronyms.

    Args:
        value: Source scalar label, numeric identifier, or missing value.
        missing_placeholders: Case-insensitive text treated as missing.

    Returns:
        Formatted string or pd.NA.
    """
    if pd.isna(value):
        return pd.NA
    text = re.sub(r"\s+", " ", str(value)).strip()
    if text.casefold() in {str(item).casefold() for item in missing_placeholders}:
        return pd.NA

    def capitalize_word(match):
        word = match.group(0)
        # Attached duration units are notation, not words to title-case.
        # Preserve the abbreviation: 2hr/2HR -> 2hr, without changing duration.
        if (
            match.start() > 0
            and text[match.start() - 1].isdigit()
            and word.casefold() in {"hr", "hrs", "min", "mins"}
        ):
            return word.casefold()
        return word if word.isupper() else word.capitalize()

    # Match words within punctuation, so West/Vela and (Gliderport) retain
    # their word boundaries. Internal apostrophes remain part of a word.
    return re.sub(r"[^\W\d_]+(?:['’][^\W\d_]+)*", capitalize_word, text)


# Full-label patterns only: no loading/patient/reserved qualifiers are inferred.
TIMED_CATEGORY_TYPES = r"(?:Visitor|A|B|S|D|SR|V)"
TIMED_CATEGORY_PREFIX = re.compile(
    rf"(?P<duration>\d+(?:\.\d+)?)\s*(?P<unit>Hours?|Hrs?) (?P<kind>{TIMED_CATEGORY_TYPES})",
    re.IGNORECASE,
)
TIMED_CATEGORY_SUFFIX = re.compile(
    rf"(?P<kind>{TIMED_CATEGORY_TYPES}) (?P<duration>\d+(?:\.\d+)?)\s*(?P<unit>Hours?|Hrs?)",
    re.IGNORECASE,
)


def format_category(value, missing_placeholders=DEFAULT_MISSING):
    """Format a category and order an exact hour-limited label as type then limit.

    Only full labels with a recognized type and explicit numeric hour duration
    are reordered. Hr/Hrs/Hour/Hours use canonical unit Hour. Extra qualifiers,
    duplicated wording, and separate subtype values are not interpreted.

    Args:
        value: Raw category value.
        missing_placeholders: Case-insensitive text treated as missing.

    Returns:
        Formatted category string or pd.NA.
    """
    text = format_label(value, missing_placeholders)
    if pd.isna(text):
        return pd.NA
    match = TIMED_CATEGORY_PREFIX.fullmatch(text) or TIMED_CATEGORY_SUFFIX.fullmatch(
        text
    )
    if match is None:
        return text
    kind = match.group("kind")
    return f"{kind} {match.group('duration')} Hour"


def format_labels(records, missing_placeholders=DEFAULT_MISSING):
    """Add formatted columns without modifying the three raw columns.

    Args:
        records: Table containing facility_raw, category_raw, and subtype_raw.
        missing_placeholders: Case-insensitive text treated as missing.

    Returns:
        Copy of records with facility, category, and subtype columns.
    """
    result = records.copy()
    for field in ("facility", "category", "subtype"):
        formatter = format_category if field == "category" else format_label
        result[field] = result[f"{field}_raw"].map(
            lambda value: formatter(value, missing_placeholders)
        )
    return result


def prepare_label_records(qpass):
    """Copy loader output and add raw label columns without losing provenance.

    For Format A, facility_raw is the loader's reconstructed location; original
    worksheet cells remain in raw_structure and raw_lot. A missing sub_type
    does not distinguish an absent source field from a blank source cell.

    Args:
        qpass: Shared loader output with labels and provenance columns.

    Returns:
        Copy with raw labels, source_sheet, quarter_label, and audit attributes.
    """
    from copy import deepcopy

    required = {
        "location",
        "type",
        "sub_type",
        "source_file",
        "sheet_name",
        "source_row",
        "academic_year",
        "quarter",
    }
    missing = required.difference(qpass.columns)
    if missing:
        raise ValueError(f"Missing loader columns: {sorted(missing)}")
    result = qpass.copy()
    for field, source in {
        "facility": "location",
        "category": "type",
        "subtype": "sub_type",
    }.items():
        result[f"{field}_raw"] = qpass[source].copy()
    result["source_sheet"] = qpass["sheet_name"]
    result["quarter_label"] = (
        qpass["academic_year"].astype("string")
        + " "
        + qpass["quarter"].astype("string")
    )
    result.attrs = deepcopy(qpass.attrs)
    return result
