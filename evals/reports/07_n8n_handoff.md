# Check 7: n8n hand-off (PDF + drafted email + human approval)

Run locally on 2026-10-07 with n8n 2.42.4 (Node 24.9), `python -m recipe_agent.report_server` on :8765 and
`n8n/smtp_sink.py` as the SMTP server, so mail was captured to `output/handoff/` and never delivered.

| execution | trigger | approver decision | nodes run (from n8n's execution data) | email to recipients |
|---|---|---|---|---|
| 3 | POST /webhook/recipe-dataset-handoff | Reject | webhook → summary → Compile PDF → Draft email → Ask approver → Wait for human approval → Approved? → Rejected: nothing sent | none |
| 4 | POST /webhook/recipe-dataset-handoff | Approve and send | webhook → summary → Compile PDF → Draft email → Ask approver → Wait for human approval → Approved? → Final email with PDF → Send dataset email | `03-dessert-recipe-dataset-…` with `recipe_dataset.pdf` attached |

Both executions finished with status `success`. The approval form is reached only through the signed
`$execution.resumeFormUrl` link in the approver's email; until it is submitted the execution waits and nothing
is sent to the recipients.

Captured messages: `output/handoff/01-…txt` and `02-…txt` (approval requests, PDF attached for review) and
`03-…txt` (the approved email). The `.eml` originals with the base64 PDF are not committed.

(Executions 1 and 2 were an earlier identical run before the final batch; 3 and 4 above are against the final
dataset.) The PDF attached to the approved email is byte-identical to `output/recipe_dataset.pdf` (28 pages).
