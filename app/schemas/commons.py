from pydantic import BaseModel

class ChangeForgotPasswordRequest(BaseModel):
    email: str
    new_password: str