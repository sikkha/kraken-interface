import subprocess
import json
from errors import CLIError, ParseError

def run_command(cmd: list, timeout: int = 5):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            raise CLIError(result.stderr.strip())

        if not result.stdout:
            raise CLIError("Empty response from Kraken CLI")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            raise ParseError("Invalid JSON output")

    except subprocess.TimeoutExpired:
        raise CLIError("Command timed out")


def get_ticker(pair: str):
    cmd = ["kraken", "ticker", pair, "-o", "json"]
    return run_command(cmd)
