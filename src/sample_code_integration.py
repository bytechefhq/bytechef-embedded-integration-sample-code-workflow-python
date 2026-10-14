from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bytechef_workflow_api import IntegrationDefinition, TaskContext


def shout(context: "TaskContext") -> str:
    return str(context.input("message")).upper()


integration: "IntegrationDefinition" = {
    "componentName": "httpClient",
    "componentVersion": 1,
    "version": "0.0.1",
    "description": "A sample code integration built on the HTTP Client component.",
    "workflows": [
        {
            "name": "echoMessage",
            "label": "Echo Message",
            "description": "Returns the message it was given, upper-cased.",
            "inputs": [{"name": "message", "label": "Message", "type": "STRING", "required": True}],
            "outputs": [{"name": "result", "task": "shout"}],
            "tasks": [
                {
                    "name": "shout",
                    "label": "Shout",
                    "description": "Upper-cases the message.",
                    "perform": shout,
                }
            ],
        }
    ],
}

integration
