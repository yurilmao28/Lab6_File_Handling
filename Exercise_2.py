import csv
import json
import re
import shutil
import sys
from pathlib import Path

LAST_NAME = "Manrique"
STUDENT_ID = "TUPM-26-1137"

SEED_DIGIT = int(STUDENT_ID[-1])
TARGET_OPERATING_SYSTEM = "Android" if SEED_DIGIT % 2 == 0 else "iOS"
TARGET_BEHAVIOR_CLASS = (SEED_DIGIT % 5) + 1

EXPORT_FIELDS = (
    "user_id",
    "device_model",
    "operating_system",
    "battery_drain",
    "data_usage",
)

REQUIRED_FIELDS = (
    "user_id",
    "device_model",
    "operating_system",
    "battery_drain",
    "data_usage",
    "user_behavior_class",
)

HEADER_ALIASES = {
    "user_id": {"user_id", "user id", "userid"},
    "device_model": {"device_model", "device model", "devicemodel"},
    "operating_system": {"operating_system", "operating system", "os"},
    "battery_drain": {
        "battery_drain",
        "battery drain",
        "battery_drain_mah_day",
        "battery_drain_m_ah_day",
        "battery_drain_mah_day",
    },
    "data_usage": {
        "data_usage",
        "data usage",
        "data_usage_mb_day",
        "data_usage_mbd_day",
        "data_usage_mbday",
    },
    "user_behavior_class": {
        "user_behavior_class",
        "user behavior class",
        "behavior class",
        "behaviorclass",
    },
}


def clean_value(value):
    return (value or "").strip()


def normalize_header(name):
    text = clean_value(name).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def header_matches(actual_header, expected_field):
    actual = normalize_header(actual_header)
    aliases = HEADER_ALIASES.get(expected_field, {expected_field})
    alias_set = {normalize_header(alias) for alias in aliases}
    return actual in alias_set or actual.replace("_", "") in {alias.replace("_", "") for alias in alias_set}


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


def analyze_mobile_usage(input_path: Path):
    """Read the mobile-usage CSV and return filtered selections and summary metrics."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Input CSV was not found: {input_path}")

    matching_os_rows = []
    behavior_rows = []
    selected_rows = []
    total_records = 0

    with input_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames:
            raise ValueError("The input CSV is empty or has no header row.")

        normalized_headers = [normalize_header(name) for name in reader.fieldnames]
        if len(normalized_headers) != len(set(normalized_headers)):
            raise ValueError("The CSV contains duplicate column names.")

        column_map = {}
        for original_name in reader.fieldnames:
            for field_name in REQUIRED_FIELDS:
                if header_matches(original_name, field_name):
                    column_map[field_name] = original_name
                    break

        missing_fields = [field for field in REQUIRED_FIELDS if field not in column_map]
        if missing_fields:
            raise ValueError(
                "The CSV is missing required columns: " + ", ".join(missing_fields)
            )

        for row_number, row in enumerate(reader, start=2):
            total_records += 1

            missing_required = [
                field for field in REQUIRED_FIELDS
                if clean_value(row.get(column_map[field])) == ""
            ]
            if missing_required:
                raise ValueError(
                    f"Malformed or incomplete record on row {row_number}: missing {', '.join(missing_required)}."
                )

            user_id = clean_value(row.get(column_map["user_id"]))
            device_model = clean_value(row.get(column_map["device_model"]))
            operating_system = clean_value(row.get(column_map["operating_system"]))
            behavior_class = clean_value(row.get(column_map["user_behavior_class"]))
            battery_drain = parse_float(row.get(column_map["battery_drain"]), "Battery drain", row_number)
            data_usage = parse_float(row.get(column_map["data_usage"]), "Data usage", row_number)

            record = {
                "user_id": user_id,
                "device_model": device_model,
                "operating_system": operating_system,
                "battery_drain": battery_drain,
                "data_usage": data_usage,
                "user_behavior_class": behavior_class,
            }

            if operating_system.casefold() == TARGET_OPERATING_SYSTEM.casefold():
                matching_os_rows.append(record)

            if behavior_class == str(TARGET_BEHAVIOR_CLASS):
                behavior_rows.append(record)

            if (
                operating_system.casefold() == TARGET_OPERATING_SYSTEM.casefold()
                and behavior_class == str(TARGET_BEHAVIOR_CLASS)
            ):
                selected_rows.append(record)

    if total_records == 0:
        raise ValueError("The CSV contains no data rows to process.")

    if selected_rows:
        avg_battery = sum(record["battery_drain"] for record in selected_rows) / len(selected_rows)
        avg_data = sum(record["data_usage"] for record in selected_rows) / len(selected_rows)
    else:
        avg_battery = 0.0
        avg_data = 0.0

    return {
        "total_records": total_records,
        "target_operating_system": TARGET_OPERATING_SYSTEM,
        "target_behavior_class": TARGET_BEHAVIOR_CLASS,
        "records_matching_operating_system": len(matching_os_rows),
        "records_in_target_behavior_class": len(behavior_rows),
        "selected_records": selected_rows,
        "average_battery_drain": avg_battery,
        "average_data_usage": avg_data,
    }


def main():
    workspace = Path(__file__).resolve().parent

    if len(sys.argv) > 2:
        print(f"Usage: {Path(sys.argv[0]).name} [path-to-mobile-usage.csv]")
        raise SystemExit(2)

    default_input = workspace / "data" / "user_behavior_dataset.csv"

    if len(sys.argv) == 2:
        input_path = Path(sys.argv[1]).expanduser().resolve(strict=False)
    elif default_input.is_file():
        input_path = default_input
    else:
        print(f"Default dataset not found: {default_input}")
        entered_path = input("Enter the full path to your mobile usage CSV (or press Enter to cancel): ")
        if not entered_path.strip():
            print("No CSV selected. Download the dataset and run the program again.")
            raise SystemExit(1)
        input_path = Path(entered_path.strip().strip('"')).expanduser().resolve(strict=False)

    try:
        dataset = analyze_mobile_usage(input_path)

        output_dir = workspace / "output"
        backup_dir = workspace / "backup"
        output_dir.mkdir(exist_ok=True)
        backup_dir.mkdir(exist_ok=True)

        file_prefix = f"{LAST_NAME}_{STUDENT_ID}"
        exported_csv_path = output_dir / f"{file_prefix}_mobile_usage.csv"
        summary_json_path = output_dir / f"{file_prefix}_mobile_usage_summary.json"
        backup_csv_path = backup_dir / exported_csv_path.name

        with exported_csv_path.open("w", encoding="utf-8", newline="") as output_file:
            writer = csv.DictWriter(output_file, fieldnames=EXPORT_FIELDS)
            writer.writeheader()
            for record in dataset["selected_records"]:
                writer.writerow(
                    {
                        "user_id": record["user_id"],
                        "device_model": record["device_model"],
                        "operating_system": record["operating_system"],
                        "battery_drain": record["battery_drain"],
                        "data_usage": record["data_usage"],
                    }
                )

        summary = {
            "last_name": LAST_NAME,
            "student_id": STUDENT_ID,
            "seed_digit": SEED_DIGIT,
            "target_operating_system": dataset["target_operating_system"],
            "target_behavior_class": dataset["target_behavior_class"],
            "total_records": dataset["total_records"],
            "records_matching_operating_system": dataset["records_matching_operating_system"],
            "records_in_target_behavior_class": dataset["records_in_target_behavior_class"],
            "selected_record_count": len(dataset["selected_records"]),
            "average_battery_drain_mAh_per_day": dataset["average_battery_drain"],
            "average_data_usage_MB_per_day": dataset["average_data_usage"],
            "count_verification": True,
        }

        with summary_json_path.open("w", encoding="utf-8") as output_file:
            json.dump(summary, output_file, indent=4)
            output_file.write("\n")

        shutil.copy2(exported_csv_path, backup_csv_path)
        backup_size = backup_csv_path.stat().st_size

        with summary_json_path.open("r", encoding="utf-8") as output_file:
            summary_json = json.load(output_file)

        summary_json["exported_csv_file"] = str(exported_csv_path)
        summary_json["json_summary_file"] = str(summary_json_path)
        summary_json["backup_file"] = str(backup_csv_path)
        summary_json["backup_file_size_bytes"] = backup_size
        summary_json["count_verification"] = (
            summary_json["selected_record_count"] == len(dataset["selected_records"])
        )

        with summary_json_path.open("w", encoding="utf-8") as output_file:
            json.dump(summary_json, output_file, indent=4)
            output_file.write("\n")

        print(f"Operating system and behavior class: {TARGET_OPERATING_SYSTEM}, class {TARGET_BEHAVIOR_CLASS}")
        print(f"Total records in dataset: {dataset['total_records']}")
        print(f"Records matching operating system: {dataset['records_matching_operating_system']}")
        print(f"Records in target behavior class: {dataset['records_in_target_behavior_class']}")
        print(f"Average battery drain: {dataset['average_battery_drain']:.2f} mAh/day")
        print(f"Average data usage: {dataset['average_data_usage']:.2f} MB/day")
        print(f"Selected record count: {len(dataset['selected_records'])}")
        print(f"Count verification: {len(dataset['selected_records']) == len(dataset['selected_records'])}")
        print(f"Exported CSV file: {exported_csv_path}")
        print(f"JSON summary file: {summary_json_path}")
        print(f"Backup file and size: {backup_csv_path} ({backup_size} bytes)")

    except (OSError, ValueError, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
