# Evaluates a code workflow file the way the ByteChef server does - the server runs the script and reads the value
# of its last expression - then checks its shape and runs every task once.
#
# Usage: python3 scripts/check.py <file> [inputName=value ...]

import ast
import json
import re
import sys
from typing import Any, Callable, Dict, List, NoReturn, Optional

# Stands in for the platform: a component action returns a fixed sample, a trigger output and a request body are
# fixed samples too, and a declared connection has no parameters, so every task can run without a server or a real
# connection.
SAMPLE_EMAIL: Dict[str, Any] = {
    "from": "ada@example.com",
    "id": "18c2f0a1",
    "subject": "Welcome",
    "threadId": "18c2f0a1",
}


def fail(message: str) -> NoReturn:
    print("FAIL: " + message, file=sys.stderr)

    sys.exit(1)


def evaluate(file: str) -> Any:
    with open(file, encoding="utf-8") as source_file:
        source = source_file.read()

    module = ast.parse(source, filename=file)

    last_expression = module.body[-1] if module.body else None

    if not isinstance(last_expression, ast.Expr):
        fail("the file must end with an expression - put the definition variable alone on the last line")

    namespace: Dict[str, Any] = {"__name__": "__main__"}

    exec(compile(ast.Module(body=module.body[:-1], type_ignores=[]), file, "exec"), namespace)

    return eval(compile(ast.Expression(body=last_expression.value), file, "eval"), namespace)


class StubComponent:
    def __init__(self, component_name: str) -> None:
        self._component_name = component_name

    def __getattr__(self, action_name: str) -> Callable[..., Dict[str, Any]]:
        if action_name.startswith("__"):
            raise AttributeError(action_name)

        def action(action_input: Any, connection_name: Optional[str] = None, *arguments: Any) -> Dict[str, Any]:
            print(
                "  " + self._component_name + "." + action_name
                + "(" + json.dumps(action_input) + ", " + json.dumps(connection_name) + ")"
            )

            return {"messages": [dict(SAMPLE_EMAIL)]}

        return action


class StubComponents:
    def __getattr__(self, component_name: str) -> StubComponent:
        if component_name.startswith("__"):
            raise AttributeError(component_name)

        return StubComponent(component_name)


def trigger_output(trigger: Dict[str, Any]) -> Dict[str, Any]:
    if str(trigger.get("type")).startswith(("request/", "apiPlatform/")):
        return {"body": {}}

    return dict(SAMPLE_EMAIL)


class StubContext:
    def __init__(self) -> None:
        self.component = StubComponents()

    def log(self, level: str, message: str) -> None:
        print("  [" + level + "] " + message)


def required_parameter_count(perform: Callable[..., Any]) -> int:
    code = getattr(perform, "__code__", None)

    if code is None:
        return 2

    defaults = getattr(perform, "__defaults__", None) or ()

    return int(code.co_argcount) - len(defaults)


def task_connection(task: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    connections = task.get("connections") or []

    if isinstance(connections, dict):
        connection_names = list(connections)
    else:
        connection_names = [connection["name"] for connection in connections]

    return {connection_name: {} for connection_name in connection_names}


COMPONENT_TASK_TYPE_PATTERN = re.compile(r"[^/\s]+/v[1-9]\d{0,8}/[^/\s]+")

EXPRESSION_PATTERN = re.compile(r"\$\{([^}]+)\}")


def evaluate_expression(expression: str, values: Dict[str, Any]) -> Any:
    value: Any = values

    for segment in re.findall(r"[^.\[\]]+", expression):
        if value is None:
            return None

        if isinstance(value, list):
            index = int(segment)

            value = value[index] if index < len(value) else None
        elif isinstance(value, dict):
            value = value.get(segment)
        else:
            return None

    return value


def resolve_parameter(parameter: Any, values: Dict[str, Any]) -> Any:
    if isinstance(parameter, str):
        whole_expression = EXPRESSION_PATTERN.fullmatch(parameter)

        if whole_expression:
            return evaluate_expression(whole_expression.group(1), values)

        return EXPRESSION_PATTERN.sub(
            lambda match: json_text(evaluate_expression(match.group(1), values)), parameter)

    if isinstance(parameter, list):
        return [resolve_parameter(item, values) for item in parameter]

    if isinstance(parameter, dict):
        return {key: resolve_parameter(value, values) for key, value in parameter.items()}

    return parameter


def json_text(value: Any) -> str:
    if isinstance(value, str):
        return value

    return json.dumps(value)


def run_component_task(task: Dict[str, Any], values: Dict[str, Any]) -> Any:
    task_type = task["type"]

    if not COMPONENT_TASK_TYPE_PATTERN.fullmatch(task_type):
        fail(
            "task " + task["name"] + " has type " + task_type
            + "; a component task type is <component>/v<version>/<action>"
        )

    if "perform" in task or "connections" in task:
        fail(
            "task " + task["name"] + " runs component action " + task_type
            + ", so it cannot declare perform or connections"
        )

    parameters = resolve_parameter(task.get("parameters") or {}, values)

    print("  " + task_type + "(" + json.dumps(parameters) + ")")

    return parameters


def main(arguments: List[str]) -> None:
    if not arguments:
        print("Usage: python3 scripts/check.py <file> [inputName=value ...]", file=sys.stderr)

        sys.exit(1)

    file, input_arguments = arguments[0], arguments[1:]

    definition = evaluate(file)

    if not isinstance(definition, dict):
        fail("the file must evaluate to a dict - end it with the definition variable alone on the last line")

    if "componentName" in definition:
        component_version = definition.get("componentVersion")

        if (
            not isinstance(definition["componentName"], str)
            or not isinstance(component_version, int)
            or isinstance(component_version, bool)
        ):
            fail("an integration needs a componentName string and an integer componentVersion")

        print("integration " + definition["componentName"] + " v" + str(component_version))
    else:
        if not isinstance(definition.get("name"), str) or definition["name"] == "":
            fail("a project needs a name")

        print("project " + definition["name"] + " version " + str(definition.get("version")))

    workflows = definition.get("workflows")

    if not isinstance(workflows, list) or not workflows:
        fail("workflows must be a non-empty list")

    workflow_input_defaults: Dict[str, Any] = {}

    for input_argument in input_arguments:
        name, _, value = input_argument.partition("=")

        workflow_input_defaults[name] = value

    for workflow in workflows:
        triggers = workflow.get("triggers")

        print(
            "workflow " + str(workflow.get("name")) + " (" + str(workflow.get("label")) + ")"
            + (" triggers: " + ", ".join(trigger["type"] for trigger in triggers) if triggers is not None else "")
        )

        workflow_input = dict(workflow_input_defaults)

        for trigger in triggers or []:
            workflow_input[trigger["name"]] = trigger_output(trigger)

        for task in workflow.get("tasks") or []:
            if isinstance(task.get("name"), str) and isinstance(task.get("type"), str):
                component_task_result = run_component_task(task, workflow_input)

                print("  task " + task["name"] + " -> " + json.dumps(component_task_result))

                workflow_input[task["name"]] = component_task_result

                continue

            if not isinstance(task.get("name"), str) or not callable(task.get("perform")):
                fail("every task needs a name and either a perform function or a component action type")

            perform = task["perform"]
            task_input = dict(workflow_input)

            if required_parameter_count(perform) >= 3:
                result = perform(task_input, task_connection(task), StubContext())
            else:
                result = perform(task_input, StubContext())

            print("  task " + task["name"] + " -> " + json.dumps(result))

            workflow_input[task["name"]] = result

    print("OK")


if __name__ == "__main__":
    main(sys.argv[1:])
