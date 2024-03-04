import json

class SettingsManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.settings = self.read_settings()

    def read_settings(self):
        try:
            with open(self.file_path, 'r') as json_file:
                return json.load(json_file)
        except FileNotFoundError:
            return {}

    def write_settings(self):
        with open(self.file_path, 'w') as json_file:
            json.dump(self.settings, json_file, indent=4)

    def get_setting(self, key, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value
        self.write_settings()