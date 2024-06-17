import os
from typing import List, Tuple
from fastapi.requests import HTTPConnection
from .auth_middleware import FastAPIUser
import requests


def verify_authorization(conn: HTTPConnection) -> Tuple[List[str], FastAPIUser]:
    if not os.environ.get("UC_APP_CODE", None):
        # 没配置相当于mock，有所有权限
        return ["admin"], FastAPIUser(user_name="mock_user", nick_name="mock_user", real_name="mock_user", user_id="mock")
    token_name = conn.headers.get("x-kish-token-key") or "token"
    token = conn.headers.get(token_name) or conn.cookies.get(token_name)
    if not token:
        raise RuntimeError("用户未认证！")
    headers = {"x-auth-token": token, "x-auth-app": os.environ["UC_APP_CODE"]}
    response = requests.get(url=os.environ["UC_HTTP_API_URL_VALIDATE_TOKEN"], params=None, headers=headers)

    if response.status_code != 200:
        raise RuntimeError("token效验异常！")
    json_data = response.json()
    if json_data["statusCode"] != 200:
        raise RuntimeError(json_data["message"])
    user_id = json_data["data"]["user"]["uid"]
    user_name = json_data["data"]["user"]["username"]
    nick_name = json_data["data"]["user"]["nickname"]
    real_name = json_data["data"]["user"]["realName"]
    user = FastAPIUser(user_name=user_name, nick_name=nick_name, real_name=real_name, user_id=user_id)
    admin_user: str = os.environ["UC_ADMIN_USERS"] or ""
    scopes = ["admin"] if user_id in admin_user else ["user"]
    return scopes, user