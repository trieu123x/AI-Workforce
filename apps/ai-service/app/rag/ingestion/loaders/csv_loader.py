import csv
import io


def load_csv(data: bytes) -> str:
    rows = csv.reader(io.StringIO(data.decode("utf-8-sig")))
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)
