import os
import re
import shutil


PRIMARY_EIP_PATTERN = re.compile(
    r"Exception(?: code:)?\s+C[0-9A-Fa-f]{7}\s+at\s+([0-9A-Fa-f]{8})"
)
FALLBACK_EIP_PATTERN = re.compile(r"ExceptionReturnAddress\s*=\s*([0-9A-Fa-f]{8})")


def should_process_file(filename):
    lower_name = filename.lower()
    return lower_name.endswith(".log") or lower_name == "except.txt"


def read_text_file(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read()


def extract_eip_with_pattern(content, pattern):
    match = pattern.search(content)
    if match:
        return match.group(1).upper()
    return None


def extract_eip_from_file(file_path, pattern):
    if not should_process_file(os.path.basename(file_path)):
        return None
    content = read_text_file(file_path)
    return extract_eip_with_pattern(content, pattern)


def classify_file(file_path):
    eip = extract_eip_from_file(file_path, PRIMARY_EIP_PATTERN)
    if eip:
        return "EIP", eip

    fallback_address = extract_eip_from_file(file_path, FALLBACK_EIP_PATTERN)
    if fallback_address:
        return "NOEIP", fallback_address

    return "NOEIP", None


def iter_candidate_files(directory_path):
    for current_root, _, filenames in os.walk(directory_path):
        for filename in sorted(filenames):
            if should_process_file(filename):
                yield os.path.join(current_root, filename)


def classify_directory(directory_path):
    candidate_files = list(iter_candidate_files(directory_path))

    for file_path in candidate_files:
        eip = extract_eip_from_file(file_path, PRIMARY_EIP_PATTERN)
        if eip:
            return "EIP", eip

    for file_path in candidate_files:
        fallback_address = extract_eip_from_file(file_path, FALLBACK_EIP_PATTERN)
        if fallback_address:
            return "NOEIP", fallback_address

    return "NOEIP", None


def ensure_destination_root(collection_dir, archive_group, signature):
    if archive_group == "EIP":
        destination_root = os.path.join(collection_dir, "EIP", signature)
    else:
        destination_root = os.path.join(collection_dir, "NOEIP")
        if signature:
            destination_root = os.path.join(destination_root, signature)
        else:
            destination_root = os.path.join(destination_root, "UNKNOWN")

    os.makedirs(destination_root, exist_ok=True)
    return destination_root


def archive_file(file_path, collection_dir, archive_group, signature):
    destination_root = ensure_destination_root(collection_dir, archive_group, signature)
    destination_path = os.path.join(destination_root, os.path.basename(file_path))
    shutil.copy2(file_path, destination_path)
    return destination_path


def archive_directory(directory_path, collection_dir, archive_group, signature):
    destination_root = ensure_destination_root(collection_dir, archive_group, signature)
    destination_path = os.path.join(destination_root, os.path.basename(directory_path))
    shutil.copytree(directory_path, destination_path, dirs_exist_ok=True)
    return destination_path


def process_file_entry(file_path, collection_dir):
    print(f"Processing file entry: {file_path}")

    archive_group, signature = classify_file(file_path)
    destination_path = archive_file(file_path, collection_dir, archive_group, signature)

    if archive_group == "EIP":
        print(f"[-] Extracted EIP: {signature}")
    else:
        if signature:
            print(f"[-] Fallback ExceptionReturnAddress: {signature}")
        else:
            print("[x] No EIP found, archived to NOEIP")

    print(f"[-] Copied file to: {destination_path}")
    return archive_group, signature


def process_directory_entry(directory_path, collection_dir):
    print(f"Processing directory entry: {directory_path}")

    archive_group, signature = classify_directory(directory_path)
    destination_path = archive_directory(directory_path, collection_dir, archive_group, signature)

    if archive_group == "EIP":
        print(f"[-] Extracted EIP: {signature}")
    else:
        if signature:
            print(f"[-] Fallback ExceptionReturnAddress: {signature}")
        else:
            print("[x] No EIP found, archived to NOEIP")

    print(f"[-] Copied directory to: {destination_path}")
    return archive_group, signature


def update_grouped_results(grouped_results, signature):
    grouped_results[signature] = grouped_results.get(signature, 0) + 1


def process_top_level_entry(entry_path, entry_name, collection_dir, grouped_results):
    if os.path.isfile(entry_path):
        if not should_process_file(entry_name):
            return 0, 0, 0, 0

        archive_group, signature = process_file_entry(entry_path, collection_dir)
        if archive_group == "NOEIP":
            return 1, 0, 0, 1

        update_grouped_results(grouped_results, signature)
        return 1, 0, 1, 0

    if os.path.isdir(entry_path):
        archive_group, signature = process_directory_entry(entry_path, collection_dir)
        if archive_group == "NOEIP":
            return 0, 1, 0, 1

        update_grouped_results(grouped_results, signature)
        return 0, 1, 1, 0

    return 0, 0, 0, 0


def main():
    target_dir = input("Enter the debug directory path: ").strip().strip('"')
    collection_dir = input("Enter the collection directory path: ").strip().strip('"')

    if not os.path.isdir(target_dir):
        print(f"[!] Target directory does not exist: {target_dir}")
        return

    target_dir = os.path.abspath(target_dir)
    collection_dir = os.path.abspath(collection_dir)

    if target_dir == collection_dir:
        print("[!] Target directory and collection directory cannot be the same.")
        return

    os.makedirs(os.path.join(collection_dir, "EIP"), exist_ok=True)
    os.makedirs(os.path.join(collection_dir, "NOEIP"), exist_ok=True)

    processed_files = 0
    processed_directories = 0
    eip_count = 0
    noeip_count = 0
    grouped_results = {}

    for entry_name in sorted(os.listdir(target_dir)):
        entry_path = os.path.join(target_dir, entry_name)
        file_delta, dir_delta, eip_delta, noeip_delta = process_top_level_entry(
            entry_path,
            entry_name,
            collection_dir,
            grouped_results,
        )
        processed_files += file_delta
        processed_directories += dir_delta
        eip_count += eip_delta
        noeip_count += noeip_delta

    print("\nSummary")
    print(f"[-] Processed file entries: {processed_files}")
    print(f"[-] Processed directory entries: {processed_directories}")
    print(f"[-] Archived under EIP: {eip_count}")
    print(f"[-] Archived under NOEIP: {noeip_count}")

    if not grouped_results:
        print("[x] No EIP signatures were collected.")
        return

    print("[-] Grouped by EIP:")
    for eip in sorted(grouped_results):
        print(f"    {eip}: {grouped_results[eip]}")


if __name__ == "__main__":
    main()
