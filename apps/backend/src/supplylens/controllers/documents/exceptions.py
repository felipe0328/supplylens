class DocumentNotFoundError(Exception):
    """Document is not found in the persistence layer."""


class DocumentNotUploadedError(Exception):
    """Document is found but has not been uploaded yet."""


class StoreDocumentInvalidSizeError(Exception):
    """Document is found but has an invalid size in the storage layer."""


class DocumentInvalidContentTypeError(Exception):
    """Document is found but has an invalid content type."""


class MismatchBetweenPersistenceAndStorageError(Exception):
    """Mismatch between the persistence and storage layers for a document."""


class InvalidJobProcessingID(Exception):
    """Received wrong job id from database"""
