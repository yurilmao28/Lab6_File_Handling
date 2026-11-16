import csv
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

LAST_NAME = "Manrique"
STUDENT_ID = "TUPM-26-1137"
SEED_DIGIT = int(STUDENT_ID[-1])
TARGET_YEAR = 2015 + SEED_DIGIT

REQUIRED_FIELDS = ("Year", "Attack Type", "Financial Loss (in Million $)")


def clean_value(value):
    return (value or "").strip()


def normalize_header(name):
    text = clean_value(name).lower()
    text = "".join(ch if ch.isalnum() else "_" for ch in text)
    return text.strip("_")


def parse_float(value, field_name, row_number):
    text = clean_value(value)
    if not text:
        raise ValueError(f"{field_name} is blank on row {row_number}.")
    try:
        return float(text.replace(",", ""))
    except ValueError as error:
        raise ValueError(
            f"Invalid numeric value for {field_name} on row {row_number}: {value!r}."
        ) from error


def analyze_incidents(input_path: Path):
    """Read the cybersecurity dataset and return the target-year incidents."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Input CSV was not found: {input_path}")

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("The input CSV is empty or has no header row.")

        normalized_headers = {normalize_header(name): name for name in reader.fieldnames}
        missing_fields = [
            field for field in REQUIRED_FIELDS if normalize_header(field) not in normalized_headers
        ]
        if missing_fields:
            raise ValueError(
                "The CSV is missing required columns: " + ", ".join(missing_fields)
            )

        target_records = []
        total_records = 0
        for row_number, row in enumerate(reader, start=2):
            total_records += 1
            year_value = clean_value(row.get(normalized_headers[normalize_header("Year")]))
            attack_type = clean_value(row.get(normalized_headers[normalize_header("Attack Type")]))
            loss_value = row.get(normalized_headers[normalize_header("Financial Loss (in Million $)")])

            if not year_value or not attack_type:
                raise ValueError(
                    f"Malformed or incomplete incident record on row {row_number}: missing year or attack type."
                )

            try:
                year = int(year_value)
            except ValueError as error:
                raise ValueError(
                    f"Invalid year value on row {row_number}: {year_value!r}."
                ) from error

            financial_loss = parse_float(loss_value, "Financial Loss (in Million $)", row_number)

            if year == TARGET_YEAR:
                record = dict(row)
                record["financial_loss"] = financial_loss
                target_records.append(record)

        if not target_records:
            raise ValueError(f"No incidents were found for the target year {TARGET_YEAR}.")

    attack_counts = Counter(record["Attack Type"] for record in target_records)
    total_loss = sum(record["financial_loss"] for record in target_records)
    average_loss = total_loss / len(target_records)

    ranked_records = sorted(
        range(len(target_records)),
        key=lambda index: (-target_records[index]["financial_loss"], index),
    )
    top_incidents = [target_records[index] for index in ranked_records[:5]]

    return {
        "total_records": total_records,
        "target_year": TARGET_YEAR,
        "records_in_target_year": len(target_records),
        "attack_type_counts": dict(sorted(attack_counts.items(), key=lambda item: (-item[1], item[0]))),
        "total_financial_loss": total_loss,
        "average_financial_loss": average_loss,
        "selected_records": target_records,
        "top_incidents": top_incidents,
        "fieldnames": reader.fieldnames,
    }


def write_filtered_csv(records, fieldnames, output_path):
    with output_path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field, "") for field in fieldnames}
            writer.writerow(row)


def generate_report(summary, filtered_path, summary_json_path, backup_path):
    lines = [
        "Cybersecurity Incident Report",
        "=" * 28,
        f"Target year: {summary['target_year']}",
        f"Total records in dataset: {summary['total_records']}",
        f"Incidents in target year: {summary['records_in_target_year']}",
        "",
        "Incident counts by attack type:",
    ]

    for attack_type, count in summary["attack_type_counts"].items():
        lines.append(f"- {attack_type}: {count}")

    lines.extend(
        [
            "",
            "Financial loss summary:",
            f"Total financial loss: {summary['total_financial_loss']:.2f} million USD",
            f"Average financial loss: {summary['average_financial_loss']:.2f} million USD",
            "",
            "Top five costliest incidents:",
        ]
    )

    for rank, incident in enumerate(summary["top_incidents"], start=1):
        lines.append(
            f"{rank}. {incident['Country']} | {incident['Attack Type']} | "
            f"{incident['financial_loss']:.2f} million USD | "
            f"{incident['Target Industry']} | users: {incident['Number of Affected Users']}"
        )

    lines.extend(
        [
            "",
            "Output file information:",
            f"Filtered CSV file: {filtered_path}",
            f"JSON summary file: {summary_json_path}",
            f"Verified backup: {backup_path}",
        ]
    )

    return "\n".join(lines) + "\n"


def main():
    workspace = Path(__file__).resolve().parent
    if len(sys.argv) > 2:
        print(f"Usage: {Path(sys.argv[0]).name} [path-to-cybersecurity.csv]")
        raise SystemExit(2)

    default_input = workspace / "data" / "Global_Cybersecurity_Threats_2015-2024.csv"
    if len(sys.argv) == 2:
        input_path = Path(sys.argv[1]).expanduser().resolve(strict=False)
    elif default_input.is_file():
        input_path = default_input
    else:
        print(f"Default dataset not found: {default_input}")
        entered_path = input("Enter the full path to the cyber incident CSV (or press Enter to cancel): ")
        if not entered_path.strip():
            print("No CSV selected. Download the dataset and run this program again.")
            raise SystemExit(1)
        input_path = Path(entered_path.strip().strip('"')).expanduser().resolve(strict=False)

    try:
        dataset = analyze_incidents(input_path)

        output_dir = workspace / "output"
        backup_dir = workspace / "backup"
        output_dir.mkdir(exist_ok=True)
        backup_dir.mkdir(exist_ok=True)

        file_prefix = f"{LAST_NAME}_{STUDENT_ID}"
        filtered_csv_path = output_dir / f"{file_prefix}_filtered_incidents.csv"
        summary_json_path = output_dir / f"{file_prefix}_incident_summary.json"
        report_path = output_dir / f"{file_prefix}_incident_report.txt"
        backup_json_path = backup_dir / summary_json_path.name

        write_filtered_csv(dataset["selected_records"], dataset["fieldnames"], filtered_csv_path)

        summary = {
            "last_name": LAST_NAME,
            "student_id": STUDENT_ID,
            "seed_digit": SEED_DIGIT,
            "target_year": dataset["target_year"],
            "total_records": dataset["total_records"],
            "records_in_target_year": dataset["records_in_target_year"],
            "attack_type_counts": dataset["attack_type_counts"],
            "total_financial_loss_usd_million": round(dataset["total_financial_loss"], 2),
            "average_financial_loss_usd_million": round(dataset["average_financial_loss"], 4),
            "top_five_costliest_incidents": [
                {
                    "country": incident.get("Country", ""),
                    "year": incident.get("Year", ""),
                    "attack_type": incident.get("Attack Type", ""),
                    "target_industry": incident.get("Target Industry", ""),
                    "financial_loss_in_million_usd": round(incident["financial_loss"], 2),
                    "affected_users": incident.get("Number of Affected Users", ""),
                    "attack_source": incident.get("Attack Source", ""),
                    "incident_resolution_time_hours": incident.get("Incident Resolution Time (in Hours)", ""),
                }
                for incident in dataset["top_incidents"]
            ],
        }

        with summary_json_path.open("w", encoding="utf-8") as output_file:
            json.dump(summary, output_file, indent=4)
            output_file.write("\n")

        shutil.copy2(summary_json_path, backup_json_path)
        if not backup_json_path.is_file() or backup_json_path.read_bytes() != summary_json_path.read_bytes():
            raise OSError("The JSON backup could not be verified.")

        report_text = generate_report(dataset, filtered_csv_path, summary_json_path, backup_json_path)
        report_path.write_text(report_text, encoding="utf-8")

    except (OSError, ValueError, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Target year: {TARGET_YEAR}")
    print(f"Incidents in target year: {dataset['records_in_target_year']}")
    print("Incident counts by attack type:")
    for attack_type, count in dataset["attack_type_counts"].items():
        print(f"  {attack_type}: {count}")
    print(f"Total financial loss: {dataset['total_financial_loss']:.2f} million USD")
    print(f"Average financial loss: {dataset['average_financial_loss']:.2f} million USD")
    print("Top five costliest incidents:")
    for rank, incident in enumerate(dataset["top_incidents"], start=1):
        print(
            f"  {rank}. {incident['Country']} | {incident['Attack Type']} | "
            f"{incident['financial_loss']:.2f} million USD"
        )
    print(f"Filtered CSV file: {filtered_csv_path}")
    print(f"JSON summary file: {summary_json_path}")
    print(f"Verified backup: {backup_json_path}")
    print(f"Text report: {report_path}")


if __name__ == "__main__":
    main()
