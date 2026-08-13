import datetime as dt
from typing import Optional, Tuple

from PIL import ExifTags, Image


def _to_degrees(value) -> float:
    d, m, s = value[0], value[1], value[2]
    return float(d) + float(m) / 60.0 + float(s) / 3600.0


def extract_gps_and_datetime(image_path: str) -> Tuple[Optional[float], Optional[float], Optional[dt.datetime]]:
    """사진 EXIF에서 GPS 좌표와 촬영 일시를 추출한다. 정보가 없으면 (None, None, None)."""
    lat = lng = None
    taken_at = None

    try:
        img = Image.open(image_path)
        exif = img.getexif()
        if not exif:
            return lat, lng, taken_at

        tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}

        date_str = tag_map.get("DateTimeOriginal") or tag_map.get("DateTime")
        if date_str:
            try:
                taken_at = dt.datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                taken_at = None

        gps_info = None
        gps_ifd_tag = next((k for k, v in ExifTags.TAGS.items() if v == "GPSInfo"), None)
        if gps_ifd_tag is not None:
            gps_info = exif.get_ifd(gps_ifd_tag)

        if gps_info:
            gps_tag_map = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_info.items()}
            gps_lat = gps_tag_map.get("GPSLatitude")
            gps_lat_ref = gps_tag_map.get("GPSLatitudeRef", "N")
            gps_lng = gps_tag_map.get("GPSLongitude")
            gps_lng_ref = gps_tag_map.get("GPSLongitudeRef", "E")

            if gps_lat and gps_lng:
                lat = _to_degrees(gps_lat)
                if gps_lat_ref in ("S", "s"):
                    lat = -lat
                lng = _to_degrees(gps_lng)
                if gps_lng_ref in ("W", "w"):
                    lng = -lng
    except Exception:
        return None, None, None

    return lat, lng, taken_at
