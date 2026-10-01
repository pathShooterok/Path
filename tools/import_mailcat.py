import ast
import json
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

MAILCAT_SOURCE = (
    PROJECT_ROOT.parent
    / "mailcat"
    / "src"
    / "mailcat"
    / "__init__.py"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mail_providers.json"
)


DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-z0-9]"
    r"(?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"\.)+"
    r"[a-z]{2,63}$",
    re.IGNORECASE,
)

EMAIL_DOMAIN_RE = re.compile(
    r"@([a-z0-9]"
    r"(?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9]"
    r"(?:[a-z0-9-]{0,61}[a-z0-9])?"
    r")+)",
    re.IGNORECASE,
)


TEST_DOMAINS = {
    "example.com",
    "example.org",
    "example.net",
}


PROVIDER_NAMES = {
    "gmail": "Google",
    "yandex": "Yandex",
    "proton": "Proton",
    "mailRu": "MailRU",
    "rambler": "Rambler",
    "yahoo": "Yahoo",
    "aol": "AOL",
    "outlook": "Outlook",
    "zoho": "Zoho",
    "eclipso": "Eclipso",
    "posteo": "Posteo",
    "firemail": "Firemail",
    "fastmail": "Fastmail",
    "startmail": "StartMail",
    "ukrnet": "UkrNet",
    "runbox": "Runbox",
    "duckgo": "DuckGo",
    "aikq": "Aikq",
    "emailn": "emailn",
    "vivaldi": "Vivaldi",
    "mailDe": "mail.de",
    "intpl": "int.pl",
    "interia": "Interia",
    "tpl": "T.pl",
    "onet": "Onet",
    "mailum": "Mailum",
}


def normalize_domain(value: str) -> str | None:
    value = value.strip().lower()
    value = value.lstrip("@")

    if value in TEST_DOMAINS:
        return None

    if DOMAIN_RE.fullmatch(value):
        return value

    return None


def extract_email_domains(value: str) -> set[str]:
    domains = set()

    for match in EMAIL_DOMAIN_RE.finditer(value):
        domain = normalize_domain(match.group(1))

        if domain:
            domains.add(domain)

    return domains


def get_string(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value

    return None


def provider_name(function_name: str) -> str:
    return PROVIDER_NAMES.get(
        function_name,
        function_name,
    )


def get_active_checkers(tree):
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue

            if target.id != "CHECKERS":
                continue

            if not isinstance(
                node.value,
                (ast.List, ast.Tuple),
            ):
                return []

            return [
                item.id
                for item in node.value.elts
                if isinstance(item, ast.Name)
            ]

    return []


def get_functions(tree):
    functions = {}

    for node in tree.body:
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            functions[node.name] = node

    return functions


def get_global_values(tree):
    """
    Collect useful domain-like values from module-level
    variables. This handles things such as:

        _MSA_DOMAINS = [...]
        someDomain = "yahoo.com"
    """

    result = {}

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue

            name = target.id
            value = node.value
            domains = set()

            if isinstance(
                value,
                (ast.List, ast.Tuple, ast.Set),
            ):
                for item in value.elts:
                    string = get_string(item)

                    if not string:
                        continue

                    domain = normalize_domain(string)

                    if domain:
                        domains.add(domain)

                    domains.update(
                        extract_email_domains(string)
                    )

            elif isinstance(value, ast.Constant):
                string = get_string(value)

                if string:
                    domain = normalize_domain(string)

                    if domain:
                        domains.add(domain)

                    domains.update(
                        extract_email_domains(string)
                    )

            if domains:
                result[name] = domains

    return result


def add_value(domains: set[str], value: str):
    domain = normalize_domain(value)

    if domain:
        domains.add(domain)

    domains.update(
        extract_email_domains(value)
    )


def extract_domains_from_function(
    function_node,
    global_values,
):
    domains = set()

    for node in ast.walk(function_node):


        if isinstance(node, ast.Assign):
            value = node.value

            if isinstance(
                value,
                (ast.List, ast.Tuple, ast.Set),
            ):
                for item in value.elts:
                    string = get_string(item)

                    if string:
                        add_value(
                            domains,
                            string,
                        )

            elif isinstance(value, ast.Constant):
                string = get_string(value)

                if string:
                    add_value(
                        domains,
                        string,
                    )

        if isinstance(node, ast.Name):
            if node.id in global_values:
                domains.update(
                    global_values[node.id]
                )

   
        if isinstance(node, ast.Call):
            function = node.func

            if (
                isinstance(function, ast.Name)
                and function.id == "code250"
            ):
                for argument in node.args:
                    string = get_string(argument)

                    if string:
                        add_value(
                            domains,
                            string,
                        )


        if isinstance(node, ast.Dict):
            for key, value in zip(
                node.keys,
                node.values,
            ):
                key_string = get_string(key)
                value_string = get_string(value)

                if not value_string:
                    continue

                if key_string in {
                    "domain",
                    "maildomain",
                    "mailDomain",
                    "yidDomain",
                }:
                    add_value(
                        domains,
                        value_string,
                    )

      
        if isinstance(node, ast.JoinedStr):
            for part in node.values:
                if not isinstance(
                    part,
                    ast.Constant,
                ):
                    continue

                if not isinstance(
                    part.value,
                    str,
                ):
                    continue

                domains.update(
                    extract_email_domains(
                        part.value
                    )
                )

    
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                domains.update(
                    extract_email_domains(
                        node.value
                    )
                )

    return domains


def parse_mailcat():
    if not MAILCAT_SOURCE.exists():
        raise FileNotFoundError(
            f"Mailcat source not found:\n"
            f"{MAILCAT_SOURCE}"
        )

    source = MAILCAT_SOURCE.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    tree = ast.parse(source)

    active_checkers = get_active_checkers(tree)
    functions = get_functions(tree)
    global_values = get_global_values(tree)

    if not active_checkers:
        raise RuntimeError(
            "Could not find active CHECKERS list"
        )

    providers = {}

    for checker in active_checkers:
        function_node = functions.get(
            checker
        )

        if function_node is None:
            continue

        domains = extract_domains_from_function(
            function_node,
            global_values,
        )

        if not domains:
            continue

        providers[
            provider_name(checker)
        ] = sorted(domains)

    return providers, active_checkers


def main():
    print("[*] Mailcat source:")
    print(f"    {MAILCAT_SOURCE}")

    providers, active_checkers = parse_mailcat()

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            providers,
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )

    provider_count = len(providers)

    domain_count = sum(
        len(domains)
        for domains in providers.values()
    )

    print(
        f"[*] Active checkers: "
        f"{len(active_checkers)}"
    )

    print(
        f"[*] Providers exported: "
        f"{provider_count}"
    )

    print(
        f"[*] Domains exported: "
        f"{domain_count}"
    )

    print("[*] Database written to:")
    print(f"    {OUTPUT_FILE}")


if __name__ == "__main__":
    main()