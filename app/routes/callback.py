from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/callback")
def callback(request: Request):
    # Yahoo will redirect here with ?code=AUTHORIZATION_CODE
    code = request.query_params.get("code")
    return {"authorization_code": code}
