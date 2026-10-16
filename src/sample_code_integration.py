from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from bytechef_workflow_api import IntegrationDefinition, TaskContext


def summarize(context: "TaskContext") -> str:
    email = context.input("newEmail")

    summary = f"New email from {email['from']}: {email['subject']}"

    context.log("info", summary)

    return summary


def fetch_emails(context: "TaskContext") -> List[Any]:
    request = context.input().get("request") or {}
    body = request.get("body") or {}

    result = context.component.googleMail.searchEmail(
        {"from": body.get("from"), "maxResults": body.get("maxResults") or 10}
    )

    messages: List[Any] = result.get("messages") or []

    context.log("info", f"Found {len(messages)} emails")

    return messages


def post_to_slack(context: "TaskContext") -> Any:
    email = context.input("newEmail")

    text = f"New email from {email['from']}: {email['subject']}"

    message = context.component.slack.sendChannelMessage({"channel": context.input("channel"), "text": text}, "slack")

    context.log("info", f"Posted to Slack: {text}")

    return message


integration: "IntegrationDefinition" = {
    "componentName": "googleMail",
    "componentVersion": 1,
    "version": "0.0.1",
    "description": "A sample code integration built on the Gmail component.",
    "workflows": [
        {
            "name": "summarizeNewEmail",
            "label": "Summarize New Email",
            "description": "Runs for every new email in the connected user's inbox and logs who sent it.",
            # A Gmail trigger on a Gmail integration runs on the connection the connected user created when they
            # connected the integration - nothing to declare.
            "triggers": [
                {"name": "newEmail", "type": "googleMail/v1/newEmailPolling", "parameters": {"format": "SIMPLE"}}
            ],
            "outputs": [{"name": "summary", "task": "summarize"}],
            "tasks": [
                {
                    "name": "summarize",
                    "label": "Summarize",
                    "description": "Builds a one-line summary of the new email.",
                    "perform": summarize,
                }
            ],
        },
        {
            "name": "fetchRecentEmails",
            "label": "Fetch Recent Emails",
            "description": "Returns the connected user's most recent emails, optionally only those from one sender.",
            # awaitWorkflowAndRespond makes a call to the workflow return its outputs.
            "triggers": [{"name": "request", "type": "request/v1/awaitWorkflowAndRespond"}],
            "outputs": [{"name": "emails", "task": "fetchEmails"}],
            "tasks": [
                {
                    "name": "fetchEmails",
                    "label": "Fetch Emails",
                    "description": "Searches the inbox with the Gmail Search Email action.",
                    # A call to the integration's own component needs no declared connection: it runs on the
                    # connected user's integration connection. Declare and name only connections to other components.
                    "perform": fetch_emails,
                }
            ],
        },
        {
            "name": "notifySlackOnNewEmail",
            "label": "Notify Slack on New Email",
            "description": "Posts every new email in the connected user's inbox to a Slack channel.",
            "inputs": [{"name": "channel", "label": "Slack Channel ID", "type": "STRING", "required": True}],
            "triggers": [
                {"name": "newEmail", "type": "googleMail/v1/newEmailPolling", "parameters": {"format": "SIMPLE"}}
            ],
            "outputs": [{"name": "message", "task": "postToSlack"}],
            "tasks": [
                {
                    "name": "postToSlack",
                    "label": "Post to Slack",
                    "description": "Posts the sender and subject with the Slack Send Channel Message action.",
                    # Slack is not the integration's component, so the task declares its connection and
                    # passes the name. An administrator picks the Slack connection when enabling the
                    # workflow in the integration's instance configuration.
                    "connections": [{"componentName": "slack", "name": "slack"}],
                    "perform": post_to_slack,
                }
            ],
        },
    ],
}

integration
