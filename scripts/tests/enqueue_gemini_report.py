#!/usr/bin/env python3
"""Enfile un rapport Gemini (entreprise_id argv[1])."""
import sys

from tasks.gemini_full_report_tasks import analyze_entreprise_gemini_full_report_task


def main() -> None:
    eid = int(sys.argv[1])
    task = analyze_entreprise_gemini_full_report_task.apply_async(
        kwargs={"entreprise_id": eid, "ensure_screenshots": True},
        queue="screenshot",
    )
    print("task_id:", task.id)


if __name__ == "__main__":
    main()
