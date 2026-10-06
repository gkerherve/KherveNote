import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile

# Never touch the real recovery folder of the user's recordings.
os.environ.setdefault("KHERVENOTE_RECOVERY_DIR", tempfile.mkdtemp(prefix="knote-recovery-"))
