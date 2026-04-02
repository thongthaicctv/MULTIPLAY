import uuid
import hashlib
import platform


def get_machine_id():

    mac = uuid.getnode()
    cpu = platform.processor()
    node = platform.node()

    raw = f"{mac}-{cpu}-{node}"

    return hashlib.sha256(raw.encode()).hexdigest()