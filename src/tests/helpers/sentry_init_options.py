#!/usr/bin/env python
#####################################################################
# Project:       Juniper
# Sub-Project:   JuniperCanopy
# File Name:     sentry_init_options.py
# Author:        Paul Calnon
# Version:       0.1.0
# Date:          2026-11-26
# Last Modified: 2026-11-26
# License:       MIT License
# Copyright:     Copyright (c) 2024-2026 Paul Calnon
# Description:   Which sentry-sdk option set the installed
#                juniper-observability's configure_sentry passes to
#                sentry_sdk.init, for the Sentry init tests.
#####################################################################
"""Which option set the installed ``configure_sentry`` hands ``sentry_sdk.init``.

juniper-observability 0.4.3 passes sentry-sdk 2.x's options on a 2.x SDK and 3.x's on a 3.x SDK, choosing by the
major of ``sentry_sdk.VERSION``. 0.4.2 and earlier pass 2.x's options on every SDK. sentry-sdk 3.0.0 removed
``send_default_pii``, ``include_local_variables``, ``enable_logs`` and ``before_send_transaction`` (an unknown
option raises ``TypeError``), so on the 3.x path:

- ``data_collection["user_info"]`` carries what ``send_default_pii`` did: the user and the client's address;
- Sentry Logs come from the ``LoggingIntegration`` in ``integrations``, since 3.x has no ``enable_logs``.

The tests that mock ``sentry_sdk.init`` patch the real module, so they take the path of the installed pair. The
version is read from the code (``juniper_observability.__version__``) rather than from its installed metadata,
because an editable install's metadata can name an older release than the code it imports.

``sentry_sdk`` is imported when the question is asked, not at import: sentry-sdk is canopy's optional
``observability`` extra, and the modules importing this one hold many tests that never touch Sentry.

A pre-release of 0.4.3 (``0.4.3rc1``, ``0.4.3.dev0``) counts as 0.4.3. On a sentry-sdk major other than 2 or 3,
0.4.3 initialises nothing and these tests fail, which is meant: canopy's sentry-sdk range is to be capped below 4.

The answer is derived from the two versions, not from the library's own dispatch (``_sentry_sdk_major`` in
``juniper_observability.sentry``), so that a dispatch bug in the library still fails these tests. The cost: the
unreleased juniper-ml commits between ``b54f961b`` (juniper-ml#2647) and ``b9442e3c`` (#2666) carry the 3.x code
labelled 0.4.2, and an editable install of one of them reads as 2.x here.
"""

import juniper_observability
from packaging.version import Version

#: The first juniper-observability release whose ``configure_sentry`` passes sentry-sdk 3.x's options on 3.x.
FIRST_RELEASE_WITH_3X_OPTIONS = (0, 4, 3)


def takes_sentry_3x_options() -> bool:
    """True when the installed ``configure_sentry`` passes sentry-sdk 3.x's options to ``sentry_sdk.init``."""
    import sentry_sdk

    return Version(juniper_observability.__version__).release >= FIRST_RELEASE_WITH_3X_OPTIONS and Version(sentry_sdk.VERSION).major == 3
