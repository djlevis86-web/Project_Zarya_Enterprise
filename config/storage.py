import os

from whitenoise.compress import Compressor
from whitenoise.storage import (
    CompressedManifestStaticFilesStorage,
)


class ZaryaStaticCompressor(
    Compressor
):
    """
    Apply the static-file permission contract to WhiteNoise sidecar files.
    """

    def __init__(
        self,
        *args,
        file_permissions_mode,
        **kwargs,
    ):
        self.file_permissions_mode = (
            file_permissions_mode
        )

        super().__init__(
            *args,
            **kwargs,
        )

    def write_data(
        self,
        path,
        data,
        suffix,
        stat_result,
    ):
        filename = super().write_data(
            path,
            data,
            suffix,
            stat_result,
        )

        os.chmod(
            filename,
            self.file_permissions_mode,
        )

        return filename


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

    def create_compressor(
        self,
        **kwargs,
    ):
        kwargs["file_permissions_mode"] = (
            self.file_permissions_mode
        )

        return ZaryaStaticCompressor(
            **kwargs,
        )
