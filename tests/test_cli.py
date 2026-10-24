import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import path as cli


class CLIPrivacyOptions(unittest.TestCase):
    def test_privacy_flags_override_configuration(self):
        captured = {}

        def load_config(config, overrides):
            captured["overrides"] = overrides

        with mock.patch.object(sys, "argv", [
            "path", "trace", "sample", "--no-breaches", "--no-profile-probes", "--no-profile-pages",
        ]), mock.patch.object(cli, "load_config", side_effect=load_config), \
             mock.patch.object(cli, "print_banner"), mock.patch.object(cli, "run_trace", return_value=object()), \
             mock.patch.object(cli, "_finish", return_value=0):
            self.assertEqual(cli.main(), 0)

        self.assertEqual(captured["overrides"], {
            "profiles": {"enabled": False},
            "trace": {"scan_social_profiles": False},
            "breaches": {"enabled": False},
        })

    def test_breaches_flag_remains_an_explicit_opt_in(self):
        captured = {}

        def load_config(config, overrides):
            captured["overrides"] = overrides

        with mock.patch.object(sys, "argv", ["path", "trace", "sample", "--breaches"]), \
             mock.patch.object(cli, "load_config", side_effect=load_config), \
             mock.patch.object(cli, "print_banner"), mock.patch.object(cli, "run_trace", return_value=object()), \
             mock.patch.object(cli, "_finish", return_value=0):
            self.assertEqual(cli.main(), 0)

        self.assertEqual(captured["overrides"], {"breaches": {"enabled": True}})


if __name__ == "__main__":
    unittest.main()
