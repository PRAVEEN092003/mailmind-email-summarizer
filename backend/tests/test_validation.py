"""Comprehensive validation tests for MailMind performance and extraction fixes."""

import asyncio
import time
import unittest
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.schemas import (
    ActionItem,
    StructuredSummary,
    EmailSummarizeRequest,
    EmailSummarizeResponse,
)
from app.models.database import SessionLocal, init_db, SummaryRecord
from app.services.ai_service import OllamaService
from app.services.email_service import EmailService


class TestSchemasAndNormalization(unittest.TestCase):
    """Test schema validation and null sanitization."""

    def test_action_item_null_string_normalization(self):
        item = ActionItem(
            item="Test task",
            responsible_person="null",
            deadline="None",
            status="PENDING",
        )
        self.assertIsNone(item.responsible_person)
        self.assertIsNone(item.deadline)
        self.assertEqual(item.status, "pending")

    def test_action_item_unassigned_string_normalization(self):
        item = ActionItem(
            item="Test task 2",
            responsible_person="Unassigned",
            deadline="Not specified",
            status="completed",
        )
        self.assertIsNone(item.responsible_person)
        self.assertIsNone(item.deadline)
        self.assertEqual(item.status, "completed")

    def test_structured_summary_sanitization(self):
        summary = StructuredSummary(
            overall_summary="Brief summary",
            main_discussion_points=["Point 1"],
            confirmed_decisions=["Decision 1"],
            action_items=[
                ActionItem(item="Task 1", responsible_person="Arun", deadline="12 PM"),
            ],
            responsible_persons=["Arun", "null", "none"],
            deadlines=["12 PM", "null"],
            urgency_level="MEDIUM",
        )
        self.assertEqual(summary.responsible_persons, ["Arun"])
        self.assertEqual(summary.deadlines, ["12 PM"])
        self.assertEqual(summary.important_decisions, ["Decision 1"])


class TestRefinementLogic(unittest.TestCase):
    """Test precision refinement and entity attribution."""

    def setUp(self):
        self.ai_service = OllamaService()

    def test_refine_and_sanitize_example_email(self):
        email_text = """Hi Team,

Our weekly meeting is scheduled for tomorrow at 3 PM.
Arun must finish the login module by 12 PM.
Priya will test the API integration.
Please send your progress updates before the meeting.

Thanks,
Manager"""
        raw_llm_data = {
            "overall_summary": "Weekly meeting scheduled for tomorrow. Tasks assigned.",
            "main_discussion_points": ["Meeting schedule", "Tasks"],
            "confirmed_decisions": [],
            "action_items": [
                {
                    "item": "Finish the login module",
                    "responsible_person": "Arun",
                    "deadline": "12 PM tomorrow",
                    "status": "pending",
                },
                {
                    "item": "Test the API integration",
                    "responsible_person": "Priya",
                    "deadline": "12 PM tomorrow",  # Hallucinated copy from Arun
                    "status": "pending",
                },
                {
                    "item": "Send progress updates before the meeting",
                    "responsible_person": None,
                    "deadline": None,
                    "status": "pending",
                },
            ],
            "responsible_persons": ["Arun", "Priya"],
            "deadlines": ["12 PM tomorrow"],
            "urgency_level": "MEDIUM",
        }

        refined = self.ai_service._refine_and_sanitize_summary(
            raw_llm_data, email_text, "Tomorrow's Team Meeting"
        )

        items = refined["action_items"]
        self.assertEqual(len(items), 3)

        # Item 1: Arun / Finish the login module / 12 PM tomorrow
        self.assertEqual(items[0]["responsible_person"], "Arun")
        self.assertIn("Finish the login module", items[0]["item"])
        self.assertEqual(items[0]["deadline"], "12 PM tomorrow")

        # Item 2: Priya / Test the API integration / null
        self.assertEqual(items[1]["responsible_person"], "Priya")
        self.assertIn("Test the API integration", items[1]["item"])
        self.assertIsNone(items[1]["deadline"], "Priya has no deadline in the email; should be None")

        # Item 3: Team / Send progress updates / Before tomorrow's 3 PM meeting
        self.assertEqual(items[2]["responsible_person"], "Team")
        self.assertIn("Send progress updates before the meeting", items[2]["item"])
        self.assertEqual(items[2]["deadline"], "Before tomorrow's 3 PM meeting")

        # Sync checks
        self.assertIn("Arun", refined["responsible_persons"])
        self.assertIn("Priya", refined["responsible_persons"])
        self.assertIn("Team", refined["responsible_persons"])

        self.assertIn("12 PM tomorrow", refined["deadlines"])
        self.assertIn("Before tomorrow's 3 PM meeting", refined["deadlines"])


class TestEndToEndSummarization(unittest.IsolatedAsyncioTestCase):
    """Live end-to-end tests measuring performance, cache behavior, and extraction."""

    async def test_live_summarization_and_cache(self):
        init_db()
        db = SessionLocal()
        email_service = EmailService()

        # Unique email content for fresh test
        unique_stamp = int(time.time())
        email_content = f"""Hi Team,

Our weekly meeting is scheduled for tomorrow at 3 PM. (Ref {unique_stamp})
Arun must finish the login module by 12 PM.
Priya will test the API integration.
Please send your progress updates before the meeting.

Thanks,
Manager"""
        subject = f"Tomorrow's Team Meeting {unique_stamp}"
        request = EmailSummarizeRequest(email_content=email_content, subject=subject)

        # 1. First run: Live Ollama execution (Cache Miss)
        t0 = time.perf_counter()
        res1 = await email_service.summarize_email_thread(request=request, db=db, user_id=None)
        t_miss = (time.perf_counter() - t0) * 1000

        print(f"\n[BENCHMARK] Live Run (Cache Miss): Total {t_miss:.1f}ms | Ollama Generation {res1.ollama_generation_time_ms:.1f}ms")

        self.assertTrue(res1.success)
        self.assertFalse(res1.is_cached)
        self.assertIsNotNone(res1.data)
        self.assertGreater(res1.processing_time_ms, 0)
        self.assertIsNotNone(res1.ollama_generation_time_ms)

        # Verify action items
        actions = res1.data.action_items
        self.assertGreaterEqual(len(actions), 3, "Expected at least 3 action items")

        action_dict = {a.responsible_person: a for a in actions if a.responsible_person}
        self.assertIn("Arun", action_dict)
        self.assertIn("Priya", action_dict)
        self.assertIn("Team", action_dict)

        # Verify Arun
        self.assertEqual(action_dict["Arun"].deadline, "12 PM tomorrow")
        self.assertIn("Finish the login module", action_dict["Arun"].item)

        # Verify Priya
        self.assertIsNone(action_dict["Priya"].deadline)
        self.assertIn("Test the API integration", action_dict["Priya"].item)

        # Verify Team
        self.assertEqual(action_dict["Team"].deadline, "Before tomorrow's 3 PM meeting")
        self.assertIn("Send progress updates before the meeting", action_dict["Team"].item)

        # 2. Second run: SQLite Cache Hit
        t1 = time.perf_counter()
        res2 = await email_service.summarize_email_thread(request=request, db=db, user_id=None)
        t_hit = (time.perf_counter() - t1) * 1000

        print(f"[BENCHMARK] Cache Hit Run: Total {t_hit:.2f}ms | is_cached={res2.is_cached}")

        self.assertTrue(res2.success)
        self.assertTrue(res2.is_cached)
        self.assertEqual(res2.content_hash, res1.content_hash)
        self.assertLess(t_hit, 50.0, "Cache hit must return in under 50ms")

        db.close()

    async def test_health_check_does_not_poison_summarize_timeout(self):
        """Regression test: calling check_health (5s timeout) must never poison subsequent summarize calls."""
        ai_service = OllamaService()

        # 1. Call health check (which used to set the client's timeout to 5.0s)
        health = await ai_service.check_health()
        self.assertTrue(health["connected"])

        # 2. Call summarize on a fresh unique prompt and verify it does NOT time out after 5 seconds
        unique_stamp = int(time.time() * 1000)
        t0 = time.perf_counter()
        summary, gen_ms = await ai_service.summarize(
            thread_content=f"Hi Team, please finalize the quarterly budget by tomorrow 4 PM. (ID {unique_stamp})",
            subject="Quarterly Budget"
        )
        elapsed = time.perf_counter() - t0
        self.assertIsNotNone(summary.overall_summary)
        self.assertGreater(gen_ms, 0)
        print(f"[REGRESSION TEST PASSED] summarize() succeeded after check_health() in {elapsed:.2f}s (gen: {gen_ms:.2f}ms)")

    async def test_regression_project_alpha_single_email_no_hallucinations(self):
        """Regression test: Sarah Miller's single email must not hallucinate Terms of Service, staging, standups, or Redis."""
        email_text = (
            "From: sarah.miller@acme.corp\n"
            "To: engineering-team@acme.corp, alex.wong@acme.corp, priya.sharma@acme.corp\n"
            "Date: Mon, 12 Oct 2026 09:15:00 -0400\n"
            "Subject: Re: Project Alpha Launch Date & Blocker Review\n\n"
            "Hi everyone,\n\n"
            "Following up on our sprint retro, we need to finalize the launch schedule for Project Alpha. As discussed, the marketing campaign goes live on October 25th.\n\n"
            "Can we confirm if the database migration scripts are ready?"
        )
        ai_service = OllamaService()
        summary, gen_ms = await ai_service.summarize(
            thread_content=email_text,
            subject="Re: Project Alpha Launch Date & Blocker Review"
        )
        summary_dump = summary.model_dump_json().lower()

        # 1. Assert unsupported entities are NOT present
        self.assertNotIn("terms of service", summary_dump)
        self.assertNotIn("staging", summary_dump)
        self.assertNotIn("standup", summary_dump)
        self.assertNotIn("redis", summary_dump)
        self.assertNotIn("fallback protocol", summary_dump)
        self.assertNotIn("phase 2", summary_dump)

        # 2. Assert unanswered question about migration scripts readiness is captured
        self.assertTrue(
            any("migration script" in str(q).lower() for q in summary.unanswered_questions),
            f"Expected unanswered question about migration scripts, got: {summary.unanswered_questions}"
        )

        # 3. Assert no confirmed decisions were invented
        self.assertEqual(summary.confirmed_decisions, [])
        print("[REGRESSION TEST PASSED] test_regression_project_alpha_single_email_no_hallucinations succeeded!")


if __name__ == "__main__":
    unittest.main()

