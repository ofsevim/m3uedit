"""Atomic playlist imports and edits independent of Streamlit widgets."""

import uuid

import pandas as pd

from utils import config
from utils.parser import detect_type, filter_channels, parse_m3u_lines
from utils.security import validate_url

CHANNEL_ID = "_channel_id"


def ensure_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for name, default in [
        ("Grup", "Genel"),
        ("Kanal Adı", ""),
        ("URL", ""),
        ("LogoURL", ""),
        ("Tür", ""),
        ("Durum", "❔ Bekliyor"),
    ]:
        if name not in frame:
            frame[name] = default
        else:
            frame[name] = frame[name].fillna(default)
    if CHANNEL_ID not in frame:
        frame[CHANNEL_ID] = [uuid.uuid4().hex for _ in range(len(frame))]
    else:
        missing = frame[CHANNEL_ID].isna() | (frame[CHANNEL_ID] == "")
        frame.loc[missing, CHANNEL_ID] = [uuid.uuid4().hex for _ in range(int(missing.sum()))]
    if "_Header" in frame and not frame.empty:
        headers = frame["_Header"].dropna()
        if not headers.empty:
            frame.attrs["m3u_header"] = headers.iloc[0]
    frame = frame.reset_index(drop=True)
    if not frame[CHANNEL_ID].is_unique or frame[CHANNEL_ID].isna().any():
        raise ValueError("Kanal kimlikleri geçersiz.")
    return frame


def import_playlist(source, *, only_tr=False) -> pd.DataFrame:
    if isinstance(source, bytes):
        if len(source) > config.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise ValueError(f"Dosya en fazla {config.MAX_FILE_SIZE_MB} MB olabilir.")
        lines = source.splitlines()
    else:
        lines = source
    channels = filter_channels(parse_m3u_lines(lines), only_tr)
    if not channels:
        raise ValueError("Seçilen filtrelere uygun kanal bulunamadı.")
    frame = ensure_columns(pd.DataFrame(channels))
    for url in frame["URL"]:
        validate_url(url)
    return frame


def merge_visible_edits(
    original: pd.DataFrame, visible_ids: list[str], edited: pd.DataFrame
) -> pd.DataFrame:
    """Apply additions/deletions only to the visible view; retain hidden metadata."""
    original = ensure_columns(original)
    lookup = original.set_index(CHANNEL_ID).to_dict("index")
    visible = set(visible_ids)
    if not visible.issubset(lookup):
        raise ValueError("Liste değişti; tabloyu yenileyin.")
    updates, additions = {}, []
    for row in edited.to_dict("records"):
        identifier = row.get(CHANNEL_ID)
        is_new = identifier is None or pd.isna(identifier) or identifier == ""
        if not is_new and (identifier not in visible or identifier in updates):
            raise ValueError("Kanal kimliği geçersiz veya yinelenmiş.")
        record = {} if is_new else lookup[identifier].copy()
        for key in ("Grup", "Kanal Adı", "URL"):
            value = row.get(key, "")
            record[key] = "" if value is None or pd.isna(value) else str(value).strip()
        if not record["Kanal Adı"]:
            raise ValueError("Kanal adı boş olamaz.")
        validate_url(record["URL"])
        record["Grup"] = record["Grup"] or "Genel"
        if is_new or record["URL"] != lookup[identifier]["URL"]:
            record["Tür"] = detect_type(record["URL"])
            record["Durum"] = "❔ Bekliyor"
        record[CHANNEL_ID] = uuid.uuid4().hex if is_new else identifier
        if is_new:
            additions.append(record)
        else:
            updates[identifier] = record
    records = []
    for row in original.to_dict("records"):
        identifier = row[CHANNEL_ID]
        if identifier not in visible:
            records.append(row)
        elif identifier in updates:
            records.append(updates[identifier])
    result = ensure_columns(pd.DataFrame(records + additions, columns=original.columns))
    result.attrs = original.attrs.copy()
    return result
