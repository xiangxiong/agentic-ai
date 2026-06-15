from __future__ import annotations

from typing import Any

import pandas as pd


def print_section(title: str, content: Any) -> None:
    line = "=" * 60
    print(f"\n{line}\n{title}\n{line}")
    if isinstance(content, pd.DataFrame):
        if content.empty:
            print("(empty result)")
        else:
            print(content.to_string(index=False))
    else:
        print(content)
