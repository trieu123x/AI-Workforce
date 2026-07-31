def ensure_tool_allowed(tool_name: str, allowed: set[str], denied: set[str]) -> None:
    if tool_name in denied or tool_name not in allowed:
        raise PermissionError(f"Tool is not allowed: {tool_name}")
