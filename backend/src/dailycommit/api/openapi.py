"""Print the OpenAPI schema (used by `make gen-api`). Doesn't connect to anything."""

import json
import sys

from dailycommit.api.main import app

if __name__ == "__main__":
    json.dump(app.openapi(), sys.stdout, indent=2)
