import requests
import json
from io import BytesIO
from datetime import datetime
import os
import random
import time

# ================== CONFIG ==================
username = os.environ.get("NAUKRI_EMAIL")
password = os.environ.get("NAUKRI_PASSWORD")
file_id = os.environ.get("FILE_ID")
form_key = os.environ.get("FORM_KEY")
filename = None


# ================== UTIL ==================
def generate_file_key(length):
    chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return ''.join(random.choice(chars) for _ in range(length))


# ================== LOGIN CLIENT ==================
class NaukriLoginClient:
    LOGIN_URL = "https://www.naukri.com/central-login-services/v1/login"

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password
        self.session = requests.Session()

    def _warmup_session(self):
        self.session.get("https://www.naukri.com")
        time.sleep(1)
        self.session.get("https://www.naukri.com/nlogin/login")
        time.sleep(2)

    def _get_headers(self):
        return {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "appid": "105",
            "clientid": "d3skt0p",
            "content-type": "application/json",
            "origin": "https://www.naukri.com",
            "referer": "https://www.naukri.com/nlogin/login",
            "sec-ch-ua": '"Not A;Brand";v="99", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "systemid": "jobseeker",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "x-requested-with": "XMLHttpRequest",
        }

    def _get_payload(self):
        return {
            "username": self.username,
            "password": self.password
        }

    def login(self):
        self._warmup_session()

        for attempt in range(3):
            try:
                time.sleep(random.uniform(2, 5))

                response = self.session.post(
                    self.LOGIN_URL,
                    headers=self._get_headers(),
                    json=self._get_payload(),
                    timeout=15
                )

                if response.status_code == 403:
                    print(f"Attempt {attempt+1}: Blocked (403)")
                    time.sleep(3)
                    continue

                response.raise_for_status()
                print("Login success:", response.status_code)
                return response

            except Exception as e:
                print(f"Attempt {attempt+1} failed:", e)
                time.sleep(2)

        raise Exception("Login failed after retries")

    def get_cookies(self):
        return self.session.cookies.get_dict()

    def get_bearer_token(self):
        return self.get_cookies().get("nauk_at")

    def fetch_profile_id(self):
        resp = self.session.get(
            "https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/dashboard",
            headers={
                "accept": "application/json",
                "appid": "105",
                "clientid": "d3skt0p",
                "systemid": "Naukri",
                "user-agent": "Mozilla/5.0",
                "authorization": f"Bearer {self.get_bearer_token()}",
            },
        )

        resp.raise_for_status()
        data = resp.json()

        profile_id = data.get("dashBoard", {}).get("profileId") or data.get("profileId")

        if not profile_id:
            raise Exception("Profile ID not found")

        print("Profile ID:", profile_id)
        return profile_id

    def build_required_cookies(self):
        cookies = self.get_cookies()

        result = {
            "test": "naukri.com",
            "is_login": "1"
        }

        for key in ["nauk_rt", "nauk_sid", "MYNAUKRI[UNID]"]:
            if cookies.get(key):
                result[key] = cookies[key]

        return result


# ================== MAIN ==================
def update_resume():
    if not username or not password:
        return {"success": False, "error": "Username/password missing"}

    if not file_id:
        return {"success": False, "error": "file_id missing"}

    if not form_key:
        return {"success": False, "error": "form_key missing"}

    print("Starting job...")

    today = datetime.now()
    final_filename = filename or f"resume_{today.strftime('%d_%B_%Y').lower()}.pdf"
    FILE_KEY = "U" + generate_file_key(13)

    client = NaukriLoginClient(username, password)

    try:
        client.login()
    except Exception as e:
        return {"success": False, "error": str(e)}

    token = client.get_bearer_token()
    if not token:
        return {"success": False, "error": "Bearer token missing"}

    cookies = client.build_required_cookies()

    # DOWNLOAD
    drive_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    res = requests.get(drive_url)

    if res.status_code != 200 or res.content[:4] != b'%PDF':
        return {"success": False, "error": "Invalid PDF or download failed"}

    time.sleep(random.uniform(2, 4))

    # UPLOAD
    upload_resp = requests.post(
        "https://filevalidation.naukri.com/file",
        files={"file": (final_filename, BytesIO(res.content), "application/pdf")},
        data={
            "formKey": form_key,
            "fileName": final_filename,
            "uploadCallback": "true",
            "fileKey": FILE_KEY,
        }
    )

    upload_resp.raise_for_status()

    profile_id = client.fetch_profile_id()

    profile_url = f"https://www.naukri.com/cloudgateway-mynaukri/resman-aggregator-services/v0/users/self/profiles/{profile_id}/advResume"

    payload = {
        "textCV": {
            "formKey": form_key,
            "fileKey": FILE_KEY,
            "textCvContent": None
        }
    }

    resp = client.session.post(
        profile_url,
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
        },
        cookies=cookies,
        data=json.dumps(payload)
    )

    resp.raise_for_status()

    return {"success": True, "message": "Resume updated successfully"}


# ================== RUN ==================
print(update_resume())
