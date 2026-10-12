export const SAMPLE_THREADS = [
  {
    title: "Project Alpha Launch Coordination",
    content: `From: sarah.miller@acme.corp
To: engineering-team@acme.corp, alex.wong@acme.corp, priya.sharma@acme.corp
Date: Mon, 12 Oct 2026 09:15:00 -0400
Subject: Re: Project Alpha Launch Date & Blocker Review

Hi everyone,

Following up on our sprint retro, we need to finalize the launch schedule for Project Alpha. As discussed, the marketing campaign goes live on October 25th.

Can we confirm if the database migration scripts are ready?

---
From: alex.wong@acme.corp
To: sarah.miller@acme.corp, engineering-team@acme.corp, priya.sharma@acme.corp
Date: Mon, 12 Oct 2026 10:30:00 -0400
Subject: Re: Project Alpha Launch Date & Blocker Review

Hi Sarah,

Yes, we completed the dry-run yesterday. The migration script passed all sanity checks.
We made the final decision to deploy the schema updates to Staging this Wednesday at 8 PM EST.

I will personally handle the production database deployment on Friday, October 23rd by 5:00 PM EST.

However, we are still waiting on legal approval for the updated Terms of Service. Who is following up with the compliance team on that?

---
From: priya.sharma@acme.corp
To: alex.wong@acme.corp, sarah.miller@acme.corp, engineering-team@acme.corp
Date: Mon, 12 Oct 2026 11:45:00 -0400
Subject: Re: Project Alpha Launch Date & Blocker Review

Thanks Alex. I will reach out to David in legal today to get the Terms of Service signed off before Thursday, October 15th.

Also, we agreed that we will not enable payment gateway integration for EU customers in this first release—that is deferred to Phase 2.

One open question: what is our fallback protocol if the primary Redis cache fails during peak traffic on launch day? Did the DevOps team create a failover runbook for that?

---
From: sarah.miller@acme.corp
To: priya.sharma@acme.corp, alex.wong@acme.corp, engineering-team@acme.corp
Date: Mon, 12 Oct 2026 13:00:00 -0400
Subject: Re: Project Alpha Launch Date & Blocker Review

Great. So decisions are locked: Staging deploy Wednesday, Prod deploy Oct 23rd, EU payment deferred.

Priya, please make sure legal confirms by Thursday.
Alex, let me know once staging is verified.

Let's meet tomorrow at 10 AM for the daily standup.`,
  },
  {
    title: "Quarterly Budget Planning & Vendor Selection",
    content: `From: mark.chen@enterprise.io
To: finance-committee@enterprise.io
Subject: Q4 Cloud Infrastructure Vendor Selection

Team,

We evaluated AWS vs GCP cost structures for the ML training pipeline.
After reviewing the volume discount proposal, we decided to sign the 1-year contract with AWS.

Action items:
- Mark Chen: Finalize and sign the contract by October 18, 2026.
- Elena Rostova: Set up the IAM roles and billing alerts before October 22, 2026.

Open questions:
- Are there any remaining data sovereignty compliance requirements for customer data stored in Frankfurt?`,
  },
];
