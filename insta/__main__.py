# SPDX-FileCopyrightText: 2026 Peter Bittner <django@bittner.it>
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point for ``python -m insta``."""

import sys

from insta.cli import main

sys.exit(main())
