class UpdateManager:
    def __init__(self):
        self.current_version = "0.1.0"

    def check_for_update(self) -> bool:
        return False

    def apply_update(self, version: str):
        self.current_version = version