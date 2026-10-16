# bytechef-embedded-integration-sample-code-workflow-python

A sample ByteChef **embedded code integration** written in Python. The whole integration is one file,
[`src/sample_code_integration.py`](src/sample_code_integration.py), and that file is what you deploy - there is no
build step. The file is a single Python script. The server runs it with GraalPy and reads the value of its **last
expression**: the script defines each task's `perform` function with `def`, builds the integration as a plain `dict`
assigned to `integration`, and ends with `integration` alone on the last line. The server reads the dict's
`componentName`, `componentVersion`, `description`, `version` and `workflows`, then calls each task's
`perform(context)` when the workflow runs. Keep the definition a plain dict and keep it last: anything after it, or a
`main()` wrapper, hides the dict from the server.

A code integration is keyed by the component it integrates, and that component must exist on the server. This sample
uses the built-in Gmail component, `googleMail` version 1, so connecting the integration means connecting a Gmail
account. It has three workflows:

- `summarizeNewEmail` starts with the Gmail **New Email** polling trigger (`googleMail/v1/newEmailPolling`). It runs once
  for every new email and its `summarize` task returns a one-line summary as the `summary` output. A Gmail trigger on a
  Gmail integration runs on the connection the connected user created when they connected the integration - there is
  nothing to declare.
- `fetchRecentEmails` starts with a request trigger, so you call it over HTTP. Its `fetchEmails` task calls the Gmail
  **Search Email** action and returns the matching messages as the `emails` output.
- `notifySlackOnNewEmail` starts with the same Gmail trigger and takes a required `channel` input; its options come from
  Slack's own `channel` input (`componentName`, `componentVersion` and `groupName` on the input), so it is picked from
  the Slack workspace's channels. Its `postToSlack` task calls the Slack **Send Channel Message** action, and Slack is
  not the integration's component, so the task declares a `slack` connection and passes its name. An administrator picks
  that connection when enabling the workflow in the integration's instance configuration; until one is picked the
  workflow cannot be enabled, and the channel list stays empty.

Inside `perform`, `context.input()` returns the workflow inputs, the trigger output (under the trigger's name) and the
output of every task that already ran (under the task's name); `context.input("newEmail")` returns one of them, and
`context.log(level, message)` writes to the execution log.

### Connections

A task calls an action of the integration's own component - `googleMail` here - without declaring a connection. It
runs on the connected user's integration connection, which ByteChef binds when the workflow runs:

```python
def fetch_emails(context: "TaskContext") -> Any:
    return context.component.googleMail.searchEmail({"maxResults": 10})

# in the task definition:
"perform": fetch_emails,
```

A task that calls any other component (say `slack`) declares that connection and passes its name. An administrator
chooses it in the integration's instance configuration, and it is the same for every connected user:

```python
def notify(context: "TaskContext") -> Any:
    return context.component.slack.sendChannelMessage({"channel": "C0123456", "text": "New email"}, "slack")

# in the task definition:
"connections": [{"componentName": "slack", "name": "slack"}],
"perform": notify,
```

## Types

The keys are the same camelCase keys as in a JavaScript code integration (`componentName` is a string,
`componentVersion` an integer). To have a type checker catch a missing `componentName` or a misspelled `perform`, the
file is annotated with the types from the
[`bytechef-workflow-api`](https://pypi.org/project/bytechef-workflow-api/) package:
`integration: "IntegrationDefinition"` and `def summarize(context: "TaskContext") -> str`. The ByteChef runtime can't
import that package, so the file imports it only under `typing.TYPE_CHECKING` and quotes the annotations; at run time
the import is skipped. Standard-library imports are fine; nothing else is available on the server.

## Check

```bash
python3 scripts/check.py src/sample_code_integration.py
```

Evaluates the file the same way the server does (runs every statement but the last, then evaluates the last
expression), checks its shape and runs each task once with a stub context. The stub stands in for Gmail: every trigger
output and every component action call returns a fixed sample email, and a request trigger an empty body. It needs
only Python 3.9 or later; there are no dependencies to install.

To type check the file as well:

```bash
pip install -r requirements-dev.txt
mypy --strict src scripts
```

`requirements-dev.txt` installs `bytechef-workflow-api` and `mypy`.

## Deploy

Upload `src/sample_code_integration.py`. Deploying again for the same component deploys a new version of the
existing code integration instead of creating a second one.

### From the UI

Embedded → **Integrations** → the arrow next to **New Integration** → **Import Code Integration**, then pick the file.

### Through the public API

`POST /api/embedded/v1/integration-code-workflows/deploy` with a `multipart/form-data` body holding one file part,
`integrationFile`: the `.py` file. The file name must end in `.py`; the server picks the language from the
extension. A successful deploy returns `204 No Content`.

Authenticate with `Authorization: Bearer <API key>`, using an **Embedded API key** (Embedded → Settings →
**API Keys**) that belongs to an administrator - deploying requires the admin role. This endpoint takes only a typed
API key: an organization admin key (Settings → Organization → **Admin API Keys**) is rejected with `401`. The key is
looked up in the environment named by the `X-ENVIRONMENT` header (`DEVELOPMENT`, `STAGING` or `PRODUCTION`;
`PRODUCTION` when the header is absent), so send the environment the key was created in. The request runs as the
key's own ByteChef user, not as a connected user.

```bash
curl -X POST "$BYTECHEF_URL/api/embedded/v1/integration-code-workflows/deploy" \
  -H "Authorization: Bearer $BYTECHEF_EMBEDDED_API_KEY" \
  -H "X-ENVIRONMENT: DEVELOPMENT" \
  -F "integrationFile=@src/sample_code_integration.py"
```

`BYTECHEF_URL` is the server's base URL, for example `http://localhost:9555` for a local development server.

## Enable and run

Deploying with `?enable=true` also enables the integration in that environment. A Gmail integration needs Gmail OAuth
app credentials first: an administrator enters them in the integration's instance configuration, and until then the
enable is refused.

Once a connected user has connected the integration and enabled `fetchRecentEmails` on their integration instance
(`POST /api/embedded/v1/integration-instances/{id}/workflows/{workflowUuid}/enable`), call it with their JWT:

```bash
curl -X POST "$BYTECHEF_URL/api/embedded/v1/workflows/$WORKFLOW_UUID" \
  -H "Authorization: Bearer $CONNECTED_USER_JWT" \
  -H "X-ENVIRONMENT: DEVELOPMENT" \
  -H "Content-Type: application/json" \
  -d '{"from": "ada@example.com", "maxResults": 5}'
```

The body is optional. `summarizeNewEmail` needs no call: once enabled, it runs whenever a new email arrives.
