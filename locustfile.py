import base64
import os
import random
import re
import time
import uuid
from pathlib import Path
from collections import deque

from locust import HttpUser, LoadTestShape, between, task


CSRF_RE = re.compile(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']')
PHOTO_DETAIL_RE = re.compile(r"/photo/(\d+)/")
PROJECT_ROOT = Path(__file__).resolve().parent
TEST_IMAGE_PATH = os.getenv("TEST_IMAGE_PATH", "test_image.png")
LOCUST_USE_SHAPE = os.getenv("LOCUST_USE_SHAPE", "0") == "1"


def extract_csrf_token(html_text: str) -> str | None:
    match = CSRF_RE.search(html_text)
    if not match:
        return None
    return match.group(1)


def extract_photo_ids(html_text: str) -> list[int]:
    ids = PHOTO_DETAIL_RE.findall(html_text)
    return [int(pid) for pid in ids]


def tiny_png_bytes() -> bytes:
    # 1x1 transparent PNG for repeatable upload tests.
    b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4"
        "//8/AwAI/AL+X+0XWQAAAABJRU5ErkJggg=="
    )
    return base64.b64decode(b64)


def upload_image_bytes() -> tuple[str, bytes, str]:
    image_path = Path(TEST_IMAGE_PATH)
    if not image_path.is_absolute():
        image_path = PROJECT_ROOT / image_path

    if image_path.exists() and image_path.is_file():
        suffix = image_path.suffix.lower()
        if suffix in [".jpg", ".jpeg"]:
            mime = "image/jpeg"
        elif suffix == ".gif":
            mime = "image/gif"
        elif suffix == ".webp":
            mime = "image/webp"
        else:
            mime = "image/png"
        return image_path.name, image_path.read_bytes(), mime

    return "locust_test.png", tiny_png_bytes(), "image/png"


class PhotoAlbumUser(HttpUser):
    wait_time = between(float(os.getenv("LOCUST_WAIT_MIN", "0.6")), float(os.getenv("LOCUST_WAIT_MAX", "2.0")))

    username = os.getenv("PHOTOALBUM_USERNAME", "user")
    password = os.getenv("PHOTOALBUM_PASSWORD", "user-12345678")
    upload_filename, upload_content, upload_mime = upload_image_bytes()

    def on_start(self) -> None:
        self.created_photo_ids: deque[int] = deque(maxlen=200)
        self.last_seen_photo_ids: list[int] = []
        self.login()

    def on_stop(self) -> None:
        while self.created_photo_ids:
            photo_id = self.created_photo_ids.pop()
            self._delete_photo_by_id(photo_id, mark_failure=False)

    def login(self) -> None:
        with self.client.get("/accounts/login/", name="GET /accounts/login", catch_response=True) as response:
            token = extract_csrf_token(response.text)
            if not token:
                response.failure("No CSRF token on login page")
                return

        payload = {
            "username": self.username,
            "password": self.password,
            "csrfmiddlewaretoken": token,
        }
        headers = {
            "Referer": f"{self.host}/accounts/login/",
        }

        with self.client.post(
            "/accounts/login/",
            data=payload,
            headers=headers,
            allow_redirects=True,
            name="POST /accounts/login",
            catch_response=True,
        ) as response:
            bad_creds = "Please enter a correct" in response.text
            if response.status_code >= 400 or bad_creds:
                response.failure("Login failed")
                return
            response.success()

    @task(4)
    def browse_gallery(self) -> None:
        sort = random.choice(["name", "name_desc", "date_desc", "date_asc"])
        search = random.choice(["", "test", "a", "photo"])
        query = f"?sort={sort}"
        if search:
            query += f"&search={search}"

        with self.client.get(f"/{query}", name="GET / (list)", catch_response=True) as response:
            if response.status_code >= 400:
                response.failure("List page failed")
                return
            ids = extract_photo_ids(response.text)
            if ids:
                self.last_seen_photo_ids = ids
            response.success()

    @task(3)
    def view_photo_detail(self) -> None:
        if not self.last_seen_photo_ids:
            self.browse_gallery()
            if not self.last_seen_photo_ids:
                return

        photo_id = random.choice(self.last_seen_photo_ids)
        with self.client.get(f"/photo/{photo_id}/", name="GET /photo/:id", catch_response=True) as response:
            if response.status_code == 404:
                # Under concurrent upload/delete churn, a previously listed photo can disappear.
                self.last_seen_photo_ids = []
                response.success()
                return
            if response.status_code >= 400:
                response.failure(f"Detail page failed for id={photo_id}")
                return
            response.success()

    @task(1)
    def upload_photo(self) -> None:
        with self.client.get("/upload/", name="GET /upload", catch_response=True) as response:
            token = extract_csrf_token(response.text)
            if not token:
                response.failure("No CSRF token on upload page")
                return

        photo_name = f"locust-{int(time.time())}-{uuid.uuid4().hex[:8]}"
        payload = {
            "name": photo_name,
            "csrfmiddlewaretoken": token,
        }
        files = {
            "image": (self.upload_filename, self.upload_content, self.upload_mime),
        }
        headers = {
            "Referer": f"{self.host}/upload/",
        }

        with self.client.post(
            "/upload/",
            data=payload,
            files=files,
            headers=headers,
            allow_redirects=False,
            name="POST /upload",
            catch_response=True,
        ) as response:
            if response.status_code >= 400:
                response.failure("Upload failed")
                return

            location_header = response.headers.get("Location", "")
            ids_from_location = PHOTO_DETAIL_RE.findall(location_header)
            if ids_from_location:
                self.created_photo_ids.append(int(ids_from_location[0]))
                response.success()
                return

            ids_from_body = PHOTO_DETAIL_RE.findall(response.text)
            if ids_from_body:
                self.created_photo_ids.append(int(ids_from_body[0]))
                response.success()
                return

            ids_from_url = PHOTO_DETAIL_RE.findall(str(response.url))
            if ids_from_url:
                self.created_photo_ids.append(int(ids_from_url[0]))
                response.success()
                return

            response.failure("Upload succeeded but created photo id is unknown")

    @task(1)
    def delete_owned_photo(self) -> None:
        if not self.created_photo_ids:
            return

        photo_id = self.created_photo_ids.pop()
        self._delete_photo_by_id(photo_id, mark_failure=True)

    def _delete_photo_by_id(self, photo_id: int, mark_failure: bool) -> bool:
        with self.client.get(f"/delete/{photo_id}/", name="GET /delete/:id", catch_response=True) as response:
            if response.status_code == 404:
                response.success()
                return True

            token = extract_csrf_token(response.text)
            if not token:
                if mark_failure:
                    response.failure(f"No CSRF token on delete page for id={photo_id}")
                else:
                    response.success()
                return False

            response.success()

        payload = {
            "csrfmiddlewaretoken": token,
        }
        headers = {
            "Referer": f"{self.host}/delete/{photo_id}/",
        }

        with self.client.post(
            f"/delete/{photo_id}/",
            data=payload,
            headers=headers,
            allow_redirects=True,
            name="POST /delete/:id",
            catch_response=True,
        ) as response:
            if response.status_code >= 400:
                if mark_failure:
                    response.failure(f"Delete failed for id={photo_id}")
                else:
                    response.success()
                return False

            response.success()
            return True


if LOCUST_USE_SHAPE:
    class RampUpDownShape(LoadTestShape):
        stages = [
            {"duration": 60, "users": 1, "spawn_rate": 1},
            {"duration": 120, "users": 5, "spawn_rate": 1},
            {"duration": 180, "users": 10, "spawn_rate": 2},
            {"duration": 240, "users": 15, "spawn_rate": 2},
            {"duration": 300, "users": 10, "spawn_rate": 2},
            {"duration": 360, "users": 5, "spawn_rate": 1},
            {"duration": 420, "users": 1, "spawn_rate": 1},
            {"duration": 450, "users": 0, "spawn_rate": 1},
        ]

        def tick(self):
            run_time = self.get_run_time()

            for stage in self.stages:
                if run_time < stage["duration"]:
                    return stage["users"], stage["spawn_rate"]

            return None
