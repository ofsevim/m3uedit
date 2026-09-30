"""Generate only the export format requested by the user."""

from utils.parser import (
    convert_df_to_csv,
    convert_df_to_json,
    convert_df_to_m3u,
    convert_df_to_proxied_m3u,
    convert_df_to_txt,
)


def make_export(frame, format_name, *, proxy_base_url=None):
    if format_name == "VPN Köprüsü M3U":
        if not proxy_base_url:
            raise ValueError("Proxy adresi gerekli.")
        return (
            convert_df_to_proxied_m3u(frame, proxy_base_url),
            "vpn_koprusu.m3u",
            "application/x-mpegurl",
        )
    converters = {
        "M3U": (convert_df_to_m3u, "m3u", "application/x-mpegurl"),
        "M3U8": (convert_df_to_m3u, "m3u8", "application/x-mpegurl"),
        "CSV": (convert_df_to_csv, "csv", "text/csv"),
        "JSON": (convert_df_to_json, "json", "application/json"),
        "TXT": (convert_df_to_txt, "txt", "text/plain"),
    }
    convert, extension, mime = converters[format_name]
    return convert(frame), f"kanallar.{extension}", mime
