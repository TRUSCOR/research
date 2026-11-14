"""Finish the last runs of the locked xAI design after its own USD 305 folder cap stopped it.

`drive_pf_complete_locked.py` is frozen (MANIFEST-extension.sha256) and unchanged. Its cap was set
for the author's USD 500 Azure budget; the author raised the budget to USD 700 on 2026-11-14.
This wrapper imports it, raises only the cap (to this folder's current Azure spend plus USD 12,
enough for the about 50 remaining Grok 4.20 runs), and runs its unchanged job list; runs already
made are skipped. Recorded as a deviation.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import drive_pf_complete_locked as locked  # noqa: E402
import run_pf_confirmatory as rc  # noqa: E402

rc.BUDGET["azure"] = rc.spent("azure") + 12.0
print(f"cap for this folder raised to {rc.BUDGET['azure']:.2f}", flush=True)
sys.exit(locked.main())
