from whitenoise.storage import (
    CompressedManifestStaticFilesStorage,
)


class ZaryaCompressedManifestStaticFilesStorage(
    CompressedManifestStaticFilesStorage
):
    """
    Keep collected static files readable by the Nginx worker.

    These permissions apply only to STATIC_ROOT. User-uploaded media keeps
    the default FileSystemStorage contract.
    """

    def __init__(
        self,
        *args,
        **kwargs,
    ):
        kwargs["file_permissions_mode"] = 0o644
        kwargs["directory_permissions_mode"] = 0o755

        super().__init__(
            *args,
            **kwargs,
        )
