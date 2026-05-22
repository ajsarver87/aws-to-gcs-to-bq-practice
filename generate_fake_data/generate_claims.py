"""
Generate realistic fake healthcare claims data for S3 → GCS/BigQuery migration practice.

Produces three tables:
  - pharmacy_claims (flat)
  - medical_claim_headers (parent)
  - medical_claim_lines (child, FK to headers)

Each table is written as both CSV and Parquet to simulate a mixed-format source bucket.
"""

import random
import string
import os
from datetime import datetime, timedelta

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

random.seed(42)

OUTPUT_DIR = "fake_claims_data"
os.makedirs(f"{OUTPUT_DIR}/pharmacy", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/medical_headers", exist_ok=True)
os.makedirs(f"{OUTPUT_DIR}/medical_lines", exist_ok=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def rand_npi():
    return str(random.randint(1_000_000_000, 9_999_999_999))

def rand_ndc():
    # 5-4-2 NDC format
    return f"{random.randint(10000,99999)}-{random.randint(1000,9999)}-{random.randint(10,99)}"

def rand_member_id():
    prefix = random.choice(["MBR", "ENR", "SUB"])
    return f"{prefix}{random.randint(100_000, 999_999)}"

def rand_icd10():
    letter = random.choice("ABCDEFGHJKLMNPQRSTVWXYZ")
    num = random.randint(0, 99)
    dec = random.randint(0, 9)
    return f"{letter}{num:02d}.{dec}"

def rand_cpt():
    return str(random.randint(10000, 99999))

def rand_rev_code():
    return str(random.randint(100, 999))

def rand_pos():
    return random.choice(["11", "21", "22", "23", "31", "32", "41", "49", "51", "52", "61", "65", "71", "72", "81"])

def rand_date_in_range(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

def rand_claim_id(prefix="CLM"):
    return f"{prefix}{random.randint(1_000_000_000, 9_999_999_999)}"

# Reference data
PLAN_IDS = [f"PLAN-{random.randint(1000,9999)}" for _ in range(20)]
GROUP_IDS = [f"GRP-{random.randint(100,999)}" for _ in range(50)]
PHARMACIES = [rand_npi() for _ in range(200)]
PROVIDERS = [rand_npi() for _ in range(500)]
MEMBERS = [rand_member_id() for _ in range(10_000)]
DAW_CODES = ["0", "1", "2", "3", "4", "5", "7", "8", "9"]
CLAIM_STATUSES = ["PAID", "DENIED", "ADJUSTED", "REVERSED", "PENDING"]
MED_CLAIM_TYPES = ["PROFESSIONAL", "INSTITUTIONAL"]
MODIFIERS = ["25", "26", "59", "76", "77", "TC", "XE", "XS", "XP", "XU", ""]

START_DATE = datetime(2022, 1, 1)
END_DATE = datetime(2024, 12, 31)


# ---------------------------------------------------------------------------
# Pharmacy Claims (flat table)
# ---------------------------------------------------------------------------

def generate_pharmacy_claims(n=200_000):
    print(f"Generating {n:,} pharmacy claims...")
    rows = []
    for i in range(n):
        fill_date = rand_date_in_range(START_DATE, END_DATE)
        days_supply = random.choice([30, 60, 90, 7, 14, 1])
        qty = random.choice([30, 60, 90, 120, 1, 2, 3, 5, 10])
        ingredient_cost = round(random.uniform(1.0, 8000.0), 2)
        dispensing_fee = round(random.uniform(0.50, 15.00), 2)
        copay = round(random.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 50, 75, 100]), 2)
        plan_paid = round(max(0, ingredient_cost + dispensing_fee - copay), 2)

        rows.append({
            "claim_id": rand_claim_id("RX"),
            "member_id": random.choice(MEMBERS),
            "plan_id": random.choice(PLAN_IDS),
            "group_id": random.choice(GROUP_IDS),
            "fill_date": fill_date.strftime("%Y-%m-%d"),
            "ndc": rand_ndc(),
            "quantity_dispensed": qty,
            "days_supply": days_supply,
            "pharmacy_npi": random.choice(PHARMACIES),
            "prescriber_npi": random.choice(PROVIDERS),
            "daw_code": random.choice(DAW_CODES),
            "ingredient_cost": ingredient_cost,
            "dispensing_fee": dispensing_fee,
            "member_copay": copay,
            "plan_paid_amount": plan_paid,
            "claim_status": random.choice(CLAIM_STATUSES),
            "formulary_tier": random.choice([1, 2, 3, 4, 5, None]),
            "prior_auth_flag": random.choice(["Y", "N"]),
            "generic_indicator": random.choice(["GENERIC", "BRAND", "BRAND_GENERIC"]),
            "mail_retail_indicator": random.choice(["RETAIL", "MAIL"]),
        })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Medical Claim Headers + Lines
# ---------------------------------------------------------------------------

def generate_medical_claims(n_headers=150_000, max_lines_per_claim=8):
    print(f"Generating {n_headers:,} medical claim headers with lines...")
    headers = []
    lines = []
    line_seq = 0

    for i in range(n_headers):
        claim_id = rand_claim_id("MED")
        member_id = random.choice(MEMBERS)
        claim_type = random.choice(MED_CLAIM_TYPES)
        service_from = rand_date_in_range(START_DATE, END_DATE)
        service_to = service_from + timedelta(days=random.choice([0, 0, 0, 1, 2, 3, 5, 7, 14, 30]))
        received_date = service_to + timedelta(days=random.randint(1, 60))

        n_lines = random.randint(1, max_lines_per_claim)
        total_charged = 0
        total_allowed = 0
        total_paid = 0

        primary_dx = rand_icd10()
        dx_codes = [primary_dx] + [rand_icd10() for _ in range(random.randint(0, 3))]

        for line_num in range(1, n_lines + 1):
            line_seq += 1
            charged = round(random.uniform(25.0, 15000.0), 2)
            allowed = round(charged * random.uniform(0.3, 1.0), 2)
            copay = round(random.choice([0, 20, 25, 30, 40, 50, 75, 100, 150, 250]), 2)
            coinsurance = round(allowed * random.choice([0, 0, 0, 0.1, 0.2, 0.3]), 2)
            deductible = round(random.choice([0, 0, 0, 0, 50, 100, 250, 500]), 2)
            paid = round(max(0, allowed - copay - coinsurance - deductible), 2)

            total_charged += charged
            total_allowed += allowed
            total_paid += paid

            line_service_from = service_from + timedelta(days=random.randint(0, max(0, (service_to - service_from).days)))

            lines.append({
                "claim_line_id": f"{claim_id}-{line_num:03d}",
                "claim_id": claim_id,
                "line_number": line_num,
                "service_from_date": line_service_from.strftime("%Y-%m-%d"),
                "service_to_date": line_service_from.strftime("%Y-%m-%d"),
                "cpt_code": rand_cpt(),
                "modifier_1": random.choice(MODIFIERS),
                "modifier_2": random.choice(["", "", "", random.choice(MODIFIERS)]),
                "revenue_code": rand_rev_code() if claim_type == "INSTITUTIONAL" else "",
                "place_of_service": rand_pos() if claim_type == "PROFESSIONAL" else "",
                "rendering_provider_npi": random.choice(PROVIDERS),
                "diagnosis_pointer": "1" if line_num <= len(dx_codes) else str(random.randint(1, len(dx_codes))),
                "units": random.choice([1, 1, 1, 2, 3, 4, 5, 10, 15, 20]),
                "charged_amount": charged,
                "allowed_amount": allowed,
                "member_copay": copay,
                "coinsurance": coinsurance,
                "deductible": deductible,
                "plan_paid_amount": paid,
                "line_status": random.choice(CLAIM_STATUSES),
            })

        headers.append({
            "claim_id": claim_id,
            "member_id": member_id,
            "plan_id": random.choice(PLAN_IDS),
            "group_id": random.choice(GROUP_IDS),
            "claim_type": claim_type,
            "service_from_date": service_from.strftime("%Y-%m-%d"),
            "service_to_date": service_to.strftime("%Y-%m-%d"),
            "claim_received_date": received_date.strftime("%Y-%m-%d"),
            "billing_provider_npi": random.choice(PROVIDERS),
            "facility_npi": random.choice(PROVIDERS) if claim_type == "INSTITUTIONAL" else "",
            "primary_diagnosis": primary_dx,
            "diagnosis_code_2": dx_codes[1] if len(dx_codes) > 1 else "",
            "diagnosis_code_3": dx_codes[2] if len(dx_codes) > 2 else "",
            "diagnosis_code_4": dx_codes[3] if len(dx_codes) > 3 else "",
            "total_charged_amount": round(total_charged, 2),
            "total_allowed_amount": round(total_allowed, 2),
            "total_paid_amount": round(total_paid, 2),
            "claim_status": random.choice(CLAIM_STATUSES),
            "drg_code": str(random.randint(1, 999)).zfill(3) if claim_type == "INSTITUTIONAL" else "",
        })

    return pd.DataFrame(headers), pd.DataFrame(lines)


# ---------------------------------------------------------------------------
# Write to disk
# ---------------------------------------------------------------------------

def write_table(df, name, subdir):
    csv_path = f"{OUTPUT_DIR}/{subdir}/{name}.csv"
    parquet_path = f"{OUTPUT_DIR}/{subdir}/{name}.parquet"

    df.to_csv(csv_path, index=False)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, parquet_path)

    csv_mb = os.path.getsize(csv_path) / (1024 * 1024)
    pq_mb = os.path.getsize(parquet_path) / (1024 * 1024)
    print(f"  {name}: CSV={csv_mb:.1f}MB, Parquet={pq_mb:.1f}MB, rows={len(df):,}")


if __name__ == "__main__":
    print("=" * 60)
    print("Healthcare Claims Data Generator")
    print("=" * 60)

    # Generate pharmacy claims — write as CSV (simulating a CSV-only source)
    rx_df = generate_pharmacy_claims(200_000)
    write_table(rx_df, "pharmacy_claims_2022_2024", "pharmacy")

    # Generate medical claims — write headers as Parquet, lines as CSV
    # (simulating the real-world mix where different systems export differently)
    headers_df, lines_df = generate_medical_claims(150_000)
    write_table(headers_df, "medical_claim_headers_2022_2024", "medical_headers")
    write_table(lines_df, "medical_claim_lines_2022_2024", "medical_lines")

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Pharmacy claims:       {len(rx_df):>10,} rows")
    print(f"  Medical claim headers: {len(headers_df):>10,} rows")
    print(f"  Medical claim lines:   {len(lines_df):>10,} rows")
    print(f"  Output directory:      {OUTPUT_DIR}/")
    print()
    print("Directory structure (simulates S3 bucket layout):")
    print(f"  {OUTPUT_DIR}/")
    print(f"    pharmacy/")
    print(f"      pharmacy_claims_2022_2024.csv")
    print(f"      pharmacy_claims_2022_2024.parquet")
    print(f"    medical_headers/")
    print(f"      medical_claim_headers_2022_2024.csv")
    print(f"      medical_claim_headers_2022_2024.parquet")
    print(f"    medical_lines/")
    print(f"      medical_claim_lines_2022_2024.csv")
    print(f"      medical_claim_lines_2022_2024.parquet")
    print()
    print("Next steps:")
    print("  1. Upload to S3:  aws s3 sync fake_claims_data/ s3://your-bucket/claims/")
    print("  2. Transfer to GCS via Storage Transfer Service")
    print("  3. Load into BigQuery and validate")
    print("  4. Wire up dbt sources")