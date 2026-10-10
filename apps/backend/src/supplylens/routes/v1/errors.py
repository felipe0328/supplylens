from dataclasses import dataclass

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from supplylens.controllers.documents.exceptions import (
    DocumentInvalidContentTypeError,
    DocumentNotFoundError,
    DocumentNotUploadedError,
    InvalidJobProcessingID,
    StoreDocumentInvalidSizeError,
)
from supplylens.controllers.users.constants import INVALID_REFRESH_TOKEN
from supplylens.controllers.users.exceptions import (
    AccountNotAcceptedError,
    InvalidCredentialsError,
    InvalidEmailAddressError,
    InvalidOrExpiredRefreshTokenError,
    InvalidPasswordError,
    UserAlreadyExistsError,
    UserPendingError,
)
from supplylens.port.storage.storage import StorageUnavailableError, UploadTooLargeError
from supplylens.schemas.common import ErrorResponse

_ERROR_RESPONSE_REF = {"$ref": "#/components/schemas/ErrorResponse"}
_VALIDATION_ERROR_REF = {"$ref": "#/components/schemas/HTTPValidationError"}
_REQUEST_VALIDATION_DESCRIPTION = "The request body failed validation."


@dataclass(frozen=True)
class HttpErrorSpec:
    status_code: int
    description: str
    detail: str
    use_exception_message: bool = False


HTTP_ERRORS: dict[type[Exception], HttpErrorSpec] = {
    DocumentNotFoundError: HttpErrorSpec(
        status_code=status.HTTP_404_NOT_FOUND,
        description="The document was not found.",
        detail="Document not found.",
    ),
    DocumentNotUploadedError: HttpErrorSpec(
        status_code=status.HTTP_409_CONFLICT,
        description="The document has not been uploaded yet.",
        detail="Document has not been uploaded.",
    ),
    StoreDocumentInvalidSizeError: HttpErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        description="The upload size does not match the declared size.",
        detail="Uploaded document size does not match the declared size.",
    ),
    DocumentInvalidContentTypeError: HttpErrorSpec(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        description="The stored object is not a PDF.",
        detail="Uploaded document must be a PDF.",
    ),
    UploadTooLargeError: HttpErrorSpec(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        description="The declared file size exceeds the configured limit.",
        detail="Upload exceeds the maximum document size.",
    ),
    StorageUnavailableError: HttpErrorSpec(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        description="Object storage is unavailable.",
        detail="Object storage is unavailable.",
    ),
    InvalidJobProcessingID: HttpErrorSpec(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        description="The processing job id from the database was invalid.",
        detail="Invalid database id",
    ),
    UserPendingError: HttpErrorSpec(
        status_code=status.HTTP_409_CONFLICT,
        description="The email is still pending approval.",
        detail="This email is already waiting for approval.",
        use_exception_message=True,
    ),
    UserAlreadyExistsError: HttpErrorSpec(
        status_code=status.HTTP_409_CONFLICT,
        description="The email is already accepted.",
        detail="An account with this email already exists. Log in instead.",
        use_exception_message=True,
    ),
    InvalidEmailAddressError: HttpErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        description="The email address does not meet the rules.",
        detail="Invalid email address.",
        use_exception_message=True,
    ),
    InvalidPasswordError: HttpErrorSpec(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        description="The password does not meet the registration rules.",
        detail="Password must be at least 8 characters long",
        use_exception_message=True,
    ),
    InvalidCredentialsError: HttpErrorSpec(
        status_code=status.HTTP_401_UNAUTHORIZED,
        description="The email or password is incorrect.",
        detail="Invalid email or password.",
        use_exception_message=True,
    ),
    InvalidOrExpiredRefreshTokenError: HttpErrorSpec(
        status_code=status.HTTP_401_UNAUTHORIZED,
        description="The refresh token is invalid or expired.",
        detail=INVALID_REFRESH_TOKEN,
        use_exception_message=True,
    ),
    AccountNotAcceptedError: HttpErrorSpec(
        status_code=status.HTTP_403_FORBIDDEN,
        description="The account is not accepted.",
        detail="This account is not available.",
        use_exception_message=True,
    ),
}


def http_error_spec(error: Exception) -> HttpErrorSpec:
    spec = HTTP_ERRORS.get(type(error))
    if spec is None:
        raise TypeError(f"No HTTP mapping for {type(error).__name__}")
    return spec


def public_detail(error: Exception) -> str:
    spec = http_error_spec(error)
    if spec.use_exception_message:
        return str(error)
    return spec.detail


def http_error_response(error: Exception) -> JSONResponse:
    spec = http_error_spec(error)
    return JSONResponse(
        status_code=spec.status_code,
        content={"detail": public_detail(error)},
    )


def handle_registered_http_error(_request: Request, error: Exception) -> JSONResponse:
    return http_error_response(error)


def register_http_exception_handlers(app: FastAPI) -> None:
    for error_type in HTTP_ERRORS:
        app.add_exception_handler(error_type, handle_registered_http_error)


def error_responses(
    *errors: type[Exception], validation: bool = False
) -> dict[int, dict[str, object]]:
    grouped: dict[int, list[HttpErrorSpec]] = {}
    for error in errors:
        spec = HTTP_ERRORS[error]
        grouped.setdefault(spec.status_code, []).append(spec)
    if validation:
        grouped.setdefault(status.HTTP_422_UNPROCESSABLE_CONTENT, [])

    return {
        status_code: _open_api_response(
            specs,
            validation=validation
            and status_code == status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
        for status_code, specs in grouped.items()
    }


def _open_api_response(
    specs: list[HttpErrorSpec], *, validation: bool
) -> dict[str, object]:
    descriptions = [spec.description for spec in specs]
    if validation:
        descriptions.append(_REQUEST_VALIDATION_DESCRIPTION)
    description = " ".join(descriptions)
    if not validation:
        return {"model": ErrorResponse, "description": description}
    schema: dict[str, object]
    if specs:
        schema = {"oneOf": [_ERROR_RESPONSE_REF, _VALIDATION_ERROR_REF]}
    else:
        schema = _VALIDATION_ERROR_REF
    return {
        "description": description,
        "content": {"application/json": {"schema": schema}},
    }
