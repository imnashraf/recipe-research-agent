"""Generates the n8n workflows (kept as code so the JSON stays reviewable).

    python n8n/build_workflow.py

  recipe_dataset_handoff.json        local test: SMTP credential, backend on 127.0.0.1:8765
  recipe_dataset_handoff_cloud.json  n8n Cloud: Gmail OAuth credential, backend URL sent by the
                                     Railway service in the webhook body and checked against an
                                     allow-list in the "Settings" node
"""

import json
import uuid
from pathlib import Path

REPORT = "http://127.0.0.1:8765"
FROM, APPROVER, RECIPIENTS = "recipe-agent@example.com", "approver@example.com", "dataset-recipients@example.com"
SMTP = {"smtp": {"id": "recipeAgentSmtp", "name": "Recipe agent SMTP"}}

DRAFT_JS = r"""
const s = $('Get dataset summary').first().json;
const states = Object.entries(s.terminal_states).map(([k, v]) => `${k}: ${v}`).join(', ');
const subject = `${s.category} recipe dataset: ${s.recipes} recipes, ${(s.match_rate * 100).toFixed(1)}% ingredient match rate`;
const body = [
  'Hello,',
  '',
  `Attached is the ${s.category.toLowerCase()} recipe dataset compiled by the recipe research agent (PDF).`,
  '',
  `- Recipes: ${s.recipes} (terminal states: ${states})`,
  `- Ingredient lines: ${s.ingredients}; matched to a USDA SR28 food id: ${s.matched} (${(s.match_rate * 100).toFixed(1)}%)`,
  `- With a gram weight and nutrition: ${s.ingredients_with_nutrition}; unknown: ${s.unknown} (${s.hit_retry_cap} reached the retry cap)`,
  `- Cook notes cards: ${s.cards_produced} produced, ${s.cards_skipped} skipped (fewer than ${s.comment_threshold} comments)`,
  '',
  `Settings: retry cap ${s.retry_cap} lookups per ingredient, comment threshold ${s.comment_threshold}, card cap ${s.card_word_cap} words.`,
  'Unmatched ingredients are listed as unknown with the queries tried; they are never estimated, so recipe totals marked Partial leave them out.',
  '',
  'Regards,',
  'Recipe research agent (sent after human approval)',
].join('\n');
return [{ json: { to: '__RECIPIENTS__', subject, body }, binary: $('Compile PDF').first().binary }];
""".replace("__RECIPIENTS__", RECIPIENTS)

FINAL_JS = r"""
const draft = $('Draft email').first().json;
const edited = ($json['Edited body (optional)'] || '').trim();
return [{
  json: { to: draft.to, subject: draft.subject, body: edited || draft.body, approved_at: $json.submittedAt || null },
  binary: $('Compile PDF').first().binary,
}];
"""


def node(name, type_, version, params, pos, **extra):
    return {"parameters": params, "id": str(uuid.uuid5(uuid.NAMESPACE_URL, name)), "name": name,
            "type": type_, "typeVersion": version, "position": pos, **extra}


nodes = [
    node("Batch finished (webhook)", "n8n-nodes-base.webhook", 2,
         {"httpMethod": "POST", "path": "recipe-dataset-handoff", "responseMode": "onReceived", "options": {}},
         [0, 300], webhookId=str(uuid.uuid5(uuid.NAMESPACE_URL, "recipe-dataset-handoff-webhook"))),
    node("Get dataset summary", "n8n-nodes-base.httpRequest", 4.2, {"url": f"{REPORT}/summary", "options": {}}, [220, 300]),
    node("Compile PDF", "n8n-nodes-base.httpRequest", 4.2,
         {"url": f"{REPORT}/report.pdf",
          "options": {"response": {"response": {"responseFormat": "file", "outputPropertyName": "report"}}}},
         [440, 300]),
    node("Draft email", "n8n-nodes-base.code", 2, {"jsCode": DRAFT_JS.strip()}, [660, 300]),
    node("Ask approver", "n8n-nodes-base.emailSend", 2.1,
         {"fromEmail": FROM, "toEmail": APPROVER,
          "subject": "=Approval needed before sending: {{ $json.subject }}",
          "emailFormat": "text",
          "text": "=A draft email with the recipe dataset PDF is waiting for your approval. Nothing is sent until you "
                  "approve.\n\nTo: {{ $json.to }}\nSubject: {{ $json.subject }}\n\n{{ $json.body }}\n\n"
                  "Approve, edit or reject here: {{ $execution.resumeFormUrl }}",
          "options": {"attachments": "report"}},
         [880, 300], credentials=SMTP),
    node("Wait for human approval", "n8n-nodes-base.wait", 1.1,
         {"resume": "form", "formTitle": "Send the recipe dataset email?",
          "formDescription": "=To: {{ $('Draft email').first().json.to }}\nSubject: {{ $('Draft email').first().json.subject }}\n\n{{ $('Draft email').first().json.body }}",
          "formFields": {"values": [
              {"fieldLabel": "Decision", "fieldType": "dropdown",
               "fieldOptions": {"values": [{"option": "Approve and send"}, {"option": "Reject"}]}, "requiredField": True},
              {"fieldLabel": "Edited body (optional)", "fieldType": "textarea"},
          ]},
          "options": {}},
         [1100, 300], webhookId=str(uuid.uuid5(uuid.NAMESPACE_URL, "recipe-dataset-approval-form"))),
    node("Approved?", "n8n-nodes-base.if", 2.2,
         {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                         "conditions": [{"id": "approved", "leftValue": "={{ $json.Decision }}", "rightValue": "Approve and send",
                                         "operator": {"type": "string", "operation": "equals"}}],
                         "combinator": "and"},
          "options": {}},
         [1320, 300]),
    node("Final email with PDF", "n8n-nodes-base.code", 2, {"jsCode": FINAL_JS.strip()}, [1540, 200]),
    node("Send dataset email", "n8n-nodes-base.emailSend", 2.1,
         {"fromEmail": FROM, "toEmail": "={{ $json.to }}", "subject": "={{ $json.subject }}", "emailFormat": "text",
          "text": "={{ $json.body }}", "options": {"attachments": "report"}},
         [1760, 200], credentials=SMTP),
    node("Rejected: nothing sent", "n8n-nodes-base.noOp", 1, {}, [1540, 420]),
]


def link(a, b, out=0):
    return a, b, out


edges = [link("Batch finished (webhook)", "Get dataset summary"), link("Get dataset summary", "Compile PDF"),
         link("Compile PDF", "Draft email"), link("Draft email", "Ask approver"),
         link("Ask approver", "Wait for human approval"), link("Wait for human approval", "Approved?"),
         link("Approved?", "Final email with PDF", 0), link("Approved?", "Rejected: nothing sent", 1),
         link("Final email with PDF", "Send dataset email")]
connections = {}
for a, b, out in edges:
    main = connections.setdefault(a, {"main": []})["main"]
    while len(main) <= out:
        main.append([])
    main[out].append({"node": b, "type": "main", "index": 0})

workflow = {
    "name": "Recipe dataset hand-off (PDF + approved email)",
    "nodes": nodes,
    "connections": connections,
    "settings": {"executionOrder": "v1"},
    "pinData": {},
    "active": False,
    "id": "recipeDatasetHandoff",
    "meta": {"templateCredsSetupCompleted": False},
    "tags": [],
}
Path(__file__).with_name("recipe_dataset_handoff.json").write_text(json.dumps(workflow, indent=2) + "\n")
print("wrote n8n/recipe_dataset_handoff.json")


# ------------------------------------------------------------------------------------------ cloud
SETTINGS_JS = r"""
// ==== Edit these two lines once after importing ====
const APPROVER_EMAIL = 'you@example.com';          // who approves before anything is sent
const RECIPIENTS = 'you@example.com';              // comma-separated list for the final email
// ====================================================
// Only call back to a Railway service. Optionally pin the exact host, e.g. 'recipe-agent.up.railway.app'
const PINNED_HOST = '';
const body = $json.body || {};
const url = String(body.backend_url || '').replace(/\/+$/, '');
const ok = /^https:\/\/[a-z0-9-]+(\.[a-z0-9-]+)*\.up\.railway\.app$/.test(url) && (!PINNED_HOST || url === 'https://' + PINNED_HOST);
if (!ok) throw new Error('Rejected: backend_url must be your https://*.up.railway.app service, got ' + JSON.stringify(url));
if (APPROVER_EMAIL.endsWith('@example.com')) throw new Error('Set APPROVER_EMAIL and RECIPIENTS in the Settings node first');
return [{ json: { backend_url: url, approver: APPROVER_EMAIL, recipients: RECIPIENTS, batch: body.batch || '' } }];
"""

GMAIL = {"gmailOAuth2": {"id": "", "name": "Gmail account"}}


def gmail(name, to, subject, text, pos):
    return node(name, "n8n-nodes-base.gmail", 2.1,
                {"sendTo": to, "subject": subject, "emailType": "text", "message": text,
                 "options": {"appendAttribution": False,
                             "attachmentsUi": {"attachmentsBinary": [{"property": "report"}]}}},
                pos, credentials=GMAIL)


cloud_draft = DRAFT_JS.replace(f"to: '{RECIPIENTS}'", "to: $('Settings').first().json.recipients")
assert cloud_draft != DRAFT_JS
by_name = {n["name"]: n for n in nodes}
cloud_nodes = [
    by_name["Batch finished (webhook)"],
    node("Settings", "n8n-nodes-base.code", 2, {"jsCode": SETTINGS_JS.strip()}, [180, 300]),
    node("Get dataset summary", "n8n-nodes-base.httpRequest", 4.2,
         {"url": "={{ $('Settings').first().json.backend_url }}/api/summary", "options": {}}, [360, 300]),
    node("Compile PDF", "n8n-nodes-base.httpRequest", 4.2,
         {"url": "={{ $('Settings').first().json.backend_url }}/api/report.pdf",
          "options": {"response": {"response": {"responseFormat": "file", "outputPropertyName": "report"}}}},
         [540, 300]),
    node("Draft email", "n8n-nodes-base.code", 2, {"jsCode": cloud_draft.strip()}, [720, 300]),
    gmail("Ask approver", "={{ $('Settings').first().json.approver }}",
          "=Approval needed before sending: {{ $json.subject }}",
          "=A draft email with the recipe dataset PDF is waiting for your approval. Nothing is sent until you "
          "approve.\n\nTo: {{ $json.to }}\nSubject: {{ $json.subject }}\n\n{{ $json.body }}\n\n"
          "Approve, edit or reject here: {{ $execution.resumeFormUrl }}", [900, 300]),
    {**by_name["Wait for human approval"], "position": [1100, 300]},
    {**by_name["Approved?"], "position": [1300, 300]},
    {**by_name["Final email with PDF"], "position": [1500, 200]},
    gmail("Send dataset email", "={{ $json.to }}", "={{ $json.subject }}", "={{ $json.body }}", [1700, 200]),
    {**by_name["Rejected: nothing sent"], "position": [1500, 420]},
]
cloud_edges = [("Batch finished (webhook)", "Settings", 0), ("Settings", "Get dataset summary", 0)] + [
    e for e in edges if e[0] != "Batch finished (webhook)"]
cloud_connections = {}
for a, b, out in cloud_edges:
    main = cloud_connections.setdefault(a, {"main": []})["main"]
    while len(main) <= out:
        main.append([])
    main[out].append({"node": b, "type": "main", "index": 0})
cloud = {**workflow, "name": "Recipe dataset hand-off (n8n Cloud, Gmail)", "id": "recipeDatasetHandoffCloud",
         "nodes": cloud_nodes, "connections": cloud_connections}
Path(__file__).with_name("recipe_dataset_handoff_cloud.json").write_text(json.dumps(cloud, indent=2) + "\n")
print("wrote n8n/recipe_dataset_handoff_cloud.json")
