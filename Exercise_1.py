import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path


LAST_NAME = "Manrique"
STUDENT_ID = "TUPM-26-1137"

SEED_DIGIT = int(STUDENT_ID[-1])
ID_SUM = sum(int(digit) for digit in STUDENT_ID if digit.isdigit())
RECORD_LIMIT = 1000 + ID_SUM
TARGET_STATUS_CLASS = (SEED_DIGIT % 4) + 2
REQUIRED_FIELDS = ("ip", "time", "url", "status")


def analyze_log(input_path: Path) -> tuple[list[str], list[dict[str, str]], Counter[int], Counter[str], int]:
    """Read the required sample from a CSV and collect target-class records."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Input CSV was not found: {input_path}")

    selected_records: list[dict[str, str]] = []
    status_counts: Counter[int] = Counter()
    url_counts: Counter[str] = Counter()

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("The input CSV is empty or has no header row.")

        field_names = reader.fieldnames
        normalized_names = [name.strip().casefold() for name in field_names]
        normalized_names = [
            "status" if name in {"response status", "staus"} else name
            for name in normalized_names
        ]
        if len(set(normalized_names)) != len(normalized_names):
            raise ValueError("The CSV contains duplicate column names.")

        missing_fields = [name for name in REQUIRED_FIELDS if name not in normalized_names]
        if missing_fields:
            raise ValueError(
                "The CSV is missing required columns: " + ", ".join(missing_fields)
            )

        column_names = dict(zip(normalized_names, field_names))
        records_processed = 0
        for row in reader:
            if records_processed == RECORD_LIMIT:
                break
            records_processed += 1

            line_number = records_processed + 1
            if None in row or any(row.get(column_names[name]) is None for name in REQUIRED_FIELDS):
                raise ValueError(f"Malformed or incomplete record on CSV line {line_number}.")

            status_text = row[column_names["status"]].strip()
            try:
                status_code = int(status_text)
            except ValueError as error:
                raise ValueError(
                    f"Invalid HTTP status on CSV line {line_number}: {status_text!r}."
                ) from error

            if not 100 <= status_code <= 599:
                raise ValueError(
                    f"HTTP status on CSV line {line_number} must be between 100 and 599."
                )

            if any(not row[column_names[name]].strip() for name in REQUIRED_FIELDS):
                raise ValueError(f"Required field is blank on CSV line {line_number}.")

            status_counts[status_code] += 1
            if status_code // 100 == TARGET_STATUS_CLASS:
                selected_records.append(row)
                url_counts[row[column_names["url"]].strip()] += 1

    if records_processed < RECORD_LIMIT:
        raise ValueError(
            f"Expected at least {RECORD_LIMIT} data records, found {records_processed}."
        )

    return field_names, selected_records, status_counts, url_counts, records_processed


def main() -> None:
    workspace = Path(__file__).resolve().parent
    if len(sys.argv) > 2:
        print(f"Usage: {Path(sys.argv[0]).name} [path-to-weblog.csv]")
        raise SystemExit(2)

    default_input = workspace / "data" / "weblog.csv"
    if len(sys.argv) == 2:
        input_path = Path(sys.argv[1].strip().strip('"'))
    elif default_input.is_file():
        input_path = default_input
    else:
        print(f"Default dataset not found: {default_input}")
        entered_path = input("Enter the path to your web-log CSV (or press Enter to cancel): ")
        if not entered_path.strip():
            print("No CSV selected. Download the web-log dataset and run this program again.")
            raise SystemExit(1)
        input_path = Path(entered_path.strip().strip('"'))

    try:
        field_names, selected_records, status_counts, url_counts, records_processed = (
            analyze_log(input_path)
        )

        output_dir = workspace / "output"
        backup_dir = workspace / "backup"
        output_dir.mkdir(exist_ok=True)
        backup_dir.mkdir(exist_ok=True)

        file_prefix = f"{LAST_NAME}_{STUDENT_ID}"
        filtered_path = output_dir / f"{file_prefix}_filtered.csv"
        summary_path = output_dir / f"{file_prefix}_summary.json"
        backup_path = backup_dir / summary_path.name

        with filtered_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=field_names)
            writer.writeheader()
            writer.writerows(selected_records)

        top_urls = sorted(url_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
        summary = {
            "last_name": LAST_NAME,
            "student_id": STUDENT_ID,
            "seed_digit": SEED_DIGIT,
            "id_sum": ID_SUM,
            "records_processed": records_processed,
            "target_status_class": f"{TARGET_STATUS_CLASS}xx",
            "target_records": len(selected_records),
            "status_code_counts": {
                str(code): count for code, count in sorted(status_counts.items())
            },
            "top_five_urls": [
                {"url": url, "count": count} for url, count in top_urls
            ],
        }

        with summary_path.open("w", encoding="utf-8") as output:
            json.dump(summary, output, indent=4)
            output.write("\n")

        shutil.copy2(summary_path, backup_path)
        if not backup_path.is_file() or backup_path.read_bytes() != summary_path.read_bytes():
            raise OSError("The JSON backup could not be verified.")

    except (OSError, ValueError, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Records processed: {records_processed}")
    print(f"Target status class: {TARGET_STATUS_CLASS}xx")
    print(f"Target records: {len(selected_records)}")
    print("Status code counts:")
    for status_code, count in sorted(status_counts.items()):
        print(f"  {status_code}: {count}")
    print("Top URLs in target class:")
    for rank, (url, count) in enumerate(top_urls, start=1):
        print(f"  {rank}. {url}: {count}")
    print(f"Filtered CSV: {filtered_path}")
    print(f"Summary JSON: {summary_path}")
    print(f"Verified backup: {backup_path}")


if __name__ == "__main__":
    main()