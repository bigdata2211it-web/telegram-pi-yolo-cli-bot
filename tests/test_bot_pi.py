import os
import unittest
from pathlib import Path
from unittest.mock import patch

import bot_pi


class PiCommandTests(unittest.TestCase):
    def test_default_command_runs_pi_with_json_mode_and_project_prompt(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                bot_pi.command_config(),
                [
                    "pi",
                    "--mode",
                    "json",
                ],
            )

    def test_command_with_dir_removes_legacy_dir_option(self):
        cmd = ["pi", "--mode", "json", "--dir", "/old", "--model", "openai/gpt-5"]

        self.assertEqual(
            bot_pi.command_with_dir(cmd, "/new"),
            ["pi", "--mode", "json", "--model", "openai/gpt-5"],
        )

    def test_session_command_appends_session_option(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                bot_pi.pi_session_command("019df6bf-b533-72ef-ab1f-deaebb66a91d"),
                [
                    "pi",
                    "--mode",
                    "json",
                    "--session",
                    "019df6bf-b533-72ef-ab1f-deaebb66a91d",
                ],
            )

    def test_resume_last_command_uses_pi_continue(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(
                bot_pi.pi_resume_last_command(),
                ["pi", "--mode", "json", "--continue"],
            )

    def test_add_files_to_command_uses_pi_file_args(self):
        cmd = ["pi", "--mode", "json", "--session", "019df6bf-b533-72ef-ab1f-deaebb66a91d", "Describe this"]

        self.assertEqual(
            bot_pi.add_files_to_command(cmd, [Path("/tmp/a.png"), Path("/tmp/b.txt")]),
            [
                "pi",
                "--mode",
                "json",
                "--session",
                "019df6bf-b533-72ef-ab1f-deaebb66a91d",
                "Describe this",
                "@/tmp/a.png",
                "@/tmp/b.txt",
            ],
        )

    def test_parse_session_id_accepts_pi_session_header(self):
        self.assertEqual(
            bot_pi.parse_session_id(
                '{"type":"session","id":"019df6bf-b533-72ef-ab1f-deaebb66a91d","cwd":"/home/debian"}'
            ),
            "019df6bf-b533-72ef-ab1f-deaebb66a91d",
        )

    def test_old_ses_session_ids_are_not_valid_for_pi(self):
        self.assertFalse(bot_pi.valid_session_id("ses_21586fc63ffe054SNYSZo63vLm"))

    def test_extract_final_answer_joins_json_text_deltas(self):
        output = "\n".join(
            [
                '{"type":"message.part.delta","properties":{"field":"text","delta":"Hello"}}',
                '{"type":"message.part.delta","properties":{"field":"text","delta":" world"}}',
            ]
        )

        self.assertEqual(bot_pi.extract_final_answer(output), "Hello world")

    def test_extract_final_answer_reads_pi_assistant_messages(self):
        output = (
            '{"type":"message_end","message":{"role":"assistant",'
            '"content":[{"type":"text","text":"HELLO_FROM_PI"}]}}'
        )

        self.assertEqual(bot_pi.extract_final_answer(output), "HELLO_FROM_PI")

    def test_extract_final_answer_uses_last_pi_turn(self):
        output = "\n".join(
            [
                '{"type":"message_end","message":{"role":"assistant","content":[{"type":"text","text":"OLD"}]}}',
                '{"type":"turn_end","message":{"role":"assistant","content":[{"type":"text","text":"NEW"}]}}',
            ]
        )

        self.assertEqual(bot_pi.extract_final_answer(output), "NEW")


if __name__ == "__main__":
    unittest.main()
