import os
from typing import List, Tuple
from fastapi_auth_middleware import FastAPIUser
from starlette.datastructures import Headers
import requests



def verify_authorization_header(auth_header: Headers) -> Tuple[List[str], FastAPIUser]:
    if not os.environ.get("UC_APP_CODE", None):
        # 没配置相当于mock，有所有权限
        return ["admin"], FastAPIUser(first_name=None, last_name=None, user_id="mock")
    
    token = auth_header.get(auth_header.get("x-kish-token-key") or "token")
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
    user = FastAPIUser(first_name=None, last_name=None, user_id=user_id)
    admin_user: str = os.environ["UC_ADMIN_USERS"] or ""
    scopes = ["admin"] if user_id in admin_user else ["user"]
    return scopes, user