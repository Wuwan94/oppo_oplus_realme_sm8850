from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = [
    ROOT / ".github/workflows/build-test.yml",
    ROOT / ".github/workflows/fastbuild_6.12.23.yml",
    ROOT / ".github/workflows/fastbuild_6.12.23_gki.yml",
    ROOT / ".github/workflows/fastbuild_6.12.23_mtk.yml",
    ROOT / ".github/workflows/fastbuild_6.12.38.yml",
    ROOT / ".github/workflows/fastbuild_6.12.58.yml",
    ROOT / ".github/workflows/fastbuild_6.12.58_mtk.yml",
    ROOT / ".github/workflows/fastbuild_6.12.69_gki.yml",
]
INPUT_ENV = "  KERNEL_SUFFIX: ${{ github.event.inputs.kernel_suffix }}"


class WorkflowInputSafetyTests(unittest.TestCase):
    def test_every_suffix_input_is_passed_through_env_and_validated_first(self):
        self.assertTrue(all(path.is_file() for path in WORKFLOWS))
        pattern = None
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertEqual(text.splitlines().count(INPUT_ENV), 1)
                self.assertEqual(text.count("${{ github.event.inputs.kernel_suffix }}"), 1)
                self.assertNotIn("${{ github.event.inputs.KERNEL_SUFFIX }}", text)
                validate = text.index("      - name: Validate kernel suffix")
                steps = text.index("    steps:", text.index("  build:"))
                self.assertGreater(validate, steps)
                raw_uses = [i for i, line in enumerate(text.splitlines())
                            if "$KERNEL_SUFFIX" in line and "github.event.inputs" not in line]
                validate_line = text[:validate].count("\n")
                self.assertTrue(raw_uses)
                self.assertGreater(min(raw_uses), validate_line)
                match = re.search(
                    r'(?m)^\s+if \[\[ -n "\$KERNEL_SUFFIX" && ! "\$KERNEL_SUFFIX" =~ (.+) \]\]; then$',
                    text)
                self.assertIsNotNone(match)
                if pattern is None:
                    pattern = match.group(1)
                self.assertEqual(match.group(1), pattern)
        self.pattern = pattern

    def suffix_is_accepted(self, value):
        script = (
            'value=$1\n'
            f'if [[ -n "$value" && ! "$value" =~ {self._pattern()} ]]; then exit 1; fi\n'
        )
        return subprocess.run(["bash", "-c", script, "test", value], check=False).returncode == 0

    def _pattern(self):
        text = WORKFLOWS[0].read_text(encoding="utf-8")
        match = re.search(
            r'(?m)^\s+if \[\[ -n "\$KERNEL_SUFFIX" && ! "\$KERNEL_SUFFIX" =~ (.+) \]\]; then$',
            text)
        return match.group(1)

    def test_allowlist_accepts_normal_versions_and_rejects_shell_or_path_syntax(self):
        for value in ("", "android16-5-ga8f88ad96df3-ab13929693-4k", "release_1.0+7"):
            with self.subTest(value=value):
                self.assertTrue(self.suffix_is_accepted(value))
        for value in (
            "$(touch /tmp/injected)",
            "v1;echo pwned",
            "../outside",
            " leading-space",
            "-leading-dash",
            "quote'\"",
            "x" * 65,
        ):
            with self.subTest(value=value):
                self.assertFalse(self.suffix_is_accepted(value))


if __name__ == "__main__":
    unittest.main()
