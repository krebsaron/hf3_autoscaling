#!/usr/bin/env python3
import os
import re
from pathlib import Path

import requests

CSRF_RE = re.compile(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']')
PHOTO_RE = re.compile(r"/photo/(\d+)/")


def csrf(html: str) -> str:
    m = CSRF_RE.search(html)
    if not m:
        raise RuntimeError("CSRF token not found")
    return m.group(1)


def main() -> None:
    host = os.getenv("TARGET_HOST", "").rstrip("/")
    username = os.getenv("PHOTOALBUM_USERNAME", "")
    password = os.getenv("PHOTOALBUM_PASSWORD", "")
    test_image_path = os.getenv("TEST_IMAGE_PATH", "test_image.png")

    if not host:
        raise RuntimeError("TARGET_HOST is required")
    if not username or not password:
        raise RuntimeError("PHOTOALBUM_USERNAME and PHOTOALBUM_PASSWORD are required")

    path = Path(test_image_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[1] / path
    if not path.exists():
        raise RuntimeError(f"Test image not found: {path}")

    s = requests.Session()

    login_page = s.get(f"{host}/accounts/login/", timeout=30)
    login_page.raise_for_status()
    login_token = csrf(login_page.text)

    login_res = s.post(
        f"{host}/accounts/login/",
        data={
            "username": username,
            "password": password,
            "csrfmiddlewaretoken": login_token,
        },
        headers={"Referer": f"{host}/accounts/login/"},
        allow_redirects=True,
        timeout=30,
    )
    login_res.raise_for_status()
    if "Please enter a correct" in login_res.text:
        raise RuntimeError("Login failed with provided credentials")

    list_res = s.get(f"{host}/?sort=date_desc&search=", timeout=30)
    list_res.raise_for_status()
    ids = PHOTO_RE.findall(list_res.text)
    if not ids:
        raise RuntimeError("No photo IDs found on list page")

    photo_id = ids[0]
    detail_res = s.get(f"{host}/photo/{photo_id}/", timeout=30)
    detail_res.raise_for_status()

    upload_page = s.get(f"{host}/upload/", timeout=30)
    upload_page.raise_for_status()
    upload_token = csrf(upload_page.text)

    with open(path, "rb") as fp:
        up_res = s.post(
            f"{host}/upload/",
            data={
                "name": "functional-check-upload",
                "csrfmiddlewaretoken": upload_token,
            },
            files={"image": (path.name, fp, "image/png")},
            headers={"Referer": f"{host}/upload/"},
            allow_redirects=False,
            timeout=60,
        )

    if up_res.status_code not in [302, 303]:
        raise RuntimeError(f"Upload did not redirect as expected, status={up_res.status_code}")

    location = up_res.headers.get("Location", "")
    created_ids = PHOTO_RE.findall(location)
    if not created_ids:
        raise RuntimeError(f"Could not extract created photo id from Location: {location}")

    created_id = created_ids[0]

    delete_page = s.get(f"{host}/delete/{created_id}/", timeout=30)
    delete_page.raise_for_status()
    delete_token = csrf(delete_page.text)

    del_res = s.post(
        f"{host}/delete/{created_id}/",
        data={"csrfmiddlewaretoken": delete_token},
        headers={"Referer": f"{host}/delete/{created_id}/"},
        allow_redirects=True,
        timeout=30,
    )
    del_res.raise_for_status()

    print("Functional check OK: login, list, detail, upload(test_image), delete")


if __name__ == "__main__":
    main()
