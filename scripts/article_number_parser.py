from pathlib import Path
import re

STEP_EXTENSIONS = {".step", ".stp"}

def extract_article_number(name: str):
    """
    Extracts the Würth article number from a filename or folder name.

    Expected examples:
        Wuerth_031760_DIN_934.step
        Wuerth_006410_25_DIN_961.step
    """

    match = re.search(
        r"(?:Wuerth|Würth)[_-](\d{5,10})",
        name,
        re.IGNORECASE
    )

    return match.group(1) if match else None


def find_step_files(root_folder):
    root = Path(root_folder)
    results = []

    for path in root.rglob("*"):
        if path.suffix.lower() not in STEP_EXTENSIONS:
            continue

        article_number = extract_article_number(path.name)

        if article_number is None:
            for parent in path.parents:
                if parent == root.parent:
                    break

                article_number = extract_article_number(parent.name)

                if article_number:
                    break

        results.append({
            "path": path,
            "relative_path": str(path.relative_to(root)),
            "filename": path.name,
            "article_number": article_number
        })

    return results


if __name__ == "__main__":
    ROOT = "../"

    for item in find_step_files(ROOT):
        print(
            item["article_number"],
            item["relative_path"]
        )