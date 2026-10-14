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
uses the built-in HTTP Client, `httpClient` version 1. It has one workflow, `echoMessage`: it takes a `message`
input, runs one task, `shout`, that upper-cases it, and exposes that as the `result` output.

Inside `perform`, `context.input()` returns the workflow inputs plus the output of every task that already ran
(under the task's name), `context.input("message")` returns one of them, and `context.log(level, message)` writes to
the execution log.

## Types

The keys are the same camelCase keys as in a JavaScript code integration (`componentName` is a string,
`componentVersion` an integer). To have a type checker catch a missing `componentName` or a misspelled `perform`, the
file is annotated with the types from the
[`bytechef-workflow-api`](https://pypi.org/project/bytechef-workflow-api/) package:
`integration: "IntegrationDefinition"` and `def shout(context: "TaskContext") -> str`. The ByteChef runtime can't
import that package, so the file imports it only under `typing.TYPE_CHECKING` and quotes the annotations; at run time
the import is skipped. Standard-library imports are fine; nothing else is available on the server.

## Check

```bash
python3 scripts/check.py src/sample_code_integration.py message=hello
```

Evaluates the file the same way the server does (runs every statement but the last, then evaluates the last
expression), checks its shape and runs each task once with a stub context. It needs only Python 3.9 or later; there
are no dependencies to install.

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
