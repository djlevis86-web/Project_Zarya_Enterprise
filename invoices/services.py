import uuid
import os


def generate_invoice_filename(filename):

    ext = filename.split('.')[-1]

    return f"{uuid.uuid4()}.{ext}"