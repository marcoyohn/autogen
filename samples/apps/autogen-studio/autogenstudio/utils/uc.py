import os
import time
from typing import List, Tuple
from fastapi.requests import HTTPConnection
import jwt
from .auth_middleware import FastAPIUser
import requests


def verify_authorization(conn: HTTPConnection) -> Tuple[List[str], FastAPIUser]:
    if not os.environ.get("UC_APP_CODE", None):
        # 没配置相当于mock，有所有权限
        return ["admin"], FastAPIUser(user_name="mock_user", nick_name="mock_user", real_name="mock_user", user_id="mock")
    token_name = conn.headers.get("x-kish-token-key") or conn.cookies.get("x-kish-token-key") or "token"
    token = conn.query_params.get("access_token") or conn.headers.get(token_name) or conn.cookies.get(token_name)
    if not token:
        raise RuntimeError("用户未认证！")
    if token.startswith("jwt:"):
        jwt_token = token[4:]
        payload = jwt.decode(jwt_token, os.environ["WS_TOKEN_JWT_SECRET"], algorithms=[os.environ["WS_TOKEN_JWT_ALGORITHM"]])
        exp = int(payload["exp"])
        if time.time() > exp:
            raise RuntimeError("token效验异常！")
        return payload["scopes"], FastAPIUser(**payload["user"])
    else:
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